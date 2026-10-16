import shutil
import unicodedata

import pytest

from uchumataqu_hfst.build import analysis
from uchumataqu_hfst.data import ROOT, SOURCES, normalize, read_json, sha256
from uchumataqu_hfst.native import lookup, run
from uchumataqu_hfst.runtime import Analyzer


@pytest.fixture(scope='module')
def analyzer():
    return Analyzer()


@pytest.mark.parametrize(('surface', 'lemma', 'segments'), [
    ('Achasinaka', 'achasi', ['achasi', 'naka']),
    ('Achichay', 'achichay', ['achichay']),
    ('Chhaqpinichay', 'chhaq', ['chhaq', 'pini', 'chay']),
    ('Sitsñinakachay', 'sitsñi', ['sitsñi', 'naka', 'chay']),
    ('Anapini', 'ana', ['ana', 'pini']),
    ('Ch’atschaypini', "ch'atschay", ["ch'atschay", 'pini']),
])
def test_documented_analysis(analyzer, surface, lemma, segments):
    result = analyzer.analyze(surface)
    assert result['status'] == 'analyzed'
    record = result['analyses'][0]
    assert record['lemma'] == lemma
    assert record['segments'] == segments
    assert record['features'] == {}  # No inferir rasgos validados a partir de traducciones.


@pytest.mark.parametrize('text', ['achasinakanaka', 'achasipinichay', 'zzzz', 'achichaynaka', 'chhaqchaypini'])
def test_no_unlicensed_productivity(analyzer, text):
    assert analyzer.analyze(text)['status'] == 'unknown'


@pytest.mark.parametrize('text', ['', ' ', 'achasi\notra', 'achasi\totra', '<achasi>',
                                'achasi otra', 'a' * 129, '123', '😀'])
def test_unsupported_input(analyzer, text):
    assert analyzer.analyze(text)['status'] == 'unsupported_input'


def test_unicode_and_diacritics(analyzer):
    assert normalize(' CHʼATSCHAY ') == "ch'atschay"
    assert analyzer.analyze(unicodedata.normalize('NFD', 'PÄKU'))['analyses'][0]['surface'] == 'päku'
    assert normalize('päku') != normalize('paku')


def test_comparison_does_not_rewrite_response(analyzer):
    assert analyzer.compare('Achasi', 'Achasinaka')['diagnosis'] == 'documented_form_difference'
    assert analyzer.compare('Achasi', 'Achichay')['diagnosis'] == 'different_word'
    assert analyzer.compare('Achasi', 'achasi')['diagnosis'] == 'match'
    assert analyzer.compare('Achasi', 'achazi')['diagnosis'] == 'undetermined'
    assert analyzer.compare('Achasi', 'lorenzo')['diagnosis'] == 'undetermined'


def test_all_paths_are_documented():
    records = read_json(ROOT / 'shared/annotated/analyses.json')
    # La gramática es acíclica. Limitar a N+1 permite detectar rutas adicionales.
    paths = run('hfst-fst2strings', '-n', str(len(records) + 1), ROOT / 'build/generator.hfst')
    assert set(paths.splitlines()) == {analysis(r) + ':' + r['surface'] for r in records}


def test_snapshot_and_package_integrity():
    for source in SOURCES:
        assert sha256(ROOT.parent / source) == sha256(ROOT / 'shared/raw' / source)
    package = ROOT / 'export/pln-hfst-v1'
    for line in (package / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split('  ', 1)
        assert sha256(package / filename) == digest


def test_corrupt_package_is_technical_failure(tmp_path):
    shutil.copytree(ROOT / 'export/pln-hfst-v1', tmp_path / 'package')
    (tmp_path / 'package/analyses.json').write_text('[]')
    with pytest.raises(ValueError, match='Integridad'):
        Analyzer(tmp_path / 'package')


def test_ambiguous_analyses_are_preserved(tmp_path):
    grammar = tmp_path / 'ambiguous.lexc'
    grammar.write_text('LEXICON Root\na:forma # ;\nb:forma # ;\n')
    generator, model = tmp_path / 'g.hfst', tmp_path / 'a.hfst'
    run('hfst-lexc', '--quiet', grammar, '-o', generator)
    run('hfst-invert', '-i', generator, '-o', model)
    assert lookup(model, ['forma']) == {'forma': {'a', 'b'}}


def test_primary_coverage_excludes_only_multiword_expressions():
    audit = read_json(ROOT / 'reports/data-audit.json')
    assert audit['record_sources']['palabras.json'] == 317
    assert len(audit['excluded']) == 4
    assert all(' ' in record['surface'] for record in audit['excluded'])
