"""
build.py
Compilación, verificación de paridad lingüística y exportación del transductor finito HFST
para la morfología de la lengua Uchumataqu (Uru de Irohito).

Flujo del compilador:
  1. Genera la gramática formal en formato Lexc (grammar/lexicon.lexc) a partir de raíces y formas documentadas.
  2. Compila el transductor generador léxico con hfst-lexc.
  3. Invierte el transductor con hfst-invert para obtener el analizador morfológico superficie -> análisis.
  4. Optimiza el transductor a formato de consulta indexada en memoria (analyzer.hfstol) con hfst-fst2fst -O.
  5. Ejecuta pruebas de regresión contra el 100% de formas documentadas para garantizar cero discrepancias.
  6. Exporta el índice de consulta en JSON y binarios para el runtime en Unity / C#.
"""
import shutil
from collections import defaultdict

from .data import ROOT, prepare, sha256, snapshot, write_json
from .native import lookup, run


def escape(value: str) -> str:
    """Escapa caracteres especiales para el formato lexc de HFST."""
    return ''.join('%' + c if c in '%!:;# +<>0\t\n"' else c for c in value)


def annotation(record: dict) -> str:
    """Construye la cadena de etiquetas morfosintácticas canónicas (+POS+ID=id+SUF=suf)."""
    return '+' + record['pos'] + '+ID=' + record['id'] + ''.join('+SUF=' + s for s in record['suffixes'])


def analysis(record: dict) -> str:
    """Retorna la representación de análisis formal: lema + etiquetas morfológicas."""
    return record['lemma'] + annotation(record)


def grammar(records: list) -> str:
    """
    Construye la especificación léxica formal en formato Lexc.
    Define los símbolos multicarácter, el léxico Root y los léxicos de continuación
    para raíces regulares, sufijos de flexión y formas irregulares/supletivas.
    """
    tags = sorted({tag for r in records for tag in annotation(r).split('+') if tag})
    lines = ['Multichar_Symbols', *('+' + tag for tag in tags), '', 'LEXICON Root']
    families = defaultdict(list)
    for record in records:
        families[(record['family_id'], record['lemma'])].append(record)
    continuations = []
    for i, ((_, lemma), forms) in enumerate(sorted(families.items())):
        regular = [r for r in forms if r['surface'] == lemma or r['suffixes']]
        irregular = [r for r in forms if r not in regular]
        if regular:
            lines.append(f'{escape(lemma)}:{escape(lemma)} F{i} ;')
            continuations.append(f'\nLEXICON F{i}')
            for record in regular:
                tail = record['surface'][len(lemma):]
                continuations.append(f'{annotation(record)}:{escape(tail) or "0"} # ;')
        for record in irregular:
            lines.append(f'{escape(lemma)}{annotation(record)}:{escape(record["surface"])} # ;')
    return '\n'.join([*lines, *continuations, ''])


def build():
    """
    Orquestador principal de compilación y verificación HFST.
    Ejecuta todo el ciclo de construcción, prueba de paridad y exportación.
    """
    # 1. Tomar snapshot de hashes de fuentes de datos
    hashes = snapshot()
    records, audit = prepare()
    build_dir = ROOT / 'build'
    build_dir.mkdir(parents=True, exist_ok=True)
    grammar_path = ROOT / 'grammar/lexicon.lexc'
    grammar_path.parent.mkdir(parents=True, exist_ok=True)
    grammar_path.write_text(grammar(records), encoding='utf-8')

    # 2. Compilar lexc -> generador HFST
    run('hfst-lexc', '--quiet', grammar_path, '-o', build_dir / 'generator.hfst')

    # 3. Invertir transductor para análisis (superficie -> análisis morfológico)
    run('hfst-invert', '-i', build_dir / 'generator.hfst', '-o', build_dir / 'analyzer.hfst')

    # 4. Optimizar a formato hfstol (transductor de búsqueda indexada en memoria)
    run('hfst-fst2fst', '-O', '-i', build_dir / 'analyzer.hfst', '-o', build_dir / 'analyzer.hfstol')

    # 5. Verificación exhaustiva: 100% de formas documentadas deben analizarse idénticamente
    expected = defaultdict(set)
    for record in records:
        expected[record['surface']].add(analysis(record))
    for model in ('analyzer.hfst', 'analyzer.hfstol'):
        actual = lookup(build_dir / model, sorted(expected))
        if actual != expected:
            errors = {s: {'expected': sorted(expected[s]), 'actual': sorted(actual.get(s, []))}
                      for s in expected if actual.get(s) != expected[s]}
            write_json(ROOT / 'reports/build-errors.json', errors)
            raise RuntimeError(f'Falló la cobertura/paridad de {model}; ver build-errors.json')
    generated = lookup(build_dir / 'generator.hfst', [analysis(r) for r in records])
    if any(generated[analysis(r)] != {r['surface']} for r in records):
        raise RuntimeError('Falló la generación inversa.')
    paths = run('hfst-fst2strings', '-n', str(len(records) + 1), build_dir / 'generator.hfst')
    if set(paths.splitlines()) != {analysis(r) + ':' + r['surface'] for r in records}:
        raise RuntimeError('El transductor genera rutas no documentadas.')
    metrics = {'kind': 'exhaustive_lexicon_regression_not_generalization',
               'analysis_records_checked': len(records), 'surfaces_checked': len(expected),
               'analysis_exact_match': 1.0, 'generation_exact_match': 1.0,
               'optimized_parity': True, 'linguistically_validated_records': 0,
               'all_paths_documented': True,
               'android_tested': False, 'audit': audit}
    write_json(ROOT / 'reports/hfst-metrics.json', metrics)
    export = ROOT / 'export/pln-hfst-v1'
    export.mkdir(parents=True, exist_ok=True)
    for resource in (ROOT / 'resources').rglob('*'):
        if resource.is_file():
            destination = export / resource.relative_to(ROOT / 'resources')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resource, destination)
    for name in ('generator.hfst', 'analyzer.hfst', 'analyzer.hfstol'):
        shutil.copyfile(build_dir / name, export / name)
    write_json(export / 'analyses.json', records)
    write_json(export / 'lookup-index.json', {s: sorted(values) for s, values in sorted(expected.items())})
    write_json(export / 'metrics.json', metrics)
    write_json(export / 'normalization.json', {'version': 1, 'unicode': 'NFC', 'case': 'Python Unicode lower',
               'apostrophes': {'’': "'", 'ʼ': "'"}, 'strip_outer_whitespace': True,
               'preserve_diacritics': True, 'max_characters': 128, 'single_word_only': True,
               'unity_parity_verified': False})
    version = run('hfst-lexc', '--version').splitlines()[0]
    manifest = {'schema_version': 1, 'backend': 'hfst', 'scope': 'documented_forms_only',
                'hfst_version': version, 'source_sha256': hashes,
                'grammar_sha256': sha256(grammar_path), 'unknown_policy': 'abstain',
                'morphology': 'restricted_attested_continuations; suffix segmentation is a hypothesis',
                'runtime': 'Linux x86_64 CLI; Android runtime not included',
                'files': {str(p.relative_to(export)): sha256(p) for p in sorted(export.rglob('*'))
                          if p.is_file() and p.name not in {'manifest.json', 'SHA256SUMS'}}}
    write_json(export / 'manifest.json', manifest)
    (export / 'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.relative_to(export)}\n' for p in sorted(export.rglob('*'))
                                             if p.is_file() and p.name != 'SHA256SUMS'), encoding='utf-8')
    return metrics
