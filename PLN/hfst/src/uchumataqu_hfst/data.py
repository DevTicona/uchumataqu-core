"""Importación trazable; nunca transforma una hipótesis en anotación validada."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('palabras.json', 'oraciones.json', 'diccionario.json',
           'reglas_de_escritura_y_gram_tica_uchumataqu.md')
POS = {'sustantivo': 'N', 'verbo': 'V', 'adjetivo': 'ADJ', 'numeral': 'NUM',
       'pronombre': 'PRON', 'expresión': 'EXPR', 'adverbio interrogativo': 'ADVINT',
       'determinante_posesivo': 'DETPOSS', 'determinante': 'DET', 'adverbio': 'ADV',
       'pronombre interrogativo': 'PRONINT'}
SUFFIXES = {'naka': ['naka'], 'chay': ['chay'], 'pini': ['pini'],
            'pinichay': ['pini', 'chay'], 'nakachay': ['naka', 'chay'],
            'nakapini': ['naka', 'pini']}
TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)


def normalize(text):
    return unicodedata.normalize('NFC', text).lower().replace('’', "'").replace('ʼ', "'").strip()


def supported(text):
    return bool(text) and len(text) <= 128 and TOKEN.fullmatch(text) is not None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    """Conserva la primera copia; exige revisión explícita si cambian los originales."""
    hashes = {}
    (ROOT / 'shared/raw').mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        source = ROOT.parent / name
        destination = ROOT / 'shared/raw' / name
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError(f'La fuente cambió respecto al snapshot: {name}')
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
        hashes[name] = sha256(source)
    write_json(ROOT / 'shared/sources/hashes.json', hashes)
    return hashes


def prepare():
    words = read_json(ROOT / 'shared/raw/palabras.json')['palabras']
    sentences = read_json(ROOT / 'shared/raw/oraciones.json')['oraciones']
    dictionary = read_json(ROOT / 'shared/raw/diccionario.json')
    records, excluded = [], []
    identifiers = set()

    def add(record):
        if record['id'] in identifiers:
            raise ValueError(f"ID duplicado: {record['id']}")
        identifiers.add(record['id'])
        if supported(record['surface']):
            records.append(record)
        else:
            excluded.append(record)

    for word in words:
        lemma = normalize(word['uch'])
        for form in [word, *word.get('formas', [])]:
            surface = normalize(form['uch'])
            tail = surface[len(lemma):] if surface.startswith(lemma) else None
            suffixes = SUFFIXES.get(tail, []) if form is not word else []
            add({'id': 'p_' + form['id'], 'surface': surface, 'original': form['uch'],
                 'lemma': lemma, 'family_id': word['id'], 'pos': POS[word['categoria_gramatical']],
                 'translation': form['es'], 'segments': [lemma, *suffixes] if suffixes else [surface],
                 'suffixes': suffixes, 'features': {}, 'source': 'palabras.json',
                 'source_id': form['id'], 'review_status': 'documented_unreviewed',
                 'segmentation_status': 'hypothesis' if suffixes else 'not_asserted'})

    contexts = {}
    for sentence in sentences:
        for token in TOKEN.findall(normalize(sentence['uch'])):
            contexts.setdefault(token, []).append(sentence['id'])
    known = {r['surface'] for r in records}
    dictionary_index = {}
    for index, entry in enumerate(dictionary):
        dictionary_index.setdefault(normalize(entry['palabraUchumataqu']), []).append((index, entry))
    for token, ids in sorted(contexts.items()):
        if token in known:
            continue
        matches = dictionary_index.get(token, [])
        # Se incluyen todos los significados atestiguados, sin seleccionar uno por contexto.
        for index, entry in matches or [(None, None)]:
            identifier = f'd_{index:04d}' if entry else 'o_' + hashlib.sha256(token.encode()).hexdigest()[:16]
            add({'id': identifier, 'surface': token, 'original': token, 'lemma': token,
                 'family_id': identifier, 'pos': 'UNK', 'translation': entry['palabraEspanol'] if entry else None,
                 'segments': [token], 'suffixes': [], 'features': {},
                 'source': 'diccionario.json' if entry else 'oraciones.json',
                 'source_id': index if entry else ids, 'context_ids': sorted(set(ids)),
                 'review_status': 'documented_unreviewed', 'segmentation_status': 'not_asserted'})
    records.sort(key=lambda r: r['id'])
    for record in records:
        record['context_ids'] = sorted(set(contexts.get(record['surface'], [])))
    audit = {'primary_entries': len(words), 'primary_related_forms': sum(len(w.get('formas', [])) for w in words),
             'sentences': len(sentences), 'dictionary_entries_available': len(dictionary),
             'records': len(records), 'unique_surfaces': len({r['surface'] for r in records}),
             'sentence_token_types': len(contexts), 'excluded': excluded,
             'record_sources': {s: sum(r['source'] == s for r in records) for s in SOURCES[:3]},
             'linguistically_validated': 0}
    write_json(ROOT / 'shared/annotated/analyses.json', records)
    write_json(ROOT / 'reports/data-audit.json', audit)
    return records, audit
