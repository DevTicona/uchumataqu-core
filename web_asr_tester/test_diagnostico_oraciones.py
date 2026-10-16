#!/usr/bin/env python3
"""
Test de diagnóstico con oraciones compuestas y evaluación de coarticulación / elisión.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from server import SherpaOnnxManager, evaluar_audio_con_modelo

def test_oraciones_compuestas():
    sherpa_mgr = SherpaOnnxManager()

    casos = [
        ("Thuñi seschay sitsñi", "/home/primo/proyecto-grado/ASR/audios_oraciones/pedro/O_003_01.wav"),
        ("Wilk thö lorenzo", "/home/primo/proyecto-grado/ASR/audios_oraciones/pedro/O_004_01.wav"),
        ("Chhuñi pichuchay tï watha irohito urus", "/home/primo/proyecto-grado/ASR/audios_oraciones/pedro/O_018_01.wav")
    ]

    for texto, ruta in casos:
        print(f"\n=======================================================")
        print(f"Probando: '{texto}'")
        print(f"Archivo: {ruta}")
        with open(ruta, "rb") as f:
            bytes_audio = f.read()

        res = evaluar_audio_con_modelo(bytes_audio, "wav", texto, sherpa_mgr)
        met = res["metricas"]
        print(f"Predicción Cruda:   {res['salida_cruda_modelo']}")
        print(f"Fonemas Esperados:  {' '.join(res['fonemas_esperados'])}")
        print(f"Fonemas Predichos:  {' '.join(res['fonemas_predichos'])}")
        print(f"Aciertos: {met['hits']} / {met['total_referencia']} | Subs: {met['substitutions']} | Dels: {met['deletions']} | Ins: {met['insertions']}")
        print(f"PER: {met['per']}% | Precisión: {met['precision_fonetica']}% | Aceptación 85%: {met['resultado_85']}")
        print("Discrepancias explicadas:")
        for err in met["errores_detallados"]:
            print(f"  - {err['mensaje']}")

if __name__ == "__main__":
    test_oraciones_compuestas()
