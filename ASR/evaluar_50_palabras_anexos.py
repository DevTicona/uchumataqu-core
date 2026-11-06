#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_50_palabras_anexos.py
Evaluación empírica de 50 palabras independientes del Uchumataqu
mediante el modelo real de producción Zipformer INT8 (Sherpa-onnx).
Genera la tabla detallada para Anexos y las métricas exactas para la sección 4.5.6.
"""

import os
import sys
import gzip
import json
import csv
import time
import re
import unicodedata
from collections import defaultdict

DIR_PROYECTO = "/home/primo/proyecto-grado"
sys.path.insert(0, os.path.join(DIR_PROYECTO, "web_asr_tester"))

from server import (
    MultiModelASRManager,
    evaluar_audio_con_modelo,
    dp_levenshtein
)

def normalizar_palabras(texto: str) -> list:
    t = re.sub(r'[¿?¡!.,;:\"()\[\]]', '', texto).strip().lower()
    return t.split()

def normalizar_caracteres(texto: str) -> str:
    t = re.sub(r'[¿?¡!.,;:\"()\[\]]', '', texto)
    t = unicodedata.normalize("NFC", t.strip().lower())
    return re.sub(r'\s+', ' ', t)

def levenshtein_align(ref_tokens: list, hyp_tokens: list):
    n, m = len(ref_tokens), len(hyp_tokens)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): dp[i][0] = i
    for j in range(m + 1): dp[0][j] = j
    
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
                
    i, j = n, m
    align = []
    hits, subs, dels, ins = 0, 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_tokens[i - 1] == hyp_tokens[j - 1]:
            align.append(("match", ref_tokens[i - 1], hyp_tokens[j - 1]))
            hits += 1
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            align.append(("sub", ref_tokens[i - 1], hyp_tokens[j - 1]))
            subs += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            align.append(("del", ref_tokens[i - 1], None))
            dels += 1
            i -= 1
        else:
            align.append(("ins", None, hyp_tokens[j - 1]))
            ins += 1
            j -= 1
            
    align.reverse()
    return hits, subs, dels, ins, align

def main():
    print("Iniciando evaluación de las 50 palabras para Anexos...")
    multi_mgr = MultiModelASRManager()
    model_id = "scratch_int8"
    multi_mgr.get_recognizer(model_id)

    manifest_test = os.path.join(DIR_PROYECTO, "ASR/data/lhotse/uchumataqu_cuts_test.jsonl.gz")
    with gzip.open(manifest_test, "rt", encoding="utf-8") as f:
        word_cuts = [c for line in f if (c := json.loads(line))['supervisions'][0]['custom'].get('tipo') == 'palabra']

    by_spk = defaultdict(list)
    for c in word_cuts:
        spk = c['supervisions'][0].get('speaker')
        by_spk[spk].append(c)

    # 10 por hablante estratificadas por longitud
    def pick_10(cuts):
        cuts_sorted = sorted(cuts, key=lambda x: len(x['supervisions'][0]['text'].split()))
        step = len(cuts_sorted) / 10.0
        return [cuts_sorted[int(i * step)] for i in range(10)]

    selected_50 = []
    for spk in ['pedro', 'sofia', 'eva', 'lorenzo', 'roberto']:
        selected_50.extend(pick_10(by_spk[spk]))

    filas = []
    tot_s_w_g = tot_d_w_g = tot_i_w_g = tot_h_w_g = 0
    tot_s_w_l = tot_d_w_l = tot_i_w_l = tot_h_w_l = 0
    tot_s_c = tot_d_c = tot_i_c = tot_h_c = 0
    tot_s_p = tot_d_p = tot_i_p = tot_h_p = 0
    tot_n_w = 0
    tot_n_c = 0
    tot_n_p = 0
    latencias = []

    for idx, c in enumerate(selected_50, 1):
        wav_path = c["recording"]["sources"][0]["source"]
        sup = c["supervisions"][0]
        ref_text = sup["custom"].get("text_words", "").strip()
        speaker = sup.get("speaker", "")
        ref_phones = sup.get("text", "").split()

        with open(wav_path, "rb") as af:
            audio_bytes = af.read()

        t0 = time.time()
        res_greedy = evaluar_audio_con_modelo(
            audio_bytes=audio_bytes,
            extension="wav",
            texto_objetivo=ref_text,
            multi_mgr=multi_mgr,
            model_id=model_id,
            decoding_mode="greedy_search"
        )
        lat_ms = round((time.time() - t0) * 1000, 1)
        latencias.append(lat_ms)

        res_lex = evaluar_audio_con_modelo(
            audio_bytes=audio_bytes,
            extension="wav",
            texto_objetivo=ref_text,
            multi_mgr=multi_mgr,
            model_id=model_id,
            decoding_mode="con_restricciones"
        )

        hyp_greedy = res_greedy["texto_repetido_real"].strip()
        words_lex_list = res_lex["palabras_reconocidas_lexico"]
        hyp_lex = " ".join(words_lex_list) if words_lex_list else hyp_greedy

        hyp_phones = res_greedy["fonemas_predichos"]

        # Palabras
        w_ref = normalizar_palabras(ref_text)
        w_hyp_g = normalizar_palabras(hyp_greedy)
        w_hyp_l = normalizar_palabras(hyp_lex)

        hw_g, sw_g, dw_g, iw_g, _ = levenshtein_align(w_ref, w_hyp_g)
        hw_l, sw_l, dw_l, iw_l, _ = levenshtein_align(w_ref, w_hyp_l)

        nw = len(w_ref)
        tot_n_w += nw
        tot_s_w_g += sw_g
        tot_d_w_g += dw_g
        tot_i_w_g += iw_g
        tot_h_w_g += hw_g

        tot_s_w_l += sw_l
        tot_d_w_l += dw_l
        tot_i_w_l += iw_l
        tot_h_w_l += hw_l

        # Caracteres
        c_ref = list(normalizar_caracteres(ref_text))
        c_hyp = list(normalizar_caracteres(hyp_greedy))
        hc, sc, dc, ic, _ = levenshtein_align(c_ref, c_hyp)
        nc = len(c_ref)
        tot_n_c += nc
        tot_s_c += sc
        tot_d_c += dc
        tot_i_c += ic
        tot_h_c += hc

        # Fonemas
        hp, sp, dp, ip, _ = levenshtein_align(ref_phones, hyp_phones)
        np_ = len(ref_phones)
        tot_n_p += np_
        tot_s_p += sp
        tot_d_p += dp
        tot_i_p += ip
        tot_h_p += hp

        wer_g_item = round((sw_g + dw_g + iw_g) / nw * 100.0, 1) if nw > 0 else 0.0
        wer_l_item = round((sw_l + dw_l + iw_l) / nw * 100.0, 1) if nw > 0 else 0.0
        cer_item = round((sc + dc + ic) / nc * 100.0, 1) if nc > 0 else 0.0
        per_item = round((sp + dp + ip) / np_ * 100.0, 1) if np_ > 0 else 0.0
        prec_fon = max(0.0, round(100.0 - per_item, 1))
        aprob_85 = "APROBADO" if prec_fon >= 85.0 else "RECHAZADO"

        filas.append({
            "Nro": idx,
            "Hablante": speaker.capitalize(),
            "Palabra_Referencia": ref_text,
            "Fonemas_Referencia": " ".join(ref_phones),
            "Hipotesis_Greedy": hyp_greedy,
            "Hipotesis_Lexico": hyp_lex,
            "Fonemas_Predichos": " ".join(hyp_phones),
            "S_D_I_N_Word": f"{sw_l}/{dw_l}/{iw_l}/{nw}",
            "WER_Greedy_pct": wer_g_item,
            "WER_Lexico_pct": wer_l_item,
            "CER_pct": cer_item,
            "PER_pct": per_item,
            "Precision_pct": prec_fon,
            "Estado_85": aprob_85,
            "Latencia_ms": lat_ms
        })

    # Guardar CSV
    csv_path = os.path.join(DIR_PROYECTO, "evidencias_capitulo_iv/TABLA_50_PALABRAS_ASR_ANEXOS.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    print(f"[OK] CSV guardado en: {csv_path}")

    # Cálculos globales de las 50 palabras
    wer_global_g = round((tot_s_w_g + tot_d_w_g + tot_i_w_g) / tot_n_w * 100.0, 2)
    wer_global_l = round((tot_s_w_l + tot_d_w_l + tot_i_w_l) / tot_n_w * 100.0, 2)
    cer_global = round((tot_s_c + tot_d_c + tot_i_c) / tot_n_c * 100.0, 2)
    per_global = round((tot_s_p + tot_d_p + tot_i_p) / tot_n_p * 100.0, 2)
    lat_media = round(sum(latencias) / len(latencias), 2)
    aprob_count = sum(1 for f in filas if f["Estado_85"] == "APROBADO")
    pct_aprob = round(aprob_count / len(filas) * 100.0, 2)

    print("\n" + "=" * 70)
    print("  RESULTADOS CONSOLIDADOS (50 PALABRAS DE PRUEBA)")
    print("=" * 70)
    print(f"Total palabras evaluadas (N)   : {tot_n_w}")
    print(f"Sustituciones Greedy           : {tot_s_w_g}")
    print(f"WER Greedy                     : {wer_global_g}%")
    print(f"Sustituciones Léxico           : {tot_s_w_l}")
    print(f"Eliminaciones Léxico           : {tot_d_w_l}")
    print(f"Inserciones Léxico             : {tot_i_w_l}")
    print(f"WER Léxico Híbrido             : {wer_global_l}%")
    print(f"Caracteres Totales             : {tot_n_c} (S={tot_s_c}, D={tot_d_c}, I={tot_i_c}) -> CER: {cer_global}%")
    print(f"Fonemas Totales                : {tot_n_p} (S={tot_s_p}, D={tot_d_p}, I={tot_i_p}) -> PER: {per_global}%")
    print(f"Aprobados semáforo >= 85%      : {aprob_count}/50 ({pct_aprob}%)")
    print(f"Latencia media CPU             : {lat_media} ms")
    print("=" * 70)

    # Imprimir resumen de tabla markdown
    print("\nResumen guardado. Listo para generar el markdown.")

if __name__ == "__main__":
    main()

