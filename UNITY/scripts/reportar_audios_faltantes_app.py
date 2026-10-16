#!/usr/bin/env python3
"""
reportar_audios_faltantes_app.py
1. Identifica las palabras que faltan para la app móvil según UNITY/reportes/reporte_audios_app.txt.
2. Busca todas las grabaciones y tomas disponibles en cada locutor de ASR/audios_palabras/{locutor}/.
3. Genera un reporte detallado en UNITY/reportes/audios_faltantes_disponibles_locutores.txt.
4. Copia todas las tomas encontradas de todos los autores a una única carpeta de revisión
   (por defecto: audios_faltantes_revision/), con nombres ordenados por palabra y locutor
   (ejemplo: {palabra}__{locutor}_{toma}.wav), para que el usuario pueda escuchar,
   comparar y seleccionar cómodamente la mejor grabación para la app.

Uso:
  python3 UNITY/scripts/reportar_audios_faltantes_app.py
  python3 UNITY/scripts/reportar_audios_faltantes_app.py --destino mi_carpeta_audios/
  python3 UNITY/scripts/reportar_audios_faltantes_app.py --sin-copiar
"""

import os
import re
import sys
import shutil
import argparse
import glob
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNITY_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(UNITY_DIR)

REPORT_APP_FILE = os.path.join(UNITY_DIR, "reportes", "reporte_audios_app.txt")
ASR_PALABRAS_DIR = os.path.join(PROJECT_ROOT, "ASR", "audios_palabras")
DEFAULT_OUT_REPORT = os.path.join(UNITY_DIR, "reportes", "audios_faltantes_disponibles_locutores.txt")
DEFAULT_DESTINO_DIR = os.path.join(PROJECT_ROOT, "audios_faltantes_revision")

ALL_LOCUTORES = ["eva", "pedro", "sofia", "lorenzo", "roberto"]

# Variantes o alias ortográficos conocidos entre Excel y ASR
ALIASES = {
    "irohito_urus": ["irohito", "irohitourus"],
}


def obtener_palabras_faltantes_del_reporte(ruta_reporte: str) -> list:
    """Extrae la lista de palabras faltantes con sus metadatos desde la sección 1 del reporte."""
    if not os.path.exists(ruta_reporte):
        return []

    with open(ruta_reporte, "r", encoding="utf-8") as f:
        contenido = f.read()

    patron = r"1\.\s*PALABRAS EN EXCEL QUE FALTAN EN.*?\(\d+\)(.*?)2\."
    match = re.search(patron, contenido, re.DOTALL)
    if not match:
        return []

    bloque = match.group(1).strip()
    lineas = bloque.split("\n")

    faltantes = []
    for line in lineas:
        line_clean = line.rstrip()
        if not line_clean or line_clean.startswith("ID") or line_clean.startswith("-") or line_clean.startswith("="):
            continue
        if "¡100% de palabras tienen su archivo de audio" in line_clean:
            continue
        
        # Columnas fijas del reporte:
        # ID: cols 0..31, UCHUMATAQU: cols 31..57, ESPAÑOL: cols 57..83, CATEGORÍA: cols 83..
        word_id = line_clean[:31].strip().lower()
        uchu = line_clean[31:57].strip() if len(line_clean) > 31 else word_id
        esp = line_clean[57:83].strip() if len(line_clean) > 57 else ""
        cat = line_clean[83:].strip() if len(line_clean) > 83 else ""

        if word_id:
            faltantes.append({
                "id": word_id,
                "uchumataqu": uchu,
                "espanol": esp,
                "categoria": cat
            })

    return faltantes


def buscar_grabaciones_locutores(word_id: str, asr_dir: str) -> dict:
    """
    Busca todas las tomas disponibles para un word_id en cada locutor de ASR/audios_palabras/.
    Retorna un diccionario {locutor: [lista de archivos .wav encontrados]}.
    """
    hallazgos = {}
    
    locutores_existentes = sorted(
        d for d in os.listdir(asr_dir) 
        if os.path.isdir(os.path.join(asr_dir, d)) and not d.startswith(".")
    ) if os.path.exists(asr_dir) else []

    nombres_a_buscar = [word_id]
    if word_id in ALIASES:
        nombres_a_buscar.extend(ALIASES[word_id])

    for locutor in locutores_existentes:
        loc_dir = os.path.join(asr_dir, locutor)
        tomas_encontradas = []

        for name in nombres_a_buscar:
            patrones = [
                os.path.join(loc_dir, f"{name}_*.wav"),
                os.path.join(loc_dir, f"{name}.wav")
            ]
            for p in patrones:
                for match in glob.glob(p):
                    if os.path.getsize(match) > 1000:
                        bname = os.path.basename(match)
                        if bname not in [os.path.basename(x) for x in tomas_encontradas]:
                            tomas_encontradas.append(match)

        if tomas_encontradas:
            tomas_encontradas.sort()
            hallazgos[locutor] = tomas_encontradas

    return hallazgos


def extraer_sufijo_toma(nombre_archivo: str) -> str:
    """Extrae el sufijo de toma de un nombre de archivo (ej. '01', '02') o '01' si no tiene."""
    base = os.path.splitext(nombre_archivo)[0]
    match = re.search(r'_(\d+)$', base)
    if match:
        return match.group(1).zfill(2)
    return "01"


def copiar_audios_para_revision(resultados: list, destino_dir: str) -> int:
    """
    Copia todos los audios encontrados de todos los locutores a destino_dir,
    nombrándolos como: {word_id}__{locutor}_{toma}.wav
    para que se ordenen juntos alfabéticamente por palabra en el reproductor.
    Genera también un archivo 00_INDICE_AUDIOS.txt con la guía de palabras y significados.
    """
    os.makedirs(destino_dir, exist_ok=True)
    total_copiados = 0

    lineas_indice = [
        "=" * 95,
        "ÍNDICE DE AUDIOS PARA REVISIÓN Y ESCUCHA (AUDIOS FALTANTES APP)",
        "=" * 95,
        f"Carpeta: {destino_dir}",
        "Formato de nombres: {id_palabra}__{locutor}_{toma}.wav",
        "Ejemplo: achasi__eva_01.wav, achasi__pedro_01.wav, achasi__sofia_01.wav",
        "=" * 95,
        f"{'#':<3} {'ID':<18} {'UCHUMATAQU':<20} {'ESPAÑOL':<20} {'AUDIOS DISPONIBLES EN ESTA CARPETA'}",
        "-" * 95,
    ]

    for idx, item in enumerate(resultados, start=1):
        w_id = item["id"]
        uchu = item["uchumataqu"]
        esp = item["espanol"]
        locs = item["locutores"]

        archivos_generados = []

        if locs:
            for locutor, rutas in locs.items():
                for ruta_src in rutas:
                    toma = extraer_sufijo_toma(os.path.basename(ruta_src))
                    nuevo_nombre = f"{w_id}__{locutor}_{toma}.wav"
                    ruta_dst = os.path.join(destino_dir, nuevo_nombre)

                    shutil.copy2(ruta_src, ruta_dst)
                    total_copiados += 1
                    archivos_generados.append(nuevo_nombre)

            resumen_archivos = f"{len(archivos_generados)} tomas ({', '.join(locs.keys())})"
        else:
            resumen_archivos = "❌ Sin audio"

        lineas_indice.append(f"{idx:<3} {w_id:<18} {uchu[:19]:<20} {esp[:19]:<20} {resumen_archivos}")

    lineas_indice.append("=" * 95)
    lineas_indice.append(f"Total archivos .wav copiados: {total_copiados}")
    lineas_indice.append("=" * 95)

    ruta_indice = os.path.join(destino_dir, "00_INDICE_AUDIOS.txt")
    with open(ruta_indice, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas_indice))

    return total_copiados


def main():
    parser = argparse.ArgumentParser(
        description="Reporta y reúne los audios de palabras faltantes de la app en una sola carpeta para escucha y selección."
    )
    parser.add_argument("--reporte-app", default=REPORT_APP_FILE, help="Ruta al reporte de audios de la app")
    parser.add_argument("--asr-dir", default=ASR_PALABRAS_DIR, help="Ruta a ASR/audios_palabras")
    parser.add_argument("--salida-reporte", default=DEFAULT_OUT_REPORT, help="Archivo donde guardar el reporte de texto")
    parser.add_argument("--destino", default=DEFAULT_DESTINO_DIR, help="Carpeta donde se copiarán todos los audios juntos")
    parser.add_argument("--sin-copiar", action="store_true", help="Solo genera el reporte de texto sin copiar audios")
    args = parser.parse_args()

    faltantes_items = obtener_palabras_faltantes_del_reporte(args.reporte_app)
    if not faltantes_items:
        print(f"[INFO] No se encontraron palabras faltantes en {args.reporte_app} o el archivo no existe.")
        return

    conteo_por_locutor = defaultdict(int)
    total_con_al_menos_un_locutor = 0
    resultados = []

    for item in faltantes_items:
        w_id = item["id"]
        locs_audio = buscar_grabaciones_locutores(w_id, args.asr_dir)
        
        if locs_audio:
            total_con_al_menos_un_locutor += 1
            for loc in locs_audio.keys():
                conteo_por_locutor[loc] += 1

        resultados.append({
            "id": w_id,
            "uchumataqu": item["uchumataqu"],
            "espanol": item["espanol"],
            "categoria": item["categoria"],
            "locutores": locs_audio
        })

    # Construir reporte de texto
    lineas = []
    lineas.append("=" * 95)
    lineas.append("REPORTE DE AUDIOS DISPONIBLES EN LOCUTORES ASR PARA PALABRAS FALTANTES DE LA APP")
    lineas.append("=" * 95)
    lineas.append(f"Total palabras faltantes en la App : {len(faltantes_items)}")
    lineas.append(f"Palabras con audio en algún locutor: {total_con_al_menos_un_locutor} / {len(faltantes_items)} ({(total_con_al_menos_un_locutor/len(faltantes_items)*100):.1f}%)")
    lineas.append(f"Palabras sin ningún audio grabado  : {len(faltantes_items) - total_con_al_menos_un_locutor}")
    lineas.append("\nDisponibilidad por locutor:")
    for loc in sorted(conteo_por_locutor.keys()):
        lineas.append(f"  • {loc.upper():<10}: {conteo_por_locutor[loc]} palabras disponibles")

    lineas.append("\n" + "=" * 95)
    lineas.append("DETALLE DE PALABRAS FALTANTES Y LOCUTORES QUE LAS TIENEN GRABADAS")
    lineas.append("=" * 95)
    lineas.append(f"{'#':<3} {'ID':<18} {'UCHUMATAQU':<20} {'ESPAÑOL':<20} {'LOCUTORES DISPONIBLES Y TOMAS'}")
    lineas.append("-" * 95)

    for idx, item in enumerate(resultados, start=1):
        w_id = item["id"]
        uchu = item["uchumataqu"][:19]
        esp = item["espanol"][:19]
        locs = item["locutores"]

        if not locs:
            detalle_locs = "❌ SIN AUDIO EN NINGÚN LOCUTOR"
        else:
            resumen_locs = []
            for loc, paths in locs.items():
                tomas_str = ", ".join([os.path.basename(p).replace(f"{w_id}_", "").replace(".wav", "") for p in paths])
                resumen_locs.append(f"{loc}({len(paths)} tomas: {tomas_str})")
            detalle_locs = " | ".join(resumen_locs)

        lineas.append(f"{idx:<3} {w_id:<18} {uchu:<20} {esp:<20} {detalle_locs}")

    lineas.append("\n" + "=" * 95)
    lineas.append("RUTAS COMPLETAS DE CADA TOMA DISPONIBLE PARA ESCUCHA Y VERIFICACIÓN")
    lineas.append("=" * 95)

    for idx, item in enumerate(resultados, start=1):
        w_id = item["id"]
        locs = item["locutores"]
        lineas.append(f"\n[{idx:02d}] ID: {w_id} ({item['uchumataqu']} - {item['espanol']})")
        if not locs:
            lineas.append("    ❌ No hay audios disponibles en ninguna carpeta de locutor.")
        else:
            for loc, paths in locs.items():
                lineas.append(f"    🎤 Locutor: {loc.upper()} ({len(paths)} tomas)")
                for p in paths:
                    rel_path = os.path.relpath(p, PROJECT_ROOT)
                    lineas.append(f"       -> {rel_path}")

    lineas.append("\n" + "=" * 95)
    lineas.append("Fin del reporte.")
    lineas.append("=" * 95)

    reporte_texto = "\n".join(lineas)

    # Guardar reporte en archivo
    os.makedirs(os.path.dirname(args.salida_reporte), exist_ok=True)
    with open(args.salida_reporte, "w", encoding="utf-8") as f:
        f.write(reporte_texto)

    print(reporte_texto)
    print(f"\n📄 Reporte guardado en: {args.salida_reporte}")

    # Copiar audios a la carpeta de revisión
    if not args.sin_copiar:
        print("\n" + "=" * 95)
        print(f"📁 COPIANDO TODOS LOS AUDIOS Y REPETICIONES A LA CARPETA DE REVISIÓN...")
        print(f"   Destino: {args.destino}")
        print("=" * 95)

        total_copiados = copiar_audios_para_revision(resultados, args.destino)

        print(f"✅ ¡Copia completada con éxito!")
        print(f"   • Total de archivos copiados : {total_copiados} tomas de audio")
        print(f"   • Carpeta de destino         : {args.destino}")
        print(f"   • Guía e índice generado en  : {os.path.join(args.destino, '00_INDICE_AUDIOS.txt')}")
        print("=" * 95)


if __name__ == "__main__":
    main()
