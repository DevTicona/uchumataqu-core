#!/usr/bin/env python3
"""
Servidor Web de Pruebas y Diagnóstico Fonético en Tiempo Real para ASR.
Soporta:
  - Selección de Múltiples Modelos:
      1. Scratch INT8 (Zipformer 100 épocas cuantizado - 72 MB)
      2. Scratch FP32 (Zipformer 100 épocas Float32 Pesado - 262 MB)
      3. Fine-Tuning INT8 (Zipformer multilingüe adaptado 50 épocas - 70 MB)
      4. Fine-Tuning FP32 (Zipformer multilingüe Float32 Pesado - 250 MB)
  - Modos de Decodificación:
      1. greedy_search: Decodificación CTC pura frame a frame (argmax acústico)
      2. con_restricciones: Decodificación guiada con el léxico pedagógico cerrado (recupera fonemas elididos en oraciones)
  - Inferencia en tiempo real (Sherpa-ONNX)
  - Transcodificación automática de audio con ffmpeg (WebM, Opus, M4A, WAV, MP3, etc.)
  - Motor lingüístico G2P canónico (Uchumataqu, 38 fonemas)
  - Alineación fonética Needleman-Wunsch / Levenshtein
  - Métricas completas: PER, WER, CER, Aciertos, Sustituciones, Eliminaciones, Inserciones
  - Diagnóstico acústico: 16 kHz Mono, duración, silencios inicio/fin, clipping
  - Biblioteca de corpus y exportación de informes CSV / Markdown
"""

import os
import sys
import json
import re
import wave
import struct
import math
import hashlib
import tempfile
import subprocess
import socket
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

# Importar sherpa_onnx
try:
    import sherpa_onnx
except ImportError:
    print("ERROR CRÍTICO: sherpa_onnx no está instalado en el entorno de Python.")
    sys.exit(1)

# Rutas del proyecto y modelos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PALABRAS_JSON = os.path.join(BASE_DIR, "UNITY", "datos_app", "palabras.json")
ORACIONES_JSON = os.path.join(BASE_DIR, "UNITY", "datos_app", "oraciones.json")

DIR_AUDIOS_ORACIONES = os.path.join(BASE_DIR, "ASR", "audios_oraciones")
DIR_AUDIOS_PALABRAS = os.path.join(BASE_DIR, "ASR", "audios_palabras")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

DEFAULT_MODEL_ID = "scratch_int8"

# Catálogo oficial de modelos disponibles
MODELS_CATALOG = {
    "scratch_int8": {
        "id": "scratch_int8",
        "nombre": "Entrenamiento desde Cero Uchumataqu (INT8 - 72 MB)",
        "descripcion": "Zipformer CTC entrenado 100 épocas en Uchumataqu. Modelo de producción desplegado en móvil y Unity (INT8).",
        "model_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "model.int8.onnx"),
        "tokens_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "tokens.txt"),
        "lexicon_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "lexicon.txt"),
        "origen": "Scratch v2 (Época 100)",
        "precision": "INT8 Dinámico",
        "recomendado": True
    },
    "scratch_fp32": {
        "id": "scratch_fp32",
        "nombre": "Entrenamiento desde Cero Uchumataqu (FP32 Pesado - 262 MB)",
        "descripcion": "Zipformer CTC entrenado 100 épocas en Uchumataqu. Precisión completa Float32.",
        "model_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "model.onnx"),
        "tokens_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "tokens.txt"),
        "lexicon_path": os.path.join(BASE_DIR, "ASR", "models", "exported_onnx", "lexicon.txt"),
        "origen": "Scratch v2 (Época 100)",
        "precision": "Float32 Completo",
        "recomendado": False
    },
    "finetune_int8": {
        "id": "finetune_int8",
        "nombre": "Fine-Tuning Multilingüe (INT8 - 70 MB)",
        "descripcion": "Zipformer adaptado desde checkpoint preentrenado con 50 épocas de fine-tuning. INT8.",
        "model_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "model.int8.onnx"),
        "tokens_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "tokens.txt"),
        "lexicon_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "lexicon.txt"),
        "origen": "Fine-Tuning v2 (Época 50)",
        "precision": "INT8 Dinámico",
        "recomendado": False
    },
    "finetune_fp32": {
        "id": "finetune_fp32",
        "nombre": "Fine-Tuning Multilingüe (FP32 Pesado - 250 MB)",
        "descripcion": "Zipformer adaptado desde checkpoint preentrenado con 50 épocas de fine-tuning. Float32.",
        "model_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "model.onnx"),
        "tokens_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "tokens.txt"),
        "lexicon_path": os.path.join(BASE_DIR, "ASR", "models", "exported_finetune", "lexicon.txt"),
        "origen": "Fine-Tuning v2 (Época 50)",
        "precision": "Float32 Completo",
        "recomendado": False
    }
}

# ===========================================================================
# 1. INVENTARIO FONOLÓGICO Y REGLAS G2P (Grafema a Fonema Canónico)
# ===========================================================================

FONEMAS_CANONICOS = {
    "A", "AA", "E", "EE", "I", "II", "O", "OO", "U", "UU",
    "P", "T", "K", "Q", "M", "N", "R", "S", "X", "J", "L", "LL", "Y", "W",
    "TS", "CH", "SH", "NY",
    "PH", "TH", "KH", "QH", "CHH",
    "P_EJ", "T_EJ", "K_EJ", "Q_EJ", "CH_EJ"
}

REGLAS_G2P_COMPILADAS = [
    # Nivel 1 — Trígrafos
    (re.compile(r"chʼ"), " CH_EJ "),   # IPA: t͡ʃʼ
    (re.compile(r"chh"), " CHH "),      # IPA: t͡ʃʰ

    # Nivel 2 — Dígrafos aspirados / eyectivos
    (re.compile(r"ph"), " PH "),        # IPA: pʰ
    (re.compile(r"th"), " TH "),        # IPA: tʰ
    (re.compile(r"kh"), " KH "),        # IPA: kʰ
    (re.compile(r"qh"), " QH "),        # IPA: qʰ
    (re.compile(r"pʼ"), " P_EJ "),      # IPA: pʼ
    (re.compile(r"tʼ"), " T_EJ "),      # IPA: tʼ
    (re.compile(r"kʼ"), " K_EJ "),      # IPA: kʼ
    (re.compile(r"qʼ"), " Q_EJ "),      # IPA: qʼ
    (re.compile(r"ch"), " CH "),        # IPA: t͡ʃ

    # Nivel 3 — Secuencias fonotácticas combinadas
    (re.compile(r"tk"), " T K "),
    (re.compile(r"tsh"), " T SH "),

    # Nivel 4 — Dígrafos restantes
    (re.compile(r"ts"), " TS "),        # IPA: t͡s
    (re.compile(r"ll|ly|lʼ"), " LL "),  # IPA: ʎ
    (re.compile(r"ñ"), " NY "),         # IPA: ɲ
    (re.compile(r"sh"), " SH "),        # IPA: ʃ

    # Nivel 5 — Vocales largas nativas con diéresis y variantes ortográficas
    (re.compile(r"ä|aa|ā|â|a:"), " AA "),
    (re.compile(r"ë|ee|ē|ê|e:"), " EE "),
    (re.compile(r"ï|ii|ī|î|i:"), " II "),
    (re.compile(r"ö|oo|ō|ô|o:"), " OO "),
    (re.compile(r"ü|uu|ū|û|u:"), " UU "),

    # Nivel 6A — Adaptaciones técnicas de préstamos del castellano
    (re.compile(r"c"), " K "),          # /k/ velar (ej. Carlos -> K A R L O S)
    (re.compile(r"d"), " T "),          # /t/ sorda aproxima /d/ sonora (ej. Pedro -> P E T R O)
    (re.compile(r"v"), " W "),          # /w/ aproxima /v/
    (re.compile(r"b"), " P "),          # /p/ aproxima /b/
    (re.compile(r"h"), ""),            # 'h' muda en préstamos (ej. Irohito -> I R O I T O)

    # Nivel 6B — Vocales castellanas acentuadas en préstamos (vocales cortas)
    (re.compile(r"á"), " A "),
    (re.compile(r"é"), " E "),
    (re.compile(r"í"), " I "),          # ej. María -> M A R I A
    (re.compile(r"ó"), " O "),
    (re.compile(r"ú"), " U "),

    # Nivel 7 — Grafemas simples restantes
    (re.compile(r"p"), " P "),
    (re.compile(r"t"), " T "),
    (re.compile(r"k"), " K "),
    (re.compile(r"q"), " Q "),
    (re.compile(r"s|z"), " S "),        # z es variante gráfica de s
    (re.compile(r"x"), " X "),          # x nativa = /χ/ uvular
    (re.compile(r"j"), " J "),          # j nativa = /x/ velar
    (re.compile(r"m"), " M "),
    (re.compile(r"n"), " N "),
    (re.compile(r"r"), " R "),
    (re.compile(r"l"), " L "),
    (re.compile(r"y"), " Y "),          # semivocal /j/
    (re.compile(r"w"), " W "),
    (re.compile(r"a"), " A "),
    (re.compile(r"e"), " E "),
    (re.compile(r"i"), " I "),
    (re.compile(r"o"), " O "),
    (re.compile(r"u"), " U "),
]

def normalizar_apostrofes(texto: str) -> str:
    """Normaliza variantes tipográficas de apóstrofe al glifo canónico U+02BC (ʼ)."""
    return re.sub(r"['’\u2018\u2019\u0060\u00b4\u02b9]", "ʼ", texto)

def palabra_a_fonemas(palabra: str) -> list:
    """Convierte una sola palabra a lista de fonemas canónicos."""
    limpia = normalizar_apostrofes(palabra.lower().strip())
    limpia = re.sub(r"[¿?¡!.,;:\-_()\"\'/]", "", limpia)
    if not limpia:
        return []

    for patron, reemplazo in REGLAS_G2P_COMPILADAS:
        limpia = patron.sub(reemplazo, limpia)

    fonemas = [f for f in limpia.split() if f]
    return fonemas

def texto_a_fonemas_completo(texto: str):
    """
    Convierte una oración o frase a:
    1. Lista plana de fonemas concatenados
    2. Estructura por palabras para visualización
    """
    palabras = texto.strip().split()
    desglose_palabras = []
    fonemas_totales = []

    for p in palabras:
        f_palabra = palabra_a_fonemas(p)
        if f_palabra:
            desglose_palabras.append({
                "palabra": p,
                "fonemas": f_palabra
            })
            fonemas_totales.extend(f_palabra)

    return {
        "fonemas": fonemas_totales,
        "cadena_fonemas": "".join(fonemas_totales),
        "desglose": desglose_palabras
    }

# Mapeo fonema canónico -> grafema natural Uchumataqu para reconstrucción de audio repetido
FONEMA_A_UCHUMATAQU = {
    # Vocales cortas
    "A": "a", "E": "e", "I": "i", "O": "o", "U": "u",
    # Vocales largas nativas (ortografía pedagógica con diéresis)
    "AA": "ä", "EE": "ë", "II": "ï", "OO": "ö", "UU": "ü",
    # Consonantes simples
    "P": "p", "T": "t", "K": "k", "Q": "q",
    "M": "m", "N": "n", "R": "r", "S": "s", "X": "x", "J": "j",
    "L": "l", "LL": "ll", "Y": "y", "W": "w",
    # Dígrafos
    "TS": "ts", "CH": "ch", "SH": "sh", "NY": "ñ",
    # Aspiradas
    "PH": "ph", "TH": "th", "KH": "kh", "QH": "qh", "CHH": "chh",
    # Eyectivas
    "P_EJ": "pʼ", "T_EJ": "tʼ", "K_EJ": "kʼ", "Q_EJ": "qʼ", "CH_EJ": "chʼ",
}

def reconstruir_texto_repetido(fonemas_predichos: list, texto_objetivo: str = "", alineacion: list = None) -> str:
    """
    Reconstruye el texto real emitido por el usuario en ortografía Uchumataqu legible,
    respetando los espacios y límites de palabras si existe un texto objetivo.
    """
    if not fonemas_predichos:
        return "(sin audio reconocido)"
    if not texto_objetivo or not alineacion:
        return "".join(FONEMA_A_UCHUMATAQU.get(f, f.lower()) for f in fonemas_predichos)

    desglose = texto_a_fonemas_completo(texto_objetivo).get("desglose", [])
    if not desglose:
        return "".join(FONEMA_A_UCHUMATAQU.get(f, f.lower()) for f in fonemas_predichos)

    palabras = [d["palabra"] for d in desglose]
    fonemas_por_palabra = [d["fonemas"] for d in desglose]

    idx_a_palabra = []
    for p_idx, f_list in enumerate(fonemas_por_palabra):
        for _ in f_list:
            idx_a_palabra.append(p_idx)

    palabras_reconstruidas = [[] for _ in palabras]
    palabra_actual = 0
    ref_idx = 0

    for step in alineacion:
        t = step["tipo"]
        if t in ("match", "substitution"):
            if ref_idx < len(idx_a_palabra):
                palabra_actual = idx_a_palabra[ref_idx]
            palabras_reconstruidas[palabra_actual].append(step["predicho"])
            ref_idx += 1
        elif t == "deletion":
            if ref_idx < len(idx_a_palabra):
                palabra_actual = idx_a_palabra[ref_idx]
            ref_idx += 1
        elif t == "insertion":
            palabras_reconstruidas[palabra_actual].append(step["predicho"])

    resultado = []
    for p_idx, f_list in enumerate(palabras_reconstruidas):
        if not f_list:
            continue
        txt = "".join(FONEMA_A_UCHUMATAQU.get(f, f.lower()) for f in f_list)
        if p_idx < len(palabras) and palabras[p_idx] and palabras[p_idx][0].isupper() and txt:
            txt = txt[0].upper() + txt[1:]
        resultado.append(txt)

    texto_final = " ".join(resultado)
    return texto_final if texto_final else "".join(FONEMA_A_UCHUMATAQU.get(f, f.lower()) for f in fonemas_predichos)

# ===========================================================================
# 2. ALGORITMO DE ALINEACIÓN FONÉTICA Y CÁLCULO DE MÉTRICAS (PER, WER, CER)
# ===========================================================================

def alinear_secuencias_foneticas(referencia: list, hipotesis: list):
    """
    Alineación global Needleman-Wunsch / Levenshtein con backtracing.
    """
    n = len(referencia)
    m = len(hipotesis)

    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if referencia[i - 1] == hipotesis[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                costo_sub = dp[i - 1][j - 1] + 1
                costo_del = dp[i - 1][j] + 1
                costo_ins = dp[i][j - 1] + 1
                dp[i][j] = min(costo_sub, costo_del, costo_ins)

    i, j = n, m
    alineacion = []

    while i > 0 or j > 0:
        if i > 0 and j > 0 and referencia[i - 1] == hipotesis[j - 1]:
            alineacion.append({
                "tipo": "match",
                "esperado": referencia[i - 1],
                "predicho": hipotesis[j - 1]
            })
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            alineacion.append({
                "tipo": "substitution",
                "esperado": referencia[i - 1],
                "predicho": hipotesis[j - 1]
            })
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            alineacion.append({
                "tipo": "deletion",
                "esperado": referencia[i - 1],
                "predicho": None
            })
            i -= 1
        else:
            alineacion.append({
                "tipo": "insertion",
                "esperado": None,
                "predicho": hipotesis[j - 1]
            })
            j -= 1

    alineacion.reverse()
    return alineacion

def calcular_metricas(referencia: list, hipotesis: list, texto_ref: str = "", tokens_predichos: list = None):
    """
    Calcula PER, precisión fonética, ratio de acierto simple, CER y umbral del 85 %.
    """
    alineacion = alinear_secuencias_foneticas(referencia, hipotesis)

    hits = sum(1 for item in alineacion if item["tipo"] == "match")
    substitutions = sum(1 for item in alineacion if item["tipo"] == "substitution")
    deletions = sum(1 for item in alineacion if item["tipo"] == "deletion")
    insertions = sum(1 for item in alineacion if item["tipo"] == "insertion")

    n_ref = len(referencia)
    n_hyp = len(hipotesis)

    if n_ref > 0:
        per = ((substitutions + deletions + insertions) / n_ref) * 100.0
        precision_fonetica = max(0.0, 100.0 - per)
        ratio_acierto_simple = (hits / n_ref) * 100.0
    else:
        per = 0.0 if n_hyp == 0 else 100.0
        precision_fonetica = 100.0 if n_hyp == 0 else 0.0
        ratio_acierto_simple = 100.0 if n_hyp == 0 else 0.0

    # Criterio estricto de aprobación: 100% exacto (cero errores fonéticos)
    pasa_100 = (hits == n_ref) and (substitutions == 0) and (deletions == 0) and (insertions == 0) and (n_ref > 0)
    resultado_100 = "APROBADO" if pasa_100 else "RECHAZADO"

    pasa_85_acierto = precision_fonetica >= 85.0
    resultado_85 = "APROBADO" if pasa_85_acierto else "RECHAZADO"

    ref_str = "".join(referencia)
    hyp_str = "".join(hipotesis)
    distancia_cer = dp_levenshtein(ref_str, hyp_str)
    cer = (distancia_cer / len(ref_str) * 100.0) if len(ref_str) > 0 else 0.0

    errores_detallados = []
    idx_ref = 0
    for step in alineacion:
        if step["tipo"] == "deletion":
            errores_detallados.append({
                "tipo": "Eliminación (Omitido)",
                "fonema": step["esperado"],
                "posicion": idx_ref + 1,
                "mensaje": f"El fonema esperado '{step['esperado']}' fue omitido o absorbido por el hablante/modelo."
            })
            idx_ref += 1
        elif step["tipo"] == "substitution":
            errores_detallados.append({
                "tipo": "Sustitución",
                "esperado": step["esperado"],
                "predicho": step["predicho"],
                "posicion": idx_ref + 1,
                "mensaje": f"Se pronunció o decodificó '{step['predicho']}' en lugar de '{step['esperado']}'."
            })
            idx_ref += 1
        elif step["tipo"] == "insertion":
            errores_detallados.append({
                "tipo": "Inserción (Aumentado)",
                "predicho": step["predicho"],
                "mensaje": f"El modelo insertó el fonema extra '{step['predicho']}' no presente en el texto objetivo."
            })
        elif step["tipo"] == "match":
            idx_ref += 1

    return {
        "per": round(per, 2),
        "precision_fonetica": round(precision_fonetica, 2),
        "ratio_acierto_simple": round(ratio_acierto_simple, 2),
        "cer": round(cer, 2),
        "pasa_100": pasa_100,
        "resultado_100": resultado_100,
        "aprobado": pasa_85_acierto,
        "resultado": resultado_85,
        "pasa_85": pasa_85_acierto,
        "resultado_85": resultado_85,
        "total_referencia": n_ref,
        "total_hipotesis": n_hyp,
        "hits": hits,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "alineacion": alineacion,
        "errores_detallados": errores_detallados
    }

def dp_levenshtein(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]

# ===========================================================================
# 3. DIAGNÓSTICO ACÚSTICO DEL ARCHIVO DE AUDIO (16 kHz, Duración, Silencios)
# ===========================================================================

def analizar_archivo_audio_wav(ruta_wav: str):
    try:
        with wave.open(ruta_wav, "rb") as wf:
            canales = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            duracion_s = n_frames / float(sample_rate) if sample_rate > 0 else 0.0

            frames = wf.readframes(n_frames)

            if sample_width == 2 and canales == 1:
                muestras = struct.unpack(f"<{n_frames}h", frames)
                muestras_norm = [s / 32768.0 for s in muestras]
            else:
                muestras_norm = []

        silencio_inicio_ms = 0.0
        silencio_fin_ms = 0.0
        clipping_detectado = False
        rms_db = -100.0

        if muestras_norm:
            tamano_ventana = max(1, int(sample_rate * 0.02))
            umbral_silencio = 0.015

            max_abs = max(abs(m) for m in muestras_norm)
            clipping_detectado = max_abs >= 0.99

            suma_sq = sum(m * m for m in muestras_norm)
            rms = math.sqrt(suma_sq / len(muestras_norm)) if muestras_norm else 0.0
            rms_db = 20 * math.log10(max(rms, 1e-6))

            # Detección silencio inicial
            for idx in range(0, len(muestras_norm), tamano_ventana):
                bloque = muestras_norm[idx:idx + tamano_ventana]
                rms_bloque = math.sqrt(sum(b * b for b in bloque) / len(bloque))
                if rms_bloque > umbral_silencio:
                    silencio_inicio_ms = (idx / float(sample_rate)) * 1000.0
                    break
            else:
                silencio_inicio_ms = duracion_s * 1000.0

            # Detección silencio final
            for idx in range(len(muestras_norm) - tamano_ventana, 0, -tamano_ventana):
                bloque = muestras_norm[idx:idx + tamano_ventana]
                rms_bloque = math.sqrt(sum(b * b for b in bloque) / len(bloque))
                if rms_bloque > umbral_silencio:
                    silencio_fin_ms = ((len(muestras_norm) - (idx + tamano_ventana)) / float(sample_rate)) * 1000.0
                    break
            else:
                silencio_fin_ms = 0.0

        return {
            "valido": True,
            "canales": canales,
            "sample_rate": sample_rate,
            "es_16k_mono": (canales == 1 and sample_rate == 16000),
            "duracion_s": round(duracion_s, 3),
            "silencio_inicio_ms": round(silencio_inicio_ms, 1),
            "silencio_fin_ms": round(silencio_fin_ms, 1),
            "clipping": clipping_detectado,
            "rms_db": round(rms_db, 1),
            "muestras": muestras_norm
        }
    except Exception as e:
        return {
            "valido": False,
            "error": str(e),
            "duracion_s": 0.0,
            "es_16k_mono": False,
            "muestras": []
        }

# ===========================================================================
# 4. GESTIÓN MULTI-MODELO Y DECODIFICACIÓN CON RESTRICCIONES (LEXICÓN)
# ===========================================================================

class MultiModelASRManager:
    _instance = None

    def __init__(self):
        self.recognizers = {}
        self.models_info = {}
        self.lexicon = {}

        # 1. Cargar el léxico canónico
        ruta_lex = MODELS_CATALOG["scratch_int8"]["lexicon_path"]
        self._cargar_lexicon(ruta_lex)

        # 2. Indexar e inicializar catálogo de modelos
        for model_id, cfg in MODELS_CATALOG.items():
            if os.path.exists(cfg["model_path"]) and os.path.exists(cfg["tokens_path"]):
                size_mb = round(os.path.getsize(cfg["model_path"]) / (1024 * 1024), 2)
                h_model = self._calcular_sha256(cfg["model_path"])
                h_tokens = self._calcular_sha256(cfg["tokens_path"])
                self.models_info[model_id] = {
                    **cfg,
                    "disponible": True,
                    "tamano_mb": size_mb,
                    "sha256": h_model,
                    "tokens_sha256": h_tokens
                }
            else:
                self.models_info[model_id] = {
                    **cfg,
                    "disponible": False,
                    "tamano_mb": 0.0,
                    "sha256": "",
                    "tokens_sha256": ""
                }

        # Pre-cargar el modelo por defecto (scratch_int8)
        self.get_recognizer(DEFAULT_MODEL_ID)
        print(f"Gestor Multi-Modelo inicializado con {len(self.models_info)} modelos.")

    def _calcular_sha256(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _cargar_lexicon(self, ruta_lexicon: str):
        if os.path.exists(ruta_lexicon):
            with open(ruta_lexicon, "r", encoding="utf-8") as f:
                for line in f:
                    partes = line.strip().split("\t")
                    if len(partes) == 2:
                        w, fonemas_str = partes[0].strip(), partes[1].strip()
                        self.lexicon[w] = fonemas_str.split()
            print(f"Léxico pedagógico cargado: {len(self.lexicon)} palabras.")
        else:
            print(f"[AVISO] No se encontró lexicon en: {ruta_lexicon}")

    def get_recognizer(self, model_id: str = DEFAULT_MODEL_ID):
        """Retorna o instancia perezosamente el reconocedor del modelo solicitado."""
        if model_id not in MODELS_CATALOG:
            model_id = DEFAULT_MODEL_ID

        cfg = MODELS_CATALOG[model_id]
        if not os.path.exists(cfg["model_path"]):
            raise FileNotFoundError(f"Archivo de modelo no disponible: {cfg['model_path']}")

        if model_id not in self.recognizers:
            print(f"Cargando modelo '{model_id}' ({cfg['nombre']})...")
            rec = sherpa_onnx.OfflineRecognizer.from_zipformer_ctc(
                model=cfg["model_path"],
                tokens=cfg["tokens_path"],
                num_threads=2,
                debug=False
            )
            self.recognizers[model_id] = rec
            print(f"Modelo '{model_id}' listo en memoria.")

        return self.recognizers[model_id]

    def transcribir_muestras_16k(self, muestras_float: list, model_id: str = DEFAULT_MODEL_ID):
        """Ejecuta la inferencia acústica cruda con el modelo seleccionado."""
        recognizer = self.get_recognizer(model_id)
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, muestras_float)
        recognizer.decode_stream(stream)

        res = stream.result
        tokens_predichos = getattr(res, "tokens", [])
        timestamps = getattr(res, "timestamps", [])
        duraciones = getattr(res, "durations", [])

        if not tokens_predichos and res.text:
            tokens_predichos = self._tokenizar_texto_ctc(res.text)

        return {
            "texto_crudo": res.text,
            "tokens": tokens_predichos,
            "timestamps": [round(t, 3) for t in timestamps] if timestamps else [],
            "duraciones": [round(d, 3) for d in duraciones] if duraciones else []
        }

    def _tokenizar_texto_ctc(self, texto_ctc: str) -> list:
        tokens_encontrados = []
        i = 0
        largo = len(texto_ctc)
        tokens_ordenados = sorted(list(FONEMAS_CANONICOS), key=lambda x: len(x), reverse=True)

        while i < largo:
            coincidio = False
            for tok in tokens_ordenados:
                if texto_ctc.startswith(tok, i):
                    tokens_encontrados.append(tok)
                    i += len(tok)
                    coincidio = True
                    break
            if not coincidio:
                tokens_encontrados.append(texto_ctc[i])
                i += 1
        return tokens_encontrados

    def decodificar_con_restricciones_lexico(self, pred_tokens: list, max_word_err_rate: float = 0.45):
        """
        Decodificación restringida por léxico pedagógico (Dynamic Programming Viterbi).
        Segmenta y mapea la secuencia fonética predicha a palabras válidas del corpus,
        recuperando consonantes y vocales elididas por coarticulación en transiciones.
        """
        if not pred_tokens or not self.lexicon:
            return [], pred_tokens

        n = len(pred_tokens)
        dp = [float("inf")] * (n + 1)
        parent = [None] * (n + 1)
        dp[0] = 0

        for j in range(1, n + 1):
            # Opción fallback: fonema no reconocido / inserción
            if dp[j - 1] + 1.2 < dp[j]:
                dp[j] = dp[j - 1] + 1.2
                parent[j] = (j - 1, None, [pred_tokens[j - 1]], True)

            # Evaluar palabras del léxico en ventanas alrededor de j
            for word, w_phones in self.lexicon.items():
                L = len(w_phones)
                for i in range(max(0, j - L - 4), j):
                    seg = pred_tokens[i:j]
                    if abs(len(seg) - L) > 3:
                        continue
                    dist = dp_levenshtein_list(w_phones, seg)
                    if dist <= max(2, int(L * max_word_err_rate)):
                        costo = dp[i] + dist
                        if costo < dp[j]:
                            dp[j] = costo
                            parent[j] = (i, word, w_phones, False)

        # Reconstrucción de la ruta óptima
        curr = n
        recon_words = []
        recon_phones = []
        while curr > 0:
            p = parent[curr]
            if not p:
                break
            prev_idx, w, phones, is_raw = p
            if w:
                recon_words.append(w)
            recon_phones = phones + recon_phones
            curr = prev_idx

        recon_words.reverse()
        return recon_words, recon_phones

def dp_levenshtein_list(s1: list, s2: list) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]

SherpaOnnxManager = MultiModelASRManager

# ===========================================================================
# 5. GESTIÓN DEL CORPUS Y AUDIOS PRE-GRABADOS
# ===========================================================================

class CorpusManager:
    _instance = None

    def __init__(self):
        self.oraciones = []
        self.palabras = []
        self.audios_oraciones_map = {}
        self.audios_palabras_map = {}
        self._cargar_catalogo()

    def _cargar_catalogo(self):
        if os.path.exists(ORACIONES_JSON):
            with open(ORACIONES_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.oraciones = data.get("oraciones", [])

        if os.path.exists(PALABRAS_JSON):
            with open(PALABRAS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_palabras = data.get("palabras", [])
                for p in raw_palabras:
                    self.palabras.append({
                        "id": p.get("id"),
                        "uch": p.get("uch"),
                        "es": p.get("es"),
                        "categoria": p.get("categoria_gramatical", "")
                    })
                    for forma in p.get("formas", []):
                        self.palabras.append({
                            "id": forma.get("id"),
                            "uch": forma.get("uch"),
                            "es": forma.get("es"),
                            "raiz_id": p.get("id"),
                            "categoria": "forma_derivada"
                        })

        if os.path.exists(DIR_AUDIOS_ORACIONES):
            for hablante in os.listdir(DIR_AUDIOS_ORACIONES):
                hablante_dir = os.path.join(DIR_AUDIOS_ORACIONES, hablante)
                if os.path.isdir(hablante_dir):
                    for arch in os.listdir(hablante_dir):
                        if arch.lower().endswith(".wav"):
                            match = re.match(r"(O_\d{3})", arch)
                            if match:
                                oid = match.group(1)
                                if oid not in self.audios_oraciones_map:
                                    self.audios_oraciones_map[oid] = []
                                self.audios_oraciones_map[oid].append({
                                    "hablante": hablante,
                                    "archivo": arch,
                                    "ruta_relativa": os.path.join("audios_oraciones", hablante, arch)
                                })

        if os.path.exists(DIR_AUDIOS_PALABRAS):
            for hablante in os.listdir(DIR_AUDIOS_PALABRAS):
                hablante_dir = os.path.join(DIR_AUDIOS_PALABRAS, hablante)
                if os.path.isdir(hablante_dir):
                    for arch in os.listdir(hablante_dir):
                        if arch.lower().endswith(".wav"):
                            nombre_base = arch[:-4]
                            match_pid = re.sub(r"_\d+$", "", nombre_base)
                            if match_pid not in self.audios_palabras_map:
                                self.audios_palabras_map[match_pid] = []
                            self.audios_palabras_map[match_pid].append({
                                "hablante": hablante,
                                "archivo": arch,
                                "ruta_relativa": os.path.join("audios_palabras", hablante, arch)
                            })

        print(f"Corpus cargado: {len(self.oraciones)} oraciones, {len(self.palabras)} unidades léxicas.")

    def obtener_muestras_rapidas(self):
        items_oraciones = []
        for o in self.oraciones[:40]:
            oid = o["id"]
            audios = self.audios_oraciones_map.get(oid, [])
            items_oraciones.append({
                "id": oid,
                "tipo": "oracion",
                "uch": o["uch"],
                "es": o["es"],
                "audios": audios
            })

        items_palabras = []
        for p in self.palabras[:50]:
            pid = p["id"]
            audios = self.audios_palabras_map.get(pid, [])
            items_palabras.append({
                "id": pid,
                "tipo": "palabra",
                "uch": p["uch"],
                "es": p["es"],
                "audios": audios
            })

        return {
            "oraciones": items_oraciones,
            "palabras": items_palabras
        }

# ===========================================================================
# 6. SERVICIO DE CONVERSIÓN Y EVALUACIÓN
# ===========================================================================

def convertir_a_wav_16k_mono(input_path: str, output_wav_path: str):
    comando = [
        "/usr/bin/ffmpeg",
        "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_wav_path
    ]
    subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=15
    )

def evaluar_audio_con_modelo(
    audio_bytes: bytes,
    extension: str,
    texto_objetivo: str,
    multi_mgr: MultiModelASRManager = None,
    model_id: str = DEFAULT_MODEL_ID,
    decoding_mode: str = "greedy_search",
    sherpa_mgr: MultiModelASRManager = None
):
    if multi_mgr is None:
        multi_mgr = sherpa_mgr
    """
    Flujo central de evaluación:
    1. Transcodifica audio a 16 kHz Mono.
    2. Diagnostica acústica (duración, silencios).
    3. Inferencia con el modelo seleccionado (Bilingüe / Scratch / Fine-tune, INT8 / FP32).
    4. Decodificación según modo (greedy_search o con_restricciones).
    5. G2P del texto objetivo.
    6. Alineación fonética y cálculo de métricas.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_tmp = os.path.join(tmp_dir, f"input.{extension}")
        output_wav = os.path.join(tmp_dir, "processed_16k.wav")

        with open(input_tmp, "wb") as f:
            f.write(audio_bytes)

        convertir_a_wav_16k_mono(input_tmp, output_wav)

        diag_acustico = analizar_archivo_audio_wav(output_wav)
        if not diag_acustico["valido"] or not diag_acustico["muestras"]:
            raise ValueError(f"Error procesando muestras de audio: {diag_acustico.get('error', 'Audio vacío')}")

        # 1. Inferencia acústica
        res_inferencia = multi_mgr.transcribir_muestras_16k(diag_acustico["muestras"], model_id=model_id)
        tokens_crudos = res_inferencia["tokens"]

        # 2. Decodificación según modo
        # Para evaluar lo que REALMENTE se repitió, preservamos los fonemas acústicos reales
        # como base de la evaluación y del cálculo de PER y precisión fonética.
        if decoding_mode == "con_restricciones":
            palabras_reconocidas, _ = multi_mgr.decodificar_con_restricciones_lexico(tokens_crudos)
        else:
            palabras_reconocidas = []

        fonemas_predichos = tokens_crudos

        # 3. G2P del texto objetivo
        res_g2p = texto_a_fonemas_completo(texto_objetivo)
        fonemas_esperados = res_g2p["fonemas"]

        # 4. Métricas y alineación
        metricas = calcular_metricas(
            referencia=fonemas_esperados,
            hipotesis=fonemas_predichos,
            texto_ref=texto_objetivo,
            tokens_predichos=fonemas_predichos
        )

        # 5. Reconstrucción fiel de lo que realmente se repitió
        texto_repetido_real = reconstruir_texto_repetido(
            fonemas_predichos=fonemas_predichos,
            texto_objetivo=texto_objetivo,
            alineacion=metricas["alineacion"]
        )

        diag_ret = {k: v for k, v in diag_acustico.items() if k != "muestras"}
        info_mod = multi_mgr.models_info.get(model_id, MODELS_CATALOG.get(DEFAULT_MODEL_ID, {}))

        return {
            "texto_objetivo": texto_objetivo,
            "fonemas_esperados": fonemas_esperados,
            "desglose_palabras_g2p": res_g2p["desglose"],
            "salida_cruda_modelo": res_inferencia["texto_crudo"],
            "tokens_crudos_ctc": tokens_crudos,
            "fonemas_predichos": fonemas_predichos,
            "texto_repetido_real": texto_repetido_real,
            "palabras_reconocidas_lexico": palabras_reconocidas,
            "modo_decodificacion": decoding_mode,
            "timestamps": res_inferencia["timestamps"],
            "metricas": metricas,
            "diagnostico_audio": diag_ret,
            "modelo_info": {
                "id": model_id,
                "nombre": info_mod.get("nombre", model_id),
                "descripcion": info_mod.get("descripcion", ""),
                "sha256": info_mod.get("sha256", ""),
                "tamano_mb": info_mod.get("tamano_mb", 0.0),
                "origen": info_mod.get("origen", ""),
                "precision": info_mod.get("precision", "")
            }
        }

# ===========================================================================
# 7. MANEJADOR HTTP Y ENDPOINTS DE LA API REST
# ===========================================================================

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class ASRRequestHandler(SimpleHTTPRequestHandler):
    multi_mgr = None
    sherpa_mgr = None
    corpus_mgr = None

    def __init__(self, *args, **kwargs):
        if self.multi_mgr is None and self.sherpa_mgr is not None:
            self.multi_mgr = self.sherpa_mgr
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _responder_json(self, status_code: int, datos: dict):
        cuerpo = json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: Info del sistema y modelos disponibles
        if path == "/api/info":
            ip_local = self._obtener_ip_local()
            modelos_lista = list(self.multi_mgr.models_info.values())
            m_def = self.multi_mgr.models_info.get(DEFAULT_MODEL_ID) or self.multi_mgr.models_info.get("scratch_int8", {})
            modelo_compat = {
                "archivo": m_def.get("model_path", ""),
                "sha256": m_def.get("sha256", ""),
                "tamano_mb": m_def.get("tamano_mb", 0.0),
                "tokens": m_def.get("tokens_path", ""),
                "tokens_sha256": m_def.get("tokens_sha256", "")
            }
            self._responder_json(200, {
                "estado": "en_linea",
                "modelo": modelo_compat,
                "modelos": modelos_lista,
                "modelo_activo_default": DEFAULT_MODEL_ID if DEFAULT_MODEL_ID in self.multi_mgr.models_info else "scratch_int8",
                "modos_decodificacion": [
                    {
                        "id": "greedy_search",
                        "nombre": "Greedy Search (CTC Puro)",
                        "descripcion": "Argmax frame a frame sin restricciones léxicas. Decodificación estándar directa de la red acústica."
                    },
                    {
                        "id": "con_restricciones",
                        "nombre": "Con Restricciones Léxicas (Lexicón Cerrado)",
                        "descripcion": "Alinea y segmenta la salida sobre el vocabulario pedagógico cerrado (326 palabras). Corrige y recupera fonemas elididos en fronteras de palabras."
                    }
                ],
                "servidor": {
                    "ip_local": ip_local,
                    "puerto": self.server.server_port,
                    "url_movil": f"http://{ip_local}:{self.server.server_port}"
                }
            })
            return

        # 2. API: Catálogo del Corpus
        elif path == "/api/corpus":
            muestras = self.corpus_mgr.obtener_muestras_rapidas()
            self._responder_json(200, muestras)
            return

        # 3. API: Transmisión de Audio de Muestra
        elif path == "/api/audio":
            ruta_rel = query.get("ruta", [""])[0]
            if not ruta_rel:
                self._responder_json(400, {"error": "Parámetro 'ruta' requerido."})
                return

            ruta_abs = os.path.abspath(os.path.join(BASE_DIR, "ASR", ruta_rel))
            directorio_permitido_asr = os.path.abspath(os.path.join(BASE_DIR, "ASR"))

            if not ruta_abs.startswith(directorio_permitido_asr + os.sep) or not os.path.exists(ruta_abs):
                self._responder_json(403, {"error": "Acceso denegado a la ruta solicitada."})
                return

            try:
                tamano = os.path.getsize(ruta_abs)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(tamano))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(ruta_abs, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
            except Exception as e:
                self._responder_json(500, {"error": f"Error leyendo audio: {str(e)}"})
            return

        # 4. Servir Frontend estático
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: Conversión G2P en vivo
        if path == "/api/g2p":
            try:
                longitud = int(self.headers.get("Content-Length", 0))
                cuerpo = self.rfile.read(longitud).decode("utf-8")
                payload = json.loads(cuerpo)
                texto = payload.get("texto", "").strip()

                resultado = texto_a_fonemas_completo(texto)
                self._responder_json(200, resultado)
            except Exception as e:
                self._responder_json(400, {"error": f"Error en G2P: {str(e)}"})
            return

        # 2. API: Evaluación de Audio con Modelo y Decodificación seleccionados
        elif path == "/api/evaluate":
            try:
                content_type = self.headers.get("Content-Type", "")
                longitud = int(self.headers.get("Content-Length", 0))

                model_id = DEFAULT_MODEL_ID
                decoding_mode = "greedy_search"

                if "application/json" in content_type:
                    cuerpo = self.rfile.read(longitud).decode("utf-8")
                    payload = json.loads(cuerpo)
                    texto_objetivo = payload.get("texto_objetivo", "").strip()
                    audio_b64 = payload.get("audio_base64", "")
                    formato = payload.get("formato", "webm")
                    model_id = payload.get("modelo", DEFAULT_MODEL_ID)
                    decoding_mode = payload.get("decodificacion", "greedy_search")

                    import base64
                    audio_bytes = base64.b64decode(audio_b64)

                elif "multipart/form-data" in content_type:
                    limite = None
                    match = re.search(r"boundary=(.*)", content_type)
                    if match:
                        limite = match.group(1).strip()

                    raw_data = self.rfile.read(longitud)
                    partes = raw_data.split(f"--{limite}".encode())

                    audio_bytes = None
                    texto_objetivo = ""
                    formato = "wav"

                    for p in partes:
                        if b"Content-Disposition" in p:
                            cabecera_cuerpo = p.split(b"\r\n\r\n", 1)
                            if len(cabecera_cuerpo) == 2:
                                cab, cont = cabecera_cuerpo
                                cab_str = cab.decode("latin1", errors="ignore")
                                cont = cont.rstrip(b"\r\n")

                                if 'name="audio"' in cab_str:
                                    audio_bytes = cont
                                    match_fn = re.search(r'filename="([^"]+)"', cab_str)
                                    if match_fn:
                                        ext = match_fn.group(1).split(".")[-1].lower()
                                        if ext in ["wav", "mp3", "m4a", "ogg", "flac", "webm"]:
                                            formato = ext
                                elif 'name="texto_objetivo"' in cab_str:
                                    texto_objetivo = cont.decode("utf-8", errors="ignore").strip()
                                elif 'name="modelo"' in cab_str:
                                    model_id = cont.decode("utf-8", errors="ignore").strip()
                                elif 'name="decodificacion"' in cab_str:
                                    decoding_mode = cont.decode("utf-8", errors="ignore").strip()

                else:
                    self._responder_json(400, {"error": "Content-Type no soportado."})
                    return

                if not audio_bytes:
                    self._responder_json(400, {"error": "No se recibió archivo de audio."})
                    return

                # Ejecutar evaluación
                resultado = evaluar_audio_con_modelo(
                    audio_bytes=audio_bytes,
                    extension=formato,
                    texto_objetivo=texto_objetivo,
                    multi_mgr=self.multi_mgr,
                    model_id=model_id,
                    decoding_mode=decoding_mode
                )

                self._responder_json(200, resultado)

            except Exception as e:
                import traceback
                traceback.print_exc()
                self._responder_json(500, {"error": f"Error evaluando audio: {str(e)}"})
            return

        # 3. API: Exportar Resultados a CSV
        elif path == "/api/export_csv":
            try:
                longitud = int(self.headers.get("Content-Length", 0))
                cuerpo = self.rfile.read(longitud).decode("utf-8")
                pruebas = json.loads(cuerpo).get("pruebas", [])

                lineas = [
                    "id,fecha,tipo,modelo,decodificacion,objetivo_uch,repetido_real,objetivo_fonemas,salida_cruda,palabras_lexico,tokens_evaluados,PER,precision,resultado_100,resultado_85,duracion_s,hash_modelo"
                ]

                for p in pruebas:
                    obj_fon = " ".join(p.get("fonemas_esperados", []))
                    tok_pred = " ".join(p.get("fonemas_predichos", []))
                    pal_lex = " ".join(p.get("palabras_reconocidas_lexico", []))
                    repetido_real = p.get("texto_repetido_real", "")
                    met = p.get("metricas", {})
                    diag = p.get("diagnostico_audio", {})
                    mod = p.get("modelo_info", {})

                    fila = [
                        str(p.get("id", "")),
                        str(p.get("timestamp", "")),
                        str(p.get("tipo", "personalizado")),
                        f'"{mod.get("nombre", "")}"',
                        f'"{p.get("modo_decodificacion", "greedy_search")}"',
                        f'"{p.get("texto_objetivo", "")}"',
                        f'"{repetido_real}"',
                        f'"{obj_fon}"',
                        f'"{p.get("salida_cruda_modelo", "")}"',
                        f'"{pal_lex}"',
                        f'"{tok_pred}"',
                        str(met.get("per", "")),
                        str(met.get("precision_fonetica", "")),
                        str(met.get("resultado_100", met.get("resultado", ""))),
                        str(met.get("resultado_85", "")),
                        str(diag.get("duracion_s", "")),
                        str(mod.get("sha256", ""))[:16]
                    ]
                    lineas.append(",".join(fila))

                csv_salida = "\n".join(lineas)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="reporte_evaluacion_asr_int8.csv"')
                self.send_header("Content-Length", str(len(csv_salida.encode("utf-8"))))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(csv_salida.encode("utf-8"))
            except Exception as e:
                self._responder_json(500, {"error": f"Error exportando CSV: {str(e)}"})
            return

        self._responder_json(404, {"error": "Endpoint no encontrado."})

    def _obtener_ip_local(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

# ===========================================================================
# 8. PUNTO DE ENTRADA PRINCIPAL
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Servidor Web ASR INT8 Diagnóstico Fonético")
    parser.add_argument("--host", default="0.0.0.0", help="Dirección host (0.0.0.0 para red local)")
    parser.add_argument("--port", type=int, default=8080, help="Puerto de escucha (default 8080)")
    args = parser.parse_args()

    print("Iniciando motor ASR Multi-Modelo Sherpa-ONNX...")
    multi_mgr = MultiModelASRManager()
    ASRRequestHandler.multi_mgr = multi_mgr

    print("Cargando catálogo del corpus...")
    corpus_mgr = CorpusManager()
    ASRRequestHandler.corpus_mgr = corpus_mgr

    servidor = ThreadedHTTPServer((args.host, args.port), ASRRequestHandler)
    ip_local = ASRRequestHandler._obtener_ip_local(None)

    print("\n==================================================================")
    print(f"  🚀 SERVIDOR WEB DE PRUEBAS ASR MULTI-MODELO EN LÍNEA")
    print(f"  🖥️  Acceso en PC:        http://localhost:{args.port}")
    print(f"  📱 Acceso en Celular:   http://{ip_local}:{args.port}")
    print(f"  📦 Modelos Cargados:")
    for mid, mcfg in multi_mgr.models_info.items():
        disp = "✅ Listo" if mcfg["disponible"] else "❌ No encontrado"
        print(f"     - [{mid}] {mcfg['nombre']} ({mcfg['tamano_mb']} MB) -> {disp}")
    print("==================================================================\n")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        servidor.server_close()

if __name__ == "__main__":
    main()
