from .data import ROOT, Codec, digest, normalize, parse, read
from .exporting import generate_onnx, sessions


class Analyzer:
    def __init__(self, folder=None):
        folder = folder or ROOT / 'export/pln-seq2seq-v1'
        manifest = read(folder / 'manifest.json')
        for name in ('encoder.onnx', 'decoder_step.onnx', 'vocab.json', 'config.json', 'lexicon.json'):
            if digest(folder / name) != manifest['files'][name]:
                raise ValueError(f'Integridad incorrecta: {name}')
        self.codec = Codec(read(folder / 'vocab.json'), read(folder / 'config.json'))
        self.encoder, self.decoder = sessions(folder)
        self.records = read(folder / 'lexicon.json')

    def analyze(self, text):
        surface = normalize(text)
        result = {'input': text, 'normalized': surface, 'engine': 'seq2seq_onnx', 'deployment_allowed': False}
        try:
            ids = self.codec.encode(surface)
        except ValueError as error:
            return {**result, 'status': str(error), 'prediction': None}
        values = self.codec.decode(generate_onnx(self.encoder, self.decoder, ids, self.codec.config['max_output']))
        prediction = parse(values, surface)
        evidence = [r for r in self.records if r['surface'] == surface and prediction
                    and all(prediction[key] == r[key] for key in ('lemma', 'pos', 'segments', 'features'))]
        return {**result, 'status': 'experimental_match' if evidence else 'abstained',
                'prediction': prediction, 'raw_tokens': values, 'evidence_ids': [r['id'] for r in evidence],
                'review_status': 'documented_unreviewed' if evidence else None,
                'note': 'Hipótesis neuronal; no genera una explicación lingüística validada.'}
