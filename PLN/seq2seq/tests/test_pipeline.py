import shutil

import numpy as np
import pytest
import torch

from uchumataqu_seq2seq.data import ROOT, Codec, digest, normalize, parse, read, split_families, tokens
from uchumataqu_seq2seq.evaluation import distance, nearest
from uchumataqu_seq2seq.exporting import generate_onnx, sessions
from uchumataqu_seq2seq.model import Seq2Seq


@pytest.fixture(scope='module')
def dataset():
    return read(ROOT / 'data/prepared/dataset.json')


@pytest.fixture(scope='module')
def codec(dataset):
    return Codec(dataset['vocab'], read(ROOT / 'configs/pilot.json'))


def test_families_and_surfaces_do_not_leak(dataset):
    families, surfaces = {}, {}
    for name, ids in dataset['splits'].items():
        rows = [r for r in dataset['records'] if r['id'] in ids]
        families[name] = {r['family_id'] for r in rows}
        surfaces[name] = {r['surface'] for r in rows}
    for a, b in [('train', 'dev'), ('train', 'test'), ('dev', 'test')]:
        assert families[a].isdisjoint(families[b])
        assert surfaces[a].isdisjoint(surfaces[b])
    assert sum(map(len, dataset['splits'].values())) == len(dataset['records'])
    assert split_families(dataset['records'], dataset['split_seed']) == dataset['splits']


def test_vocab_uses_training_characters_only(dataset):
    rows = [r for r in dataset['records'] if r['id'] in dataset['splits']['train']]
    assert set(dataset['vocab']['input'][4:]) == {c for r in rows for c in r['surface']}


def test_all_targets_round_trip_without_validating_hypotheses(dataset):
    for record in dataset['records']:
        parsed = parse(tokens(record), record['surface'])
        assert parsed == {k: record[k] for k in ('lemma', 'pos', 'segments', 'features')}
        assert record['review_status'] == 'documented_unreviewed'
    grandfather = next(r for r in dataset['records'] if r['surface'] == 'achichay')
    assert grandfather['segments'] == ['achichay']


@pytest.mark.parametrize('text', ['', ' ', 'achasi otra', '<achasi>', 'a' * 33, 'abc123', '😀', 'ê'])
def test_unsupported_input_is_never_truncated(codec, text):
    with pytest.raises(ValueError):
        codec.encode(text)


def test_normalization(codec):
    assert normalize(' CHʼATSCHAY ') == "ch'atschay"
    assert codec.encode('PÄKU') == codec.encode('pa\u0308ku')
    assert normalize('päku') != normalize('paku')


def test_malformed_output_and_wrong_reconstruction():
    values = ['<LEMMA>', 'a', '<POS>', '<N>', '<SEG>', 'a', '<FEAT>', '<NONE>', '<EOS>']
    assert parse(values, 'a')
    assert parse(values[:-1], 'a') is None
    assert parse(values, 'b') is None
    assert parse(values + ['a'], 'a') is None
    assert parse([v.replace('<N>', '<FAKE>') for v in values], 'a') is None


def test_padding_does_not_change_encoder_state(codec, dataset):
    torch.manual_seed(1)
    torch.set_num_threads(1)
    model = Seq2Seq(dataset['vocab'], codec.config).eval()
    ids = torch.tensor([codec.encode('achasi')])
    short = ids[:, :6]
    with torch.no_grad():
        _, padded_state = model.encoder(ids, (ids != 0).float())
        _, short_state = model.encoder(short, (short != 0).float())
    torch.testing.assert_close(padded_state, short_state)


def test_teacher_forcing_loss_has_finite_gradients(codec, dataset):
    model = Seq2Seq(dataset['vocab'], codec.config)
    row = next(r for r in dataset['records'] if r['id'] in dataset['splits']['train'])
    ids = torch.tensor([codec.encode(row['surface'])])
    target = torch.tensor([codec.target(row)])
    output = model(ids, target)
    loss = torch.nn.functional.cross_entropy(output.flatten(0, 1), target.flatten(), ignore_index=0)
    loss.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())


def test_baseline_preserves_real_words_and_ties():
    assert distance('achasi', 'achazi') == 1
    assert nearest('casa', ['casa', 'cosa']) == {'status': 'exact', 'candidates': ['casa']}
    assert nearest('cusa', ['casa', 'cosa'])['candidates'] == ['casa', 'cosa']
    assert nearest('zzzzz', ['achasi'])['status'] == 'unknown'


def test_smoke_onnx_uses_fixed_batch_and_has_sequence_parity(codec):
    folder = ROOT / 'runs/export-smoke'
    encoder, decoder = sessions(folder)
    assert encoder.get_inputs()[0].shape == [1, 32]
    for vector in read(folder / 'test_vectors.json'):
        predicted = codec.decode(generate_onnx(encoder, decoder, codec.encode(vector['input']), codec.config['max_output']))
        assert predicted == vector['output_tokens']


def test_originals_unchanged(dataset):
    for name, expected in dataset['source_sha256'].items():
        assert digest(ROOT.parent / name) == expected
        assert digest(ROOT / 'data/raw' / name) == expected


def test_export_rejects_corruption(tmp_path):
    from uchumataqu_seq2seq.runtime import Analyzer
    folder = ROOT / 'export/pln-seq2seq-v1'
    if not folder.exists():
        pytest.skip('La exportación entrenada aún no existe.')
    destination = tmp_path / 'package'
    shutil.copytree(folder, destination)
    (destination / 'vocab.json').write_text('{}')
    with pytest.raises(ValueError, match='Integridad'):
        Analyzer(destination)


def test_exported_package_checksums():
    folder = ROOT / 'export/pln-seq2seq-v1'
    if not folder.exists():
        pytest.skip('La exportación entrenada aún no existe.')
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert digest(folder / name) == expected
