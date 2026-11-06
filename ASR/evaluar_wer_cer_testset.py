#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_wer_cer_testset.py
Evaluación empírica independiente del módulo ASR (Zipformer INT8)
sobre el conjunto de prueba oficial (460 cortes independientes).
Calcula Sustituciones (S), Eliminaciones (D), Inserciones (I), Hits (H),
WER (Word Error Rate), CER (Character Error Rate) y PER (Phoneme Error Rate).
"""

import os
import sys
import gzip
import json
import csv
import time
import re
import unicodedata

# Agregar ruta de web_asr_tester para importar el motor
DIR_PROYECTO = "/home/primo/proyecto-grado"
sys.path.insert(0, os.path.join(DIR_PROYECTO, "web_asr_tester"))

from server import (
    MultiModelASRManager,
    evaluar_audio_con_modelo,
    FONEMA_A_UCHUMATAQU,
    texto_a_fonemas_completo
)

def normalizar_palabras(texto: str) -> list:
    """Normaliza y divide texto en palabras limpias (sin puntuación, minúsculas)."""
    # Eliminar signos de puntuación comunes excepto diacríticos y apóstrofes
    t = re.sub(r'[¿?¡!.,;:\"()\[\]]', '', texto)
    t = t.strip().lower()
    return t.split()

def normalizar_caracteres(texto: str) -> str:
    """Normaliza texto para cálculo de CER (minúsculas, normalización NFC, espacios uniformes)."""
    t = re.sub(r'[¿?¡!.,;:\"()\[\]]', '', texto)
    t = unicodedata.normalize("NFC", t.strip().lower())
    # Reducir espacios múltiples a uno
    t = re.sub(r'\s+', ' ', t)
    return t

def levenshtein_align(ref_tokens: list, hyp_tokens: list):
    """
    Alineación Needleman-Wunsch / Levenshtein con backtracing.
    Retorna (hits, subs, dels, ins, align)
    """
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
    print("=" * 75)
    print("  EVALUACIÓN DE PRECISIÓN ASR (WER, CER, PER) - CONJUNTO DE PRUEBA")
    print("  Modelo Evaluado: Scratch v2 (100 épocas, INT8 - 69.2 MB)")
    print("=" * 75)

    multi_mgr = MultiModelASRManager()
    model_id = "scratch_int8"
    multi_mgr.get_recognizer(model_id)

    manifest_test = os.path.join(DIR_PROYECTO, "ASR/data/lhotse/uchumataqu_cuts_test.jsonl.gz")
    if not os.path.exists(manifest_test):
        print(f"[ERROR] Manifiesto no encontrado: {manifest_test}")
        return

    with gzip.open(manifest_test, "rt", encoding="utf-8") as f:
        cuts = [json.loads(line) for line in f]

    print(f"Cargados {len(cuts)} cortes de prueba independientes.")

    resultados = []
    
    t_inicio = time.time()

    for idx, c in enumerate(cuts, 1):
        cut_id = c["id"]
        wav_path = c["recording"]["sources"][0]["source"]
        sup = c["supervisions"][0]
        texto_ref = sup["custom"].get("text_words", sup.get("text", "")).strip()
        speaker = sup.get("speaker", "desconocido")
        tipo = sup["custom"].get("tipo", "palabra")
        fonemas_ref_raw = sup.get("text", "")
        fonemas_ref = fonemas_ref_raw.split()

        if not os.path.exists(wav_path):
            print(f"[AVISO] Archivo no encontrado: {wav_path}")
            continue

        with open(wav_path, "rb") as af:
            audio_bytes = af.read()

        t0 = time.time()
        # 1. Evaluación directa en modo greedy
        res_eval = evaluar_audio_con_modelo(
            audio_bytes=audio_bytes,
            extension="wav",
            texto_objetivo=texto_ref,
            multi_mgr=multi_mgr,
            model_id=model_id,
            decoding_mode="greedy_search"
        )
        latencia_ms = round((time.time() - t0) * 1000, 2)

        fonemas_hyp = res_eval["fonemas_predichos"]
        texto_hyp = res_eval["texto_repetido_real"]

        # 2. Evaluación con decodificación de restricciones léxicas
        res_lex = evaluar_audio_con_modelo(
            audio_bytes=audio_bytes,
            extension="wav",
            texto_objetivo=texto_ref,
            multi_mgr=multi_mgr,
            model_id=model_id,
            decoding_mode="con_restricciones"
        )
        palabras_lex = res_lex["palabras_reconocidas_lexico"]
        texto_lex = " ".join(palabras_lex) if palabras_lex else texto_hyp

        # Normalizaciones para WER y CER
        words_ref = normalizar_palabras(texto_ref)
        words_hyp = normalizar_palabras(texto_hyp)
        words_lex = normalizar_palabras(texto_lex)

        chars_ref = list(normalizar_caracteres(texto_ref))
        chars_hyp = list(normalizar_caracteres(texto_hyp))

        # Alineación por Palabras (WER Greedy)
        hw_g, sw_g, dw_g, iw_g, _ = levenshtein_align(words_ref, words_hyp)
        nw = len(words_ref)
        wer_g = round(((sw_g + dw_g + iw_g) / nw * 100.0), 2) if nw > 0 else 0.0

        # Alineación por Palabras (WER con Restricciones Léxicas)
        hw_l, sw_l, dw_l, iw_l, _ = levenshtein_align(words_ref, words_lex)
        wer_l = round(((sw_l + dw_l + iw_l) / nw * 100.0), 2) if nw > 0 else 0.0

        # Alineación por Caracteres (CER)
        hc, sc, dc, ic, _ = levenshtein_align(chars_ref, chars_hyp)
        nc = len(chars_ref)
        cer = round(((sc + dc + ic) / nc * 100.0), 2) if nc > 0 else 0.0

        # Métricas fonéticas (PER)
        hp, sp, dp, ip, _ = levenshtein_align(fonemas_ref, fonemas_hyp)
        np_ = len(fonemas_ref)
        per = round(((sp + dp + ip) / np_ * 100.0), 2) if np_ > 0 else 0.0
        precision_fonetica = max(0.0, round(100.0 - per, 2))

        # Criterios pedagógicos
        pasa_100 = (per == 0.0 and wer_g == 0.0)
        pasa_85 = (precision_fonetica >= 85.0)

        item = {
            "id_caso": f"ASR-TEST-{idx:04d}",
            "cut_id": cut_id,
            "tipo": tipo,
            "speaker": speaker,
            "audio_path": wav_path.replace(DIR_PROYECTO + "/", ""),
            "texto_referencia": texto_ref,
            "transcripcion_greedy": texto_hyp,
            "transcripcion_lexico": texto_lex,
            "fonemas_referencia": " ".join(fonemas_ref),
            "fonemas_predichos": " ".join(fonemas_hyp),
            "N_words": nw,
            "Hits_words_greedy": hw_g,
            "Sub_words_greedy": sw_g,
            "Del_words_greedy": dw_g,
            "Ins_words_greedy": iw_g,
            "WER_greedy": wer_g,
            "Hits_words_lex": hw_l,
            "Sub_words_lex": sw_l,
            "Del_words_lex": dw_l,
            "Ins_words_lex": iw_l,
            "WER_lexico": wer_l,
            "N_chars": nc,
            "Hits_chars": hc,
            "Sub_chars": sc,
            "Del_chars": dc,
            "Ins_chars": ic,
            "CER": cer,
            "N_phones": np_,
            "Hits_phones": hp,
            "Sub_phones": sp,
            "Del_phones": dp,
            "Ins_phones": ip,
            "PER": per,
            "precision_fonetica": precision_fonetica,
            "criterio_100": "APROBADO" if pasa_100 else "RECHAZADO",
            "criterio_85": "APROBADO" if pasa_85 else "RECHAZADO",
            "latencia_ms": latencia_ms
        }
        resultados.append(item)

        if idx % 50 == 0 or idx == len(cuts):
            print(f"  Procesados {idx}/{len(cuts)} cortes... (último: {cut_id}, PER={per}%, WER={wer_g}%)")

    t_total = time.time() - t_inicio
    print(f"\nEvaluación completada en {t_total:.2f} s ({t_total/len(resultados)*1000:.1f} ms/audio).")

    # Guardar CSV
    output_dir = os.path.join(DIR_PROYECTO, "evidencias_capitulo_iv")
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "RESULTADOS_DETALLADOS_WER_CER_ASR.csv")

    fieldnames = list(resultados[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(resultados)

    print(f"\n[OK] CSV detallado generado en: {csv_path}")

    # Guardar resumen JSON para análisis y reporte
    resumen = generar_resumen(resultados, t_total)
    json_path = os.path.join(output_dir, "resumen_wer_cer_asr.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)
    print(f"[OK] Resumen JSON generado en: {json_path}")

    # Imprimir resumen en consola
    imprimir_resumen(resumen)

def generar_resumen(resultados: list, t_total: float) -> dict:
    total_n = len(resultados)
    
    # Acumuladores globales
    tot_nw = sum(r["N_words"] for r in resultados)
    tot_sw_g = sum(r["Sub_words_greedy"] for r in resultados)
    tot_dw_g = sum(r["Del_words_greedy"] for r in resultados)
    tot_iw_g = sum(r["Ins_words_greedy"] for r in resultados)
    tot_hw_g = sum(r["Hits_words_greedy"] for r in resultados)
    wer_global_greedy = round(((tot_sw_g + tot_dw_g + tot_iw_g) / tot_nw * 100.0), 2)

    tot_sw_l = sum(r["Sub_words_lex"] for r in resultados)
    tot_dw_l = sum(r["Del_words_lex"] for r in resultados)
    tot_iw_l = sum(r["Ins_words_lex"] for r in resultados)
    tot_hw_l = sum(r["Hits_words_lex"] for r in resultados)
    wer_global_lex = round(((tot_sw_l + tot_dw_l + tot_iw_l) / tot_nw * 100.0), 2)

    tot_nc = sum(r["N_chars"] for r in resultados)
    tot_sc = sum(r["Sub_chars"] for r in resultados)
    tot_dc = sum(r["Del_chars"] for r in resultados)
    tot_ic = sum(r["Ins_chars"] for r in resultados)
    tot_hc = sum(r["Hits_chars"] for r in resultados)
    cer_global = round(((tot_sc + tot_dc + tot_ic) / tot_nc * 100.0), 2)

    tot_np = sum(r["N_phones"] for r in resultados)
    tot_sp = sum(r["Sub_phones"] for r in resultados)
    tot_dp = sum(r["Del_phones"] for r in resultados)
    tot_ip = sum(r["Ins_phones"] for r in resultados)
    tot_hp = sum(r["Hits_phones"] for r in resultados)
    per_global = round(((tot_sp + tot_dp + tot_ip) / tot_np * 100.0), 2)

    prec_media = round(sum(r["precision_fonetica"] for r in resultados) / total_n, 2)
    lat_media = round(sum(r["latencia_ms"] for r in resultados) / total_n, 2)
    
    aprob_100 = sum(1 for r in resultados if r["criterio_100"] == "APROBADO")
    aprob_85 = sum(1 for r in resultados if r["criterio_85"] == "APROBADO")

    # Desglose por tipo
    desglose_tipo = {}
    for t in ["palabra", "oracion"]:
        sub = [r for r in resultados if r["tipo"] == t]
        if not sub:
            continue
        n_sub = len(sub)
        nw = sum(r["N_words"] for r in sub)
        sw_g = sum(r["Sub_words_greedy"] for r in sub)
        dw_g = sum(r["Del_words_greedy"] for r in sub)
        iw_g = sum(r["Ins_words_greedy"] for r in sub)
        wer_g = round((sw_g + dw_g + iw_g) / nw * 100.0, 2)

        sw_l = sum(r["Sub_words_lex"] for r in sub)
        dw_l = sum(r["Del_words_lex"] for r in sub)
        iw_l = sum(r["Ins_words_lex"] for r in sub)
        wer_l = round((sw_l + dw_l + iw_l) / nw * 100.0, 2)

        nc = sum(r["N_chars"] for r in sub)
        sc = sum(r["Sub_chars"] for r in sub)
        dc = sum(r["Del_chars"] for r in sub)
        ic = sum(r["Ins_chars"] for r in sub)
        cer = round((sc + dc + ic) / nc * 100.0, 2)

        np_ = sum(r["N_phones"] for r in sub)
        sp = sum(r["Sub_phones"] for r in sub)
        dp = sum(r["Del_phones"] for r in sub)
        ip = sum(r["Ins_phones"] for r in sub)
        per = round((sp + dp + ip) / np_ * 100.0, 2)

        desglose_tipo[t] = {
            "total_muestras": n_sub,
            "N_words": nw,
            "WER_greedy": wer_g,
            "WER_lexico": wer_l,
            "N_chars": nc,
            "CER": cer,
            "N_phones": np_,
            "PER": per,
            "aprobados_100_pct": round(sum(1 for r in sub if r["criterio_100"] == "APROBADO") / n_sub * 100.0, 2),
            "aprobados_85_pct": round(sum(1 for r in sub if r["criterio_85"] == "APROBADO") / n_sub * 100.0, 2),
            "latencia_media_ms": round(sum(r["latencia_ms"] for r in sub) / n_sub, 2)
        }

    # Desglose por locutor
    desglose_hablante = {}
    speakers = sorted(list(set(r["speaker"] for r in resultados)))
    for spk in speakers:
        sub = [r for r in resultados if r["speaker"] == spk]
        n_sub = len(sub)
        nw = sum(r["N_words"] for r in sub)
        sw_g = sum(r["Sub_words_greedy"] for r in sub)
        dw_g = sum(r["Del_words_greedy"] for r in sub)
        iw_g = sum(r["Ins_words_greedy"] for r in sub)
        wer_g = round((sw_g + dw_g + iw_g) / nw * 100.0, 2)

        sw_l = sum(r["Sub_words_lex"] for r in sub)
        dw_l = sum(r["Del_words_lex"] for r in sub)
        iw_l = sum(r["Ins_words_lex"] for r in sub)
        wer_l = round((sw_l + dw_l + iw_l) / nw * 100.0, 2)

        nc = sum(r["N_chars"] for r in sub)
        sc = sum(r["Sub_chars"] for r in sub)
        dc = sum(r["Del_chars"] for r in sub)
        ic = sum(r["Ins_chars"] for r in sub)
        cer = round((sc + dc + ic) / nc * 100.0, 2)

        np_ = sum(r["N_phones"] for r in sub)
        sp = sum(r["Sub_phones"] for r in sub)
        dp = sum(r["Del_phones"] for r in sub)
        ip = sum(r["Ins_phones"] for r in sub)
        per = round((sp + dp + ip) / np_ * 100.0, 2)

        desglose_hablante[spk] = {
            "total_muestras": n_sub,
            "N_words": nw,
            "WER_greedy": wer_g,
            "WER_lexico": wer_l,
            "N_chars": nc,
            "CER": cer,
            "N_phones": np_,
            "PER": per,
            "precision_media": round(sum(r["precision_fonetica"] for r in sub) / n_sub, 2),
            "latencia_media_ms": round(sum(r["latencia_ms"] for r in sub) / n_sub, 2)
        }

    # Ejemplos de discrepancias/errores representativos
    errores = [r for r in resultados if r["PER"] > 0 or r["WER_greedy"] > 0]
    errores_ordenados = sorted(errores, key=lambda x: x["PER"], reverse=True)

    return {
        "resumen_global": {
            "total_muestras": total_n,
            "N_words": tot_nw,
            "S_words_greedy": tot_sw_g,
            "D_words_greedy": tot_dw_g,
            "I_words_greedy": tot_iw_g,
            "WER_greedy": wer_global_greedy,
            "S_words_lexico": tot_sw_l,
            "D_words_lexico": tot_dw_l,
            "I_words_lexico": tot_iw_l,
            "WER_lexico": wer_global_lex,
            "N_chars": tot_nc,
            "S_chars": tot_sc,
            "D_chars": tot_dc,
            "I_chars": tot_ic,
            "CER": cer_global,
            "N_phones": tot_np,
            "S_phones": tot_sp,
            "D_phones": tot_dp,
            "I_phones": tot_ip,
            "PER": per_global,
            "precision_fonetica_media": prec_media,
            "aprobados_100": aprob_100,
            "porcentaje_aprobados_100": round(aprob_100 / total_n * 100.0, 2),
            "aprobados_85": aprob_85,
            "porcentaje_aprobados_85": round(aprob_85 / total_n * 100.0, 2),
            "latencia_media_ms": lat_media,
            "tiempo_total_s": round(t_total, 2)
        },
        "desglose_por_tipo": desglose_tipo,
        "desglose_por_hablante": desglose_hablante,
        "total_discrepancias": len(errores),
        "ejemplos_discrepancias": errores_ordenados[:15]
    }

def imprimir_resumen(res: dict):
    g = res["resumen_global"]
    print("\n" + "=" * 75)
    print("  RESULTADOS GLOBALES DEL RECONOCIMIENTO (TEST SET: 460 AUDIOS)")
    print("=" * 75)
    print(f"Total Muestras      : {g['total_muestras']} (325 palabras + 135 oraciones)")
    print(f"Palabras Totales    : {g['N_words']}")
    print(f"WER Greedy          : {g['WER_greedy']}% (S={g['S_words_greedy']}, D={g['D_words_greedy']}, I={g['I_words_greedy']})")
    print(f"WER Híbrido Léxico  : {g['WER_lexico']}% (S={g['S_words_lexico']}, D={g['D_words_lexico']}, I={g['I_words_lexico']})")
    print(f"Caracteres Totales  : {g['N_chars']}")
    print(f"CER (Char Error)    : {g['CER']}% (S={g['S_chars']}, D={g['D_chars']}, I={g['I_chars']})")
    print(f"Fonemas Totales     : {g['N_phones']}")
    print(f"PER (Phone Error)   : {g['PER']}% (S={g['S_phones']}, D={g['D_phones']}, I={g['I_phones']})")
    print(f"Precisión Media     : {g['precision_fonetica_media']}%")
    print(f"Aprobación Estricta : {g['aprobados_100']}/{g['total_muestras']} ({g['porcentaje_aprobados_100']}%)")
    print(f"Aprobación >= 85%   : {g['aprobados_85']}/{g['total_muestras']} ({g['porcentaje_aprobados_85']}%)")
    print(f"Latencia Media CPU  : {g['latencia_media_ms']} ms por audio")
    print("=" * 75)

if __name__ == "__main__":
    main()

