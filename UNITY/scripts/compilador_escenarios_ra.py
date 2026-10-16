"""
compilador_escenarios_ra.py
Re-exportador y ejecutor hacia generador_corpus.compilador_escenarios_ra.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERADOR_DIR = os.path.join(SCRIPT_DIR, "generador_corpus")

if GENERADOR_DIR not in sys.path:
    sys.path.insert(0, GENERADOR_DIR)

from compilador_escenarios_ra import (
    compilar_escenarios_ra_v2,
    compilar_y_guardar_escenarios_ra_v2
)

if __name__ == "__main__":
    compilar_y_guardar_escenarios_ra_v2()
