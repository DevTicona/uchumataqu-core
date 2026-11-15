"""
runtime.py
Motor de consulta y análisis morfológico HFST en tiempo de ejecución.
Implementa una política de abstención lingüística honesta:
  - Solo analiza formas documentadas con atestación léxica.
  - Verifica la integridad criptográfica (SHA-256) de los modelos compilados.
  - Compara respuestas de estudiantes contra objetivos pedagógicos distinguiendo:
      * 'match': Coincidencia exacta de forma.
      * 'documented_form_difference': Variación morfológica documentada dentro de la misma familia.
      * 'different_word': Entrada diferente documentada.
      * 'unknown' / 'undetermined': Forma no documentada o no resoluble.
"""
from .build import analysis
from .data import ROOT, normalize, read_json, sha256, supported
from .native import lookup


class Analyzer:
    """Analizador morfológico HFST con índice en memoria y transductor optimizado (.hfstol)."""

    def __init__(self, package=None):
        self.package = package or ROOT / 'export/pln-hfst-v1'
        manifest = read_json(self.package / 'manifest.json')
        for name in ('analyses.json', 'analyzer.hfstol'):
            if sha256(self.package / name) != manifest['files'][name]:
                raise ValueError(f'Integridad del paquete incorrecta: {name}')
        self.records = {analysis(r): r for r in read_json(self.package / 'analyses.json')}

    def analyze(self, text: str) -> dict:
        """
        Analiza una palabra en Uchumataqu retornando su lema, categoría gramatical y sufijos.
        Retorna status: 'analyzed', 'ambiguous', 'unknown' o 'unsupported_input'.
        """
        surface = normalize(text)
        result = {'input': text, 'normalized': surface, 'engine': 'hfst', 'analyses': []}
        if not supported(surface):
            return {**result, 'status': 'unsupported_input'}
        values = lookup(self.package / 'analyzer.hfstol', [surface])[surface]
        result['analyses'] = [self.records[value] for value in sorted(values)]
        return {**result, 'status': 'unknown' if not values else 'ambiguous' if len(values) > 1 else 'analyzed'}

    def compare(self, target: str, response: str) -> dict:
        """
        Diagnostica pedagógicamente la respuesta de un estudiante frente a una forma esperada.
        """
        expected, actual = self.analyze(target), self.analyze(response)
        result = {'target': expected, 'response': actual, 'diagnosis': 'undetermined'}
        if expected['status'] != 'analyzed' or actual['status'] != 'analyzed':
            return result
        left, right = expected['analyses'][0], actual['analyses'][0]
        if left['translation'] is None or right['translation'] is None:
            return result
        if left['surface'] == right['surface']:
            result.update(diagnosis='match', message='La escritura coincide con la forma solicitada.')
        elif left['family_id'] == right['family_id']:
            result.update(diagnosis='documented_form_difference',
                          message=f"La fuente registra «{right['original']}» como «{right['translation']}»; "
                                  f"se solicita «{left['original']}» («{left['translation']}»).",
                          note='La relación está documentada; los rasgos gramaticales requieren revisión.')
        else:
            result.update(diagnosis='different_word', message='La respuesta corresponde a otra entrada documentada.')
        return result
