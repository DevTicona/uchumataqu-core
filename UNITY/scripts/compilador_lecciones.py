"""
compilador_lecciones.py
Re-exportador y puente de retrocompatibilidad hacia generador_corpus.compilador_lecciones.
"""
import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERADOR_DIR = os.path.join(SCRIPT_DIR, "generador_corpus")

if GENERADOR_DIR not in sys.path:
    sys.path.insert(0, GENERADOR_DIR)

_target = os.path.join(GENERADOR_DIR, "compilador_lecciones.py")
_spec = importlib.util.spec_from_file_location("generador_corpus_compilador", _target)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v
