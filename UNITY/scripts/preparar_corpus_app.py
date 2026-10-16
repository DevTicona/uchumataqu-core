#!/usr/bin/env python3
"""
preparar_corpus_app.py
Punto de entrada y wrapper de retrocompatibilidad hacia generador_corpus.preparar_corpus_app.
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERADOR_DIR = os.path.join(SCRIPT_DIR, "generador_corpus")

if GENERADOR_DIR not in sys.path:
    sys.path.insert(0, GENERADOR_DIR)

from preparar_corpus_app import main

if __name__ == "__main__":
    main()
