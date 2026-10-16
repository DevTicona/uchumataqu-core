#!/usr/bin/env python3
"""
test_compilador_lecciones.py
Runner y wrapper de retrocompatibilidad hacia generador_corpus.test_compilador_lecciones.
"""
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERADOR_DIR = os.path.join(SCRIPT_DIR, "generador_corpus")

if GENERADOR_DIR not in sys.path:
    sys.path.insert(0, GENERADOR_DIR)

from test_compilador_lecciones import TestCompiladorLecciones

if __name__ == "__main__":
    unittest.main()
