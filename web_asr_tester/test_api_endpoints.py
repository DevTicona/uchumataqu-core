#!/usr/bin/env python3
"""
Test de integración de la API REST del servidor ASR INT8.
Levanta el servidor en segundo plano en localhost:8089, prueba todos los endpoints y verifica respuestas.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import threading

sys.path.insert(0, os.path.dirname(__file__))
from server import ThreadedHTTPServer, ASRRequestHandler, SherpaOnnxManager, CorpusManager

def test_api():
    print("Iniciando servidor de prueba en puerto 8089...")
    sherpa_mgr = SherpaOnnxManager()
    corpus_mgr = CorpusManager()
    ASRRequestHandler.sherpa_mgr = sherpa_mgr
    ASRRequestHandler.corpus_mgr = corpus_mgr

    server = ThreadedHTTPServer(("127.0.0.1", 8089), ASRRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(1)

    base_url = "http://127.0.0.1:8089"

    try:
        # 1. Test GET /
        print("\n[1/6] Testeando GET / (Frontend HTML)...")
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "ASR INT8" in html
            print("  -> OK: HTML servido correctamente.")

        # 2. Test GET /api/info
        print("\n[2/6] Testeando GET /api/info...")
        with urllib.request.urlopen(f"{base_url}/api/info") as resp:
            assert resp.status == 200
            info = json.loads(resp.read().decode("utf-8"))
            assert info["estado"] == "en_linea"
            assert "model.int8.onnx" in info["modelo"]["archivo"]
            print(f"  -> OK: Modelo cargado (Hash: {info['modelo']['sha256'][:16]}...)")

        # 3. Test GET /api/corpus
        print("\n[3/6] Testeando GET /api/corpus...")
        with urllib.request.urlopen(f"{base_url}/api/corpus") as resp:
            assert resp.status == 200
            corpus = json.loads(resp.read().decode("utf-8"))
            assert len(corpus["oraciones"]) > 0
            assert len(corpus["palabras"]) > 0
            print(f"  -> OK: Corpus con {len(corpus['oraciones'])} oraciones y {len(corpus['palabras'])} palabras.")

        # 4. Test POST /api/g2p
        print("\n[4/6] Testeando POST /api/g2p...")
        payload_g2p = json.dumps({"texto": "Tï wiyanichay wakpacha"}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/g2p",
            data=payload_g2p,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res_g2p = json.loads(resp.read().decode("utf-8"))
            assert res_g2p["fonemas"] == ['T', 'II', 'W', 'I', 'Y', 'A', 'N', 'I', 'CH', 'A', 'Y', 'W', 'A', 'K', 'P', 'A', 'CH', 'A']
            print("  -> OK: G2P generó 18 fonemas canónicos esperados.")

        # 5. Test POST /api/evaluate con audio real
        print("\n[5/6] Testeando POST /api/evaluate con audio real (Pedro O_002_01.wav)...")
        audio_path = "/home/primo/proyecto-grado/ASR/audios_oraciones/pedro/O_002_01.wav"
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        import base64
        payload_eval = json.dumps({
            "texto_objetivo": "Tï wiyanichay wakpacha",
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "formato": "wav"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/api/evaluate",
            data=payload_eval,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res_eval = json.loads(resp.read().decode("utf-8"))
            met = res_eval["metricas"]
            diag = res_eval["diagnostico_audio"]
            assert met["pasa_85"] is True
            assert met["resultado_85"] == "APROBADO"
            assert met["hits"] in (17, 18)
            assert met["deletions"] in (0, 1)
            assert met["per"] <= 5.56
            assert diag["es_16k_mono"] is True
            print(f"  -> OK: Inferencia INT8 completada exitosamente.")
            print(f"     Salida cruda: {res_eval['salida_cruda_modelo']}")
            print(f"     PER: {met['per']}%, Precisión: {met['precision_fonetica']}% (Aprobado: {met['pasa_85']})")
            print(f"     Duración: {diag['duracion_s']}s, Silencio: ini={diag['silencio_inicio_ms']}ms, fin={diag['silencio_fin_ms']}ms")

        # 6. Test POST /api/export_csv
        print("\n[6/6] Testeando POST /api/export_csv...")
        payload_csv = json.dumps({"pruebas": [res_eval]}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/export_csv",
            data=payload_csv,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            csv_text = resp.read().decode("utf-8")
            assert "objetivo_uch" in csv_text
            assert "Tï wiyanichay wakpacha" in csv_text
            print("  -> OK: Reporte CSV generado y validado.")

        print("\n🎉 TODOS LOS 6 ENDPOINTS Y FLUJOS DE LA API FUNCIONAN AL 100%")

    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    test_api()
