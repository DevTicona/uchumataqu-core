import hashlib
import json
import random
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAD, UNK, BOS, EOS = '<PAD>', '<UNK>', '<BOS>', '<EOS>'
SPECIAL = [PAD, UNK, BOS, EOS]
FIELDS = ['<LEMMA>', '<POS>', '<SEG>', '<FEAT>', '<NONE>']
POS = {'sustantivo': 'N', 'verbo': 'V', 'adjetivo': 'ADJ', 'numeral': 'NUM',
       'pronombre': 'PRON', 'expresión': 'EXPR', 'adverbio interrogativo': 'ADVINT',
       'determinante_posesivo': 'DETPOSS', 'determinante': 'DET', 'adverbio': 'ADV',
       'pronombre interrogativo': 'PRONINT'}
SUFFIXES = {'naka': ['naka'], 'chay': ['chay'], 'pini': ['pini'],
            'pinichay': ['pini', 'chay'], 'nakachay': ['naka', 'chay'], 'nakapini': ['naka', 'pini']}
SOURCES = ['palabras.json', 'oraciones.json', 'diccionario.json', 'reglas_de_escritura_y_gram_tica_uchumataqu.md']
WORD = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return unicodedata.normalize('NFC', text).lower().replace('’', "'").replace('ʼ', "'").strip()


def tokens(record):
    return ['<LEMMA>', *record['lemma'], '<POS>', '<' + record['pos'] + '>',
            '<SEG>', *'|'.join(record['segments']), '<FEAT>', '<NONE>', EOS]


def split_families(records, seed):
    families = sorted({r['family_id'] for r in records})
    random.Random(seed).shuffle(families)
    n = len(families)
    groups = {'train': set(families[:int(n * .8)]),
              'dev': set(families[int(n * .8):int(n * .9)]), 'test': set(families[int(n * .9):])}
    return {part: [r['id'] for r in records if r['family_id'] in group] for part, group in groups.items()}


def prepare(config):
    hashes = {}
    for name in SOURCES:
        source, dest = ROOT.parent / name, ROOT / 'data/raw' / name
        if dest.exists() and digest(dest) != digest(source):
            raise ValueError(f'Fuente modificada: {name}; versionar el dataset antes de continuar.')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes(source.read_bytes())
        hashes[name] = digest(source)
    words = read(ROOT / 'data/raw/palabras.json')['palabras']
    sentences = read(ROOT / 'data/raw/oraciones.json')['oraciones']
    contexts = {}
    for sentence in sentences:
        for word in WORD.findall(normalize(sentence['uch'])):
            contexts.setdefault(word, []).append(sentence['id'])
    records, excluded = [], []
    for word in words:
        lemma = normalize(word['uch'])
        for form in [word, *word.get('formas', [])]:
            surface = normalize(form['uch'])
            tail = surface[len(lemma):] if surface.startswith(lemma) else None
            suffixes = SUFFIXES.get(tail, [])
            record = {'id': form['id'], 'family_id': word['id'], 'surface': surface,
                      'lemma': lemma, 'pos': POS[word['categoria_gramatical']],
                      'segments': [lemma, *suffixes] if suffixes else [surface], 'features': {},
                      'translation': form['es'], 'source': 'palabras.json',
                      'context_ids': sorted(set(contexts.get(surface, []))),
                      'review_status': 'documented_unreviewed',
                      'segmentation_status': 'hypothesis' if suffixes else 'not_asserted'}
            if not WORD.fullmatch(surface) or len(surface) > config['max_input'] or len(tokens(record)) > config['max_output']:
                excluded.append(record)
            else:
                records.append(record)
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('Identificadores duplicados.')
    # Una superficie compartida por varias familias se excluye del piloto para evitar filtración.
    counts = {}
    for record in records:
        counts.setdefault(record['surface'], []).append(record)
    ambiguous = {surface for surface, values in counts.items() if len(values) > 1}
    excluded.extend(r for r in records if r['surface'] in ambiguous)
    records = sorted((r for r in records if r['surface'] not in ambiguous), key=lambda r: r['id'])
    splits = split_families(records, config['split_seed'])
    train = [r for r in records if r['id'] in splits['train']]
    vocab = {'input': SPECIAL + sorted({c for r in train for c in r['surface']}),
             'output': SPECIAL + FIELDS + ['<' + p + '>' for p in sorted(set(POS.values()))]
                       + sorted({c for r in train for c in r['lemma'] + '|'.join(r['segments'])} | {'|'})}
    artifact = {'records': records, 'splits': splits, 'vocab': vocab, 'source_sha256': hashes,
                'annotation_policy': 'exploratory_unreviewed_not_gold', 'split_seed': config['split_seed']}
    destination = ROOT / 'data/prepared/dataset.json'
    if destination.exists() and read(destination) != artifact:
        raise ValueError('Dataset congelado distinto; crear una nueva versión antes de cambiarlo.')
    write(destination, artifact)
    write(ROOT / 'reports/data-audit.json', {'records': len(records), 'families': len({r['family_id'] for r in records}),
          'split_sizes': {k: len(v) for k, v in splits.items()}, 'excluded': excluded,
          'sentences': len(sentences), 'sentence_only_tokens': sorted(set(contexts) - {r['surface'] for r in records}),
          'dictionary_available': len(read(ROOT / 'data/raw/diccionario.json')),
          'dictionary_training_records': 0, 'reviewed_records': 0,
          'reason_no_augmentation': 'No inventar análisis morfológicos a partir de traducciones; piloto primario primero.'})
    return artifact


class Codec:
    def __init__(self, vocab, config):
        self.vocab, self.config = vocab, config
        self.input = {c: i for i, c in enumerate(vocab['input'])}
        self.output = {c: i for i, c in enumerate(vocab['output'])}

    def encode(self, text):
        text = normalize(text)
        if not WORD.fullmatch(text) or len(text) > self.config['max_input']:
            raise ValueError('unsupported_input')
        if any(c not in self.input for c in text):
            raise ValueError('unsupported_character')
        return [self.input[c] for c in text] + [0] * (self.config['max_input'] - len(text))

    def target(self, record):
        values = tokens(record)
        if len(values) > self.config['max_output']:
            raise ValueError('Salida demasiado larga; no se permite truncar.')
        return [self.output.get(t, 1) for t in values]

    def decode(self, ids):
        values = []
        for i in ids:
            values.append(self.vocab['output'][i])
            if values[-1] == EOS:
                break
        return values


def parse(values, surface):
    if not values or values[-1] != EOS:
        return None
    pattern = r'<LEMMA>([^<>]+)<POS><([A-Z]+)><SEG>([^<>]+)<FEAT><NONE><EOS>'
    match = re.fullmatch(pattern, ''.join(values))
    if not match or match[2] not in POS.values():
        return None
    lemma, pos, segmented = match.groups()
    segments = segmented.split('|')
    if not all(segments) or ''.join(segments) != surface or not WORD.fullmatch(lemma):
        return None
    return {'lemma': lemma, 'pos': pos, 'segments': segments, 'features': {}}
