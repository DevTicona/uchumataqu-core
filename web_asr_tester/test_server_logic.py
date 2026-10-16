#!/usr/bin/env python3
"""
Test unitario de las funciones de evaluación y métricas de server.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from server import (
    palabra_a_fonemas,
    texto_a_fonemas_completo,
    alinear_secuencias_foneticas,
    calcular_metricas,
    SherpaOnnxManager,
    evaluar_audio_con_modelo
)

def test_pipeline():
    print("--- 1. Probando G2P ---")
    texto = "Tï wiyanichay wakpacha"
    res_g2p = texto_a_fonemas_completo(texto)
    print("Texto:", texto)
    print("Fonemas:", res_g2p["fonemas"])
    assert res_g2p["fonemas"] == ['T', 'II', 'W', 'I', 'Y', 'A', 'N', 'I', 'CH', 'A', 'Y', 'W', 'A', 'K', 'P', 'A', 'CH', 'A']

    print("\n--- 2. Probando Alineación Fonética y PER ---")
    ref = res_g2p["fonemas"]
    # Simular predicción donde falta la 'W'
    hyp = ['T', 'II', 'W', 'I', 'Y', 'A', 'N', 'I', 'CH', 'A', 'Y', 'A', 'K', 'P', 'A', 'CH', 'A']
    metricas = calcular_metricas(ref, hyp, texto)
    print(f"Total Ref: {metricas['total_referencia']}, Total Hyp: {metricas['total_hipotesis']}")
    print(f"Hits: {metricas['hits']}, Subs: {metricas['substitutions']}, Dels: {metricas['deletions']}, Ins: {metricas['insertions']}")
    print(f"PER: {metricas['per']}%, Precisión: {metricas['precision_fonetica']}%, Resultado 85%: {metricas['resultado_85']}")
    assert metricas['deletions'] == 1
    assert metricas['hits'] == 17
    assert metricas['resultado_85'] == "APROBADO"

    print("\n--- 3. Probando Inferencia Real con Archivo de Pedro ---")
    sherpa_mgr = SherpaOnnxManager()
    audio_path = "/home/primo/proyecto-grado/ASR/audios_oraciones/pedro/O_002_01.wav"
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    resultado = evaluar_audio_con_modelo(
        audio_bytes=audio_bytes,
        extension="wav",
        texto_objetivo="Tï wiyanichay wakpacha",
        sherpa_mgr=sherpa_mgr
    )

    print("Salida cruda del modelo:", resultado["salida_cruda_modelo"])
    print("Tokens predichos:", resultado["fonemas_predichos"])
    print("PER real:", resultado["metricas"]["per"], "%")
    print("Precisión:", resultado["metricas"]["precision_fonetica"], "%")
    print("Aprobado >= 85%:", resultado["metricas"]["pasa_85"])
    print("Duración audio:", resultado["diagnostico_audio"]["duracion_s"], "s")
    print("Silencio inicio:", resultado["diagnostico_audio"]["silencio_inicio_ms"], "ms")
    print("Silencio fin:", resultado["diagnostico_audio"]["silencio_fin_ms"], "ms")

    print("\n✅ TODAS LAS PRUEBAS DE LÓGICA PASARON CON ÉXITO")

if __name__ == "__main__":
    test_pipeline()
