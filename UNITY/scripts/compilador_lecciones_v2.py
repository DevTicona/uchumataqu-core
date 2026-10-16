"""
compilador_lecciones_v2.py
Re-exportador y ejecutor de retrocompatibilidad hacia generador_corpus.compilador_lecciones_v2.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERADOR_DIR = os.path.join(SCRIPT_DIR, "generador_corpus")

if GENERADOR_DIR not in sys.path:
    sys.path.insert(0, GENERADOR_DIR)

from compilador_lecciones_v2 import (
    compilar_lecciones_curriculares_v2,
    compilar_y_guardar_v2,
    CATALOGO_22
)

if __name__ == "__main__":
    compilar_y_guardar_v2()
