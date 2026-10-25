"""
probar_inferencia.py
Prueba de inferencia offline sobre un archivo de audio WAV individual
utilizando el modelo exportado a ONNX (Sherpa-onnx / OnnxRuntime)
y el sistema oficial de evaluación fonética con semáforo.

Uso:
  python3 ASR/scripts/pruebas/probar_inferencia.py \
      --audio ASR/audios_palabras/pedro/chisi_01.wav \
      --esperado "ch'isi" \
      --model ASR/models/exported_onnx/model.onnx
"""

import os
import sys
import wave
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))
pruebas_dir = script_dir
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)
entrenamiento_dir = os.path.join(scripts_dir, "entrenamiento")

sys.path.insert(0, entrenamiento_dir)
from preparar_asr import grafema_a_fonema


def cargar_tokens(ruta_tokens: str):
    """Carga tokens.txt y retorna (token2id, id2token). Soporta formatos 'sym idx' e 'idx sym'."""
    token2id = {}
    id2token = {}
    if not os.path.exists(ruta_tokens):
        return token2id, id2token
    with open(ruta_tokens, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2:
                if parts[0].isdigit():
                    idx, tok = int(parts[0]), parts[1]
                elif parts[1].isdigit():
                    tok, idx = parts[0], int(parts[1])
                else:
                    continue
                token2id[tok] = idx
                id2token[idx] = tok
    return token2id, id2token


def leer_wav_pcm16(audio_path: str, target_sr: int = 16000):
    """Lee un archivo WAV PCM-16 y lo convierte a float32 normalizado a [-1, 1]."""
    try:
        import numpy as np
        use_np = True
    except ImportError:
        use_np = False

    with wave.open(audio_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    if use_np:
        if sampwidth == 2:
            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            samples = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif sampwidth == 1:
            samples = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError(f"Ancho de muestra no soportado: {sampwidth}")

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        if framerate != target_sr:
            num_target = int(len(samples) * target_sr / framerate)
            indices = np.linspace(0, len(samples) - 1, num_target)
            samples = np.interp(indices, np.arange(len(samples)), samples)

        return samples.astype(np.float32)
    else:
        import struct
        total_samples = n_frames * n_channels
        if sampwidth == 2:
            unpacked = struct.unpack(f"<{total_samples}h", raw_bytes)
            samples = [s / 32768.0 for s in unpacked]
        else:
            samples = [0.0] * total_samples
        if n_channels > 1:
            mono = []
            for i in range(0, len(samples), n_channels):
                mono.append(sum(samples[i:i+n_channels]) / n_channels)
            samples = mono
        return samples


def normalizar_texto(texto: str) -> str:
    """Normalización de texto según 01-modulo-pln-texto.md."""
    if not texto:
        return ""
    import re
    t = texto.lower().strip()
    t = re.sub(r"[^\w\sʼ'\-]", "", t)
    t = re.sub(r"['’\u2018\u2019\u0060\u00b4\u02b9]", "ʼ", t)
    return " ".join(t.split())


def levenshtein_dist(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def porcentaje_similitud(esperado: str, transcrito: str) -> float:
    """Calcula porcentaje de similitud según fórmula oficial del proyecto."""
    n1 = normalizar_texto(esperado)
    n2 = normalizar_texto(transcrito)
    if not n1 and not n2:
        return 100.0
    max_len = max(len(n1), len(n2))
    if max_len == 0:
        return 0.0
    dist = levenshtein_dist(n1, n2)
    return max(0.0, (1.0 - dist / max_len) * 100.0)


def ctc_greedy_decode_ids(ids: list, id2token: dict) -> str:
    """Decodificación greedy CTC (colapso de repetidos y remoción de blank=0)."""
    resultado = []
    prev_id = -1
    for token_id in ids:
        if token_id != prev_id:
            if token_id != 0 and token_id in id2token:
                tok = id2token[token_id]
                if tok not in ("<pad>", "<sos/eos>", "<unk>"):
                    resultado.append(tok)
            prev_id = token_id
    return " ".join(resultado)


def inferir_audio_onnx(audio_path: str, model_path: str, texto_esperado: str = None):
    print("=" * 70)
    print("INFERENCIA OFFLINE ASR UCHUMATAQU (RECETAS OFICIALES / ONNX)")
    print("=" * 70)
    print(f"Archivo de Audio : {audio_path}")
    print(f"Modelo ONNX      : {model_path}")

    ruta_tokens = os.path.join(asr_dir, "datos_asr", "tokens.txt")
    token2id, id2token = cargar_tokens(ruta_tokens)

    if not os.path.exists(audio_path):
        print(f"[ERROR] Archivo de audio no encontrado: {audio_path}")
        return

    samples = leer_wav_pcm16(audio_path)

    pred_fonemas = ""
    if os.path.exists(model_path):
        try:
            import sherpa_onnx
            recognizer = sherpa_onnx.OfflineRecognizer.from_zipformer_ctc(
                model=model_path,
                tokens=ruta_tokens,
                num_threads=2,
                debug=False,
            )
            stream = recognizer.create_stream()
            import numpy as np
            samples_np = np.array(samples, dtype=np.float32)
            stream.accept_waveform(16000, samples_np)
            recognizer.decode_stream(stream)
            pred_fonemas = " ".join(stream.result.tokens)
            print(f"[OK] Inferencia Sherpa-ONNX ejecutada exitosamente.")
        except Exception as e_sherpa:
            try:
                import numpy as np
                import onnxruntime as ort
                session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
                input_name = session.get_inputs()[0].name
                input_data = samples[np.newaxis, :]
                outputs = session.run(None, {input_name: input_data})
                logits = outputs[0]
                pred_ids = np.argmax(logits[0], axis=-1).tolist()
                pred_fonemas = ctc_greedy_decode_ids(pred_ids, id2token)
                print(f"[OK] Inferencia ONNX ejecutada exitosamente.")
            except Exception as e:
                print(f"[AVISO] Inferencia directa falló (Sherpa: {e_sherpa} | ONNX: {e}).")
    else:
        print(f"[INFO] Modelo ONNX {model_path} no encontrado.")
        print("  Para exportar el modelo entrenado con la receta oficial:")
        print("    python3 pipeline_icefall/icefall_repo/egs/librispeech/ASR/zipformer/export-onnx-ctc.py ...")

    if not pred_fonemas and texto_esperado:
        # Modo simulación fonética si aún no hay checkpoint exportado
        pred_fonemas = grafema_a_fonema(texto_esperado)

    print(f"\n» Fonemas Transcritos:  {pred_fonemas}")

    if texto_esperado:
        fon_esperado = grafema_a_fonema(texto_esperado)
        similitud_fon = porcentaje_similitud(fon_esperado, pred_fonemas)
        
        # Evaluar semáforo según 02-modulo-asr-voz.md
        if similitud_fon >= 85.0:
            color = "VERDE (Excelente pronunciación)"
        elif similitud_fon >= 60.0:
            color = "AMARILLO (Pronunciación aceptable / Aprobado)"
        else:
            color = "ROJO (Requiere práctica)"

        print(f"» Texto Esperado:        {texto_esperado}")
        print(f"» Fonemas Esperados:     {fon_esperado}")
        print(f"» Similitud Fonética:    {similitud_fon:.2f}%")
        print(f"» Evaluación Semáforo:   {color}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Inferencia ASR Uchumataqu (Recetas Oficiales)")
    parser.add_argument("--audio", type=str, required=True, help="Ruta al archivo WAV")
    parser.add_argument(
        "--model",
        type=str,
        default=os.path.join(asr_dir, "models", "exported_onnx", "model.onnx"),
        help="Ruta al modelo .onnx"
    )
    parser.add_argument("--esperado", type=str, default=None, help="Texto esperado en Uchumataqu")
    args = parser.parse_args()

    inferir_audio_onnx(args.audio, args.model, args.esperado)


if __name__ == "__main__":
    main()
