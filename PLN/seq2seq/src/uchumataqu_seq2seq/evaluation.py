from collections import Counter

import torch

from .data import parse, tokens


@torch.inference_mode()
def evaluate(model, records, codec):
    model.eval()
    predictions = {}
    eligible = []
    for record in records:
        try:
            eligible.append((record, codec.encode(record['surface'])))
        except ValueError:
            predictions[record['id']] = []
    for start in range(0, len(eligible), 32):
        batch = eligible[start:start + 32]
        outputs = model.generate(torch.tensor([ids for _, ids in batch]), codec.config['max_output'])
        for (record, _), output in zip(batch, outputs):
            predictions[record['id']] = codec.decode(output)
    rows = []
    for record in records:
        values = predictions[record['id']]
        parsed = parse(values, record['surface'])
        rows.append({'id': record['id'], 'surface': record['surface'], 'expected': tokens(record),
                     'prediction': values, 'valid': parsed is not None, 'exact': values == tokens(record),
                     'lemma_exact': bool(parsed and parsed['lemma'] == record['lemma']),
                     'segments_exact': bool(parsed and parsed['segments'] == record['segments']),
                     'pos_exact': bool(parsed and parsed['pos'] == record['pos'])})
    n = len(rows)
    metrics = {'count': n, 'annotation_status': 'unreviewed_provisional_targets',
               **{key: sum(row[key] for row in rows) / n if n else None
                  for key in ('valid', 'exact', 'lemma_exact', 'segments_exact', 'pos_exact')},
               'unsupported_count': len(records) - len(eligible), 'features_f1': None,
               'features_note': 'No hay rasgos gramaticales anotados; no se calcula una métrica vacía.'}
    return metrics, rows


def distance(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        next_row = [i]
        for j, b in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = next_row
    return row[-1]


def nearest(surface, lexicon, limit=1):
    if surface in lexicon:
        return {'status': 'exact', 'candidates': [surface]}
    distances = [(distance(surface, candidate), candidate) for candidate in lexicon
                 if abs(len(candidate) - len(surface)) <= limit]
    best = min((d for d, _ in distances), default=limit + 1)
    candidates = sorted(c for d, c in distances if d == best and d <= limit)
    return {'status': 'suggestions' if candidates else 'unknown', 'candidates': candidates}


def baseline_report(train, test):
    known = {r['surface'] for r in train}
    pos = Counter(r['pos'] for r in train).most_common(1)[0][0]
    return {'count': len(test), 'train_only_dictionary_exact_coverage': sum(r['surface'] in known for r in test) / len(test),
            'identity_lemma_exact': sum(r['lemma'] == r['surface'] for r in test) / len(test),
            'identity_segments_exact': sum(r['segments'] == [r['surface']] for r in test) / len(test),
            'majority_pos': pos, 'majority_pos_exact': sum(r['pos'] == pos for r in test) / len(test),
            'full_documented_dictionary_coverage': 1.0,
            'access_note': 'El diccionario completo conoce las formas de prueba; no es generalización a familias nuevas.',
            'educational_diagnosis_evaluated': False}
