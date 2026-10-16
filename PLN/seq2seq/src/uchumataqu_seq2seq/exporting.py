import shutil

import numpy as np
import onnx
import onnxruntime as ort
import torch

from .data import ROOT, Codec, digest, read, write
from .model import Seq2Seq
from .training import load_checkpoint


def sessions(folder):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return tuple(ort.InferenceSession(str(folder / name), sess_options=options, providers=['CPUExecutionProvider'])
                 for name in ('encoder.onnx', 'decoder_step.onnx'))


def generate_onnx(encoder, decoder, ids, max_output):
    ids = np.asarray([ids], dtype=np.int64)
    mask = (ids != 0).astype(np.float32)
    memory, state = encoder.run(None, {'ids': ids, 'mask': mask})
    previous = np.array([2], dtype=np.int64)
    values = []
    for _ in range(max_output):
        logits, state = decoder.run(None, {'previous': previous, 'state': state, 'memory': memory, 'mask': mask})
        logits[:, :3] = -1e4
        previous = np.argmax(logits, axis=1).astype(np.int64)
        values.append(int(previous[0]))
        if values[-1] == 3:
            break
    return values


def export_graphs(model, codec, folder, examples):
    folder.mkdir(parents=True, exist_ok=True)
    model.eval()
    ids = torch.tensor([codec.encode(examples[0])])
    mask = (ids != 0).float()
    with torch.no_grad():
        memory, state = model.encoder(ids, mask)
        # Batch=1 y longitud fija; decodificación fuera del grafo por contrato.
        torch.onnx.export(model.encoder, (ids, mask), folder / 'encoder.onnx',
                          input_names=['ids', 'mask'], output_names=['memory', 'state'],
                          opset_version=codec.config['opset'], dynamo=False)
        torch.onnx.export(model.decoder, (torch.tensor([2]), state, memory, mask), folder / 'decoder_step.onnx',
                          input_names=['previous', 'state', 'memory', 'mask'], output_names=['logits', 'next_state'],
                          opset_version=codec.config['opset'], dynamo=False)
    for name in ('encoder.onnx', 'decoder_step.onnx'):
        onnx.checker.check_model(onnx.load(folder / name))
    encoder, decoder = sessions(folder)
    vectors = []
    max_error = 0.0
    for text in examples:
        ids_list = codec.encode(text)
        ids = torch.tensor([ids_list])
        mask = (ids != 0).float()
        with torch.no_grad():
            memory, state = model.encoder(ids, mask)
            previous = torch.tensor([2])
            logits, next_state = model.decoder(previous, state, memory, mask)
        ort_memory, ort_state = encoder.run(None, {'ids': ids.numpy(), 'mask': mask.numpy()})
        ort_logits, ort_next = decoder.run(None, {'previous': previous.numpy(), 'state': ort_state,
                                                 'memory': ort_memory, 'mask': mask.numpy()})
        for expected, actual in ((memory.numpy(), ort_memory), (state.numpy(), ort_state),
                                 (logits.numpy(), ort_logits), (next_state.numpy(), ort_next)):
            np.testing.assert_allclose(expected, actual, rtol=1e-4, atol=1e-5)
            max_error = max(max_error, float(np.max(np.abs(expected - actual))))
        pytorch_values = codec.decode(model.generate(ids, codec.config['max_output'])[0])
        ort_values = codec.decode(generate_onnx(encoder, decoder, ids_list, codec.config['max_output']))
        if pytorch_values != ort_values:
            raise RuntimeError(f'Decodificación ONNX distinta para {text}')
        vectors.append({'input': text, 'output_tokens': ort_values})
    write(folder / 'test_vectors.json', vectors)
    report = {'examples': len(examples), 'max_absolute_tensor_error': max_error,
              'rtol': 1e-4, 'atol': 1e-5, 'sequence_parity': True, 'sentis_tested': False, 'android_tested': False}
    write(folder / 'parity.json', report)
    return report


def smoke(dataset, config):
    torch.set_num_threads(config['threads'])
    torch.manual_seed(0)
    codec = Codec(dataset['vocab'], config)
    examples = [r['surface'] for r in dataset['records'] if r['id'] in dataset['splits']['train']][:5]
    return export_graphs(Seq2Seq(dataset['vocab'], config), codec, ROOT / 'runs/export-smoke', examples)


def export(dataset):
    model, checkpoint = load_checkpoint(ROOT / 'runs/selected.pt')
    torch.set_num_threads(checkpoint['config']['threads'])
    if checkpoint['dataset_sha256'] != digest(ROOT / 'data/prepared/dataset.json'):
        raise ValueError('El dataset ya no coincide con el checkpoint.')
    codec = Codec(checkpoint['vocab'], checkpoint['config'])
    examples = []
    for record in dataset['records']:
        try:
            codec.encode(record['surface'])
            examples.append(record['surface'])
        except ValueError:
            pass
    folder = ROOT / 'export/pln-seq2seq-v1'
    report = export_graphs(model, codec, folder, examples)
    write(folder / 'vocab.json', checkpoint['vocab'])
    write(folder / 'config.json', checkpoint['config'])
    write(folder / 'lexicon.json', dataset['records'])
    shutil.copyfile(ROOT / 'reports/experiment.json', folder / 'metrics.json')
    resources = ROOT / 'resources'
    for source in resources.rglob('*'):
        if source.is_file():
            destination = folder / source.relative_to(resources)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    encoder, decoder = sessions(folder)
    contracts = {name: {'inputs': [{'name': v.name, 'shape': v.shape, 'type': v.type} for v in session.get_inputs()],
                         'outputs': [{'name': v.name, 'shape': v.shape, 'type': v.type} for v in session.get_outputs()]}
                 for name, session in [('encoder', encoder), ('decoder_step', decoder)]}
    write(folder / 'manifest.json', {'schema_version': 1, 'engine': 'seq2seq', 'deployment_allowed': False,
          'dataset_sha256': checkpoint['dataset_sha256'], 'checkpoint_sha256': digest(ROOT / 'runs/selected.pt'),
          'source_sha256': dataset['source_sha256'], 'requirements_sha256': digest(ROOT / 'requirements.lock'),
          'source_code_sha256': {p.name: digest(p) for p in sorted((ROOT / 'src/uchumataqu_seq2seq').glob('*.py'))},
          'seed': checkpoint['seed'], 'epoch': checkpoint['epoch'], 'opset': checkpoint['config']['opset'],
          'contracts': contracts, 'annotation_policy': dataset['annotation_policy'],
          'decoder': 'greedy; mask PAD/UNK/BOS logits; stop at EOS or max_output; reject missing EOS',
          'files': {str(p.relative_to(folder)): digest(p) for p in folder.rglob('*') if p.is_file()
                    and p.name not in {'manifest.json', 'SHA256SUMS'}}})
    (folder / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.relative_to(folder)}\n'
        for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
    return report
