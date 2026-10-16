"""
preparar_dataset.py
Genera los manifests estructurados (JSON y formato Kaldi) y las particiones de
entrenamiento (train, val, test) para el módulo ASR de Uchumataqu.

Fuentes:
  - Para_ASR/audios_palabras/{lorenzo, pedro, roberto, sofia}/*.wav
  - Para_ASR/audios_oraciones/pedro/*.wav
  - excel/palabras_pln.xlsx
  - excel/oraciones.xlsx
  - Para_ASR/datos_asr/tokens.txt

Salidas en Para_ASR/data/manifests/:
  - all_manifest.json
  - train_manifest.json
  - val_manifest.json
  - test_manifest.json
  - kaldi/{train, val, test}/{wav.scp, text, utt2spk, spk2utt}
"""

import os
import re
import json
import wave
import random
import sys
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
entrenamiento_dir = script_dir
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)

sys.path.insert(0, entrenamiento_dir)
from lector_xlsx import leer_xlsx
from preparar_asr import grafema_a_fonema, FONEMAS_CANONICOS


def obtener_info_audio(ruta_wav: str) -> dict:
    """Extrae duración y propiedades de un archivo WAV sin dependencias externas."""
    with wave.open(ruta_wav, "rb") as w:
        canales = w.getnchannels()
        sample_width = w.getsampwidth()
        framerate = w.getframerate()
        nframes = w.getnframes()
        duracion = nframes / float(framerate) if framerate > 0 else 0.0

    return {
        "canales": canales,
        "sample_width": sample_width,
        "framerate": framerate,
        "nframes": nframes,
        "duracion_segundos": round(duracion, 4)
    }


def cargar_diccionarios_pln(ruta_palabras_xlsx: str, ruta_oraciones_xlsx: str):
    """Carga mapeos de IDs y textos en Uchumataqu y Español."""
    palabras_map = {}
    rows_p = leer_xlsx(ruta_palabras_xlsx)[1:]
    for r in rows_p:
        if len(r) > 1 and r[0] and r[1]:
            pid = r[0].strip().lower()
            uch = r[1].strip()
            es = r[2].strip() if len(r) > 2 else ""
            palabras_map[pid] = {
                "id": pid,
                "uch": uch,
                "es": es,
                "fonemas": grafema_a_fonema(uch)
            }

    oraciones_map = {}
    rows_o = leer_xlsx(ruta_oraciones_xlsx)[1:]
    for r in rows_o:
        if len(r) > 1 and r[0] and r[1]:
            oid = r[0].strip()
            # Filtrar solo las 120 primeras oraciones con audio (O_001..O_120)
            try:
                num = int(re.sub(r"\D", "", oid))
                if num > 120:
                    continue
            except ValueError:
                pass
            uch = r[1].strip()
            es = r[2].strip() if len(r) > 2 else ""
            # Fonetizar cada palabra de la oración
            palabras_oracion = [p for p in re.sub(r"[^\w\sʼ'\-]", "", uch).split() if p]
            fonemas_oracion = []
            for p in palabras_oracion:
                try:
                    fonemas_oracion.append(grafema_a_fonema(p))
                except Exception:
                    pass
            
            oraciones_map[oid] = {
                "id": oid,
                "uch": uch,
                "es": es,
                "fonemas": " ".join(fonemas_oracion)
            }

    return palabras_map, oraciones_map


def recolectar_audios(palabras_map: dict, oraciones_map: dict) -> list:
    """Escanea audios_palabras y audios_oraciones asociando metadata y fonemas."""
    manifest_entries = []

    # 1. Audios de palabras
    dir_palabras = os.path.join(asr_dir, "audios_palabras")
    if os.path.exists(dir_palabras):
        for locutor in sorted(os.listdir(dir_palabras)):
            dir_loc = os.path.join(dir_palabras, locutor)
            if not os.path.isdir(dir_loc):
                continue
            for f in sorted(os.listdir(dir_loc)):
                if not f.lower().endswith(".wav") or f.endswith(":Zone.Identifier"):
                    continue
                ruta_abs = os.path.join(dir_loc, f)
                nombre_base = os.path.splitext(f)[0]
                m = re.match(r"^(.*?)(?:_0([1-9]))?$", nombre_base)
                if not m:
                    continue
                pid = m.group(1).lower()
                toma = f"0{m.group(2)}" if m.group(2) else "01"

                item_info = palabras_map.get(pid)
                if not item_info:
                    continue

                try:
                    info_audio = obtener_info_audio(ruta_abs)
                except Exception as e:
                    print(f"[ADVERTENCIA] Error leyendo audio {ruta_abs}: {e}")
                    continue

                utt_id = f"pal_{locutor}_{pid}_{toma}"
                manifest_entries.append({
                    "utt_id": utt_id,
                    "tipo": "palabra",
                    "id_lexico": pid,
                    "locutor": locutor,
                    "toma": toma,
                    "texto_uch": item_info["uch"],
                    "texto_es": item_info["es"],
                    "fonemas": item_info["fonemas"],
                    "audio_path": ruta_abs,
                    "audio_rel_path": os.path.relpath(ruta_abs, project_root),
                    "duracion": info_audio["duracion_segundos"],
                    "framerate": info_audio["framerate"],
                    "canales": info_audio["canales"]
                })

    # 2. Audios de oraciones
    dir_oraciones = os.path.join(asr_dir, "audios_oraciones")
    if os.path.exists(dir_oraciones):
        for locutor in sorted(os.listdir(dir_oraciones)):
            dir_loc = os.path.join(dir_oraciones, locutor)
            if not os.path.isdir(dir_loc):
                continue
            for f in sorted(os.listdir(dir_loc)):
                if not f.lower().endswith(".wav") or f.endswith(":Zone.Identifier"):
                    continue
                ruta_abs = os.path.join(dir_loc, f)
                nombre_base = os.path.splitext(f)[0]
                m = re.match(r"^(.*?)(?:_0([1-9]))?$", nombre_base)
                if not m:
                    continue
                slug = m.group(1).lower()
                toma = f"0{m.group(2)}" if m.group(2) else "01"

                # Buscar la oración que coincida con el slug
                match_oid = None
                for oid, odata in oraciones_map.items():
                    # Slug generado a partir de las primeras palabras o id
                    clean_uch = re.sub(r"[^\w\s]", "", odata["uch"].lower()).replace(" ", "_")
                    if slug == clean_uch or slug == oid.lower() or clean_uch.startswith(slug) or slug.startswith(clean_uch[:20]):
                        match_oid = oid
                        break

                if not match_oid:
                    # Intento directo por id de oración
                    for oid in oraciones_map:
                        if oid.lower() == slug:
                            match_oid = oid
                            break

                if not match_oid:
                    continue

                item_info = oraciones_map[match_oid]
                try:
                    info_audio = obtener_info_audio(ruta_abs)
                except Exception as e:
                    print(f"[ADVERTENCIA] Error leyendo audio {ruta_abs}: {e}")
                    continue

                utt_id = f"ora_{locutor}_{match_oid}_{toma}"
                manifest_entries.append({
                    "utt_id": utt_id,
                    "tipo": "oracion",
                    "id_lexico": match_oid,
                    "locutor": locutor,
                    "toma": toma,
                    "texto_uch": item_info["uch"],
                    "texto_es": item_info["es"],
                    "fonemas": item_info["fonemas"],
                    "audio_path": ruta_abs,
                    "audio_rel_path": os.path.relpath(ruta_abs, project_root),
                    "duracion": info_audio["duracion_segundos"],
                    "framerate": info_audio["framerate"],
                    "canales": info_audio["canales"]
                })

    return manifest_entries


def particionar_dataset(manifest_entries: list, seed: int = 42) -> tuple:
    """
    Divide los datos en train (~80%), val (~10%), test (~10%).
    Estrategia de partición balanceada por locutor y tipo de audio.
    """
    random.seed(seed)

    # Agrupar por (tipo, id_lexico) para asegurar que diferentes tomas
    # se distribuyan de forma equilibrada o agrupada
    grupos_por_item = defaultdict(list)
    for entry in manifest_entries:
        key = (entry["tipo"], entry["id_lexico"])
        grupos_por_item[key].append(entry)

    train_list = []
    val_list = []
    test_list = []

    for key, entries in grupos_por_item.items():
        # Si hay 3 tomas por item: toma 1 y 2 van a train, toma 3 se alterna entre val y test
        # Si hay 2 tomas: 1 a train, 1 a val/test
        # Si hay 1 toma: va a train con 80% prob, val 10%, test 10%
        random.shuffle(entries)
        n = len(entries)
        if n >= 3:
            train_list.extend(entries[:n-2])
            val_list.append(entries[-2])
            test_list.append(entries[-1])
        elif n == 2:
            train_list.append(entries[0])
            if random.random() < 0.5:
                val_list.append(entries[1])
            else:
                test_list.append(entries[1])
        else:
            r = random.random()
            if r < 0.80:
                train_list.append(entries[0])
            elif r < 0.90:
                val_list.append(entries[0])
            else:
                test_list.append(entries[0])

    return train_list, val_list, test_list


def exportar_formato_kaldi(split_name: str, entries: list, out_dir: str):
    """Genera los archivos wav.scp, text, utt2spk, spk2utt requeridos por Kaldi / Sherpa."""
    dir_split = os.path.join(out_dir, split_name)
    os.makedirs(dir_split, exist_ok=True)

    entries_sorted = sorted(entries, key=lambda x: x["utt_id"])

    # 1. wav.scp
    with open(os.path.join(dir_split, "wav.scp"), "w", encoding="utf-8") as f:
        for e in entries_sorted:
            f.write(f"{e['utt_id']}\t{e['audio_path']}\n")

    # 2. text (transcripción fonética por defecto para CTC basado en fonemas)
    with open(os.path.join(dir_split, "text"), "w", encoding="utf-8") as f:
        for e in entries_sorted:
            f.write(f"{e['utt_id']}\t{e['fonemas']}\n")

    # 3. text_words (transcripción textual ortográfica)
    with open(os.path.join(dir_split, "text_words"), "w", encoding="utf-8") as f:
        for e in entries_sorted:
            f.write(f"{e['utt_id']}\t{e['texto_uch']}\n")

    # 4. utt2spk
    spk2utt = defaultdict(list)
    with open(os.path.join(dir_split, "utt2spk"), "w", encoding="utf-8") as f:
        for e in entries_sorted:
            f.write(f"{e['utt_id']}\t{e['locutor']}\n")
            spk2utt[e['locutor']].append(e['utt_id'])

    # 5. spk2utt
    with open(os.path.join(dir_split, "spk2utt"), "w", encoding="utf-8") as f:
        for spk in sorted(spk2utt.keys()):
            utts_str = " ".join(sorted(spk2utt[spk]))
            f.write(f"{spk}\t{utts_str}\n")


def main():
    print("=" * 70)
    print("PREPARACIÓN DE DATASET Y PARTICIONES ASR UCHUMATAQU")
    print("=" * 70)

    ruta_palabras_xlsx = os.path.join(project_root, "excel", "palabras_pln.xlsx")
    ruta_oraciones_xlsx = os.path.join(project_root, "excel", "oraciones.xlsx")

    dir_manifests = os.path.join(asr_dir, "data", "manifests")
    dir_kaldi = os.path.join(dir_manifests, "kaldi")
    os.makedirs(dir_manifests, exist_ok=True)
    os.makedirs(dir_kaldi, exist_ok=True)

    # 1. Cargar fuentes léxicas
    palabras_map, oraciones_map = cargar_diccionarios_pln(ruta_palabras_xlsx, ruta_oraciones_xlsx)
    print(f"Cargadas {len(palabras_map)} palabras y {len(oraciones_map)} oraciones de referencia.")

    # 2. Recolectar audios y construir manifiesto general
    entries = recolectar_audios(palabras_map, oraciones_map)
    total_audios = len(entries)
    duracion_total = sum(e["duracion"] for e in entries)
    print(f"Total audios recolectados y validados: {total_audios}")
    print(f"Duración total del corpus acústico: {duracion_total:.2f} s ({duracion_total / 60.0:.2f} min)")

    # 3. Particionar dataset
    train_list, val_list, test_list = particionar_dataset(entries, seed=42)
    print(f"\nParticiones generadas:")
    print(f"  • Train: {len(train_list)} audios ({sum(e['duracion'] for e in train_list):.1f} s, {len(train_list)/total_audios*100:.1f}%)")
    print(f"  • Val:   {len(val_list)} audios ({sum(e['duracion'] for e in val_list):.1f} s, {len(val_list)/total_audios*100:.1f}%)")
    print(f"  • Test:  {len(test_list)} audios ({sum(e['duracion'] for e in test_list):.1f} s, {len(test_list)/total_audios*100:.1f}%)")

    # 4. Guardar manifests en JSON
    archivos_json = {
        "all_manifest.json": entries,
        "train_manifest.json": train_list,
        "val_manifest.json": val_list,
        "test_manifest.json": test_list
    }
    for fname, data in archivos_json.items():
        r_json = os.path.join(dir_manifests, fname)
        with open(r_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Generado: {r_json}")

    # 5. Exportar manifests en formato Kaldi
    exportar_formato_kaldi("train", train_list, dir_kaldi)
    exportar_formato_kaldi("val", val_list, dir_kaldi)
    exportar_formato_kaldi("test", test_list, dir_kaldi)
    print(f"[OK] Exportados manifests formato Kaldi en: {dir_kaldi}")

    print("\n" + "=" * 70)
    print("DATASET ASR PREPARADO EXITOSAMENTE")
    print("=" * 70)


if __name__ == "__main__":
    main()
