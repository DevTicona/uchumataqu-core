#!/usr/bin/env python3
"""
completar_audios_app.py
Copia los audios seleccionados y revisados desde 'audios_faltantes_revision/'
hacia la carpeta de la aplicación móvil 'UNITY/audios_palabras/'.

Antes de copiar, normaliza y limpia los nombres eliminando el sufijo de locutor
y número de repetición (ej. 'chuwicha__eva_01.wav' -> 'chuwicha.wav').

Uso:
  python3 UNITY/scripts/completar_audios_app.py
  python3 UNITY/scripts/completar_audios_app.py --dry-run
  python3 UNITY/scripts/completar_audios_app.py --revision-dir audios_faltantes_revision --output-dir UNITY/audios_palabras
"""

import os
import re
import sys
import shutil
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNITY_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(UNITY_DIR)

DEFAULT_REVISION_DIR = os.path.join(PROJECT_ROOT, "audios_faltantes_revision")
DEFAULT_OUTPUT_DIR = os.path.join(UNITY_DIR, "audios_palabras")
REPORT_FILE = os.path.join(UNITY_DIR, "reportes", "reporte_audios_app.txt")
ASR_PALABRAS_DIR = os.path.join(PROJECT_ROOT, "ASR", "audios_palabras")
VERIFICAR_SCRIPT = os.path.join(SCRIPT_DIR, "verificar_audios_app.py")

DEFAULT_PRIORITY = ["eva", "pedro", "sofia", "lorenzo", "roberto"]

# Mapeo de alias conocidos si se busca en ASR como fallback
ALIASES = {
    "irohito_urus": ["irohito", "irohitourus"],
}


def limpiar_nombre_audio(nombre_archivo: str) -> tuple:
    """
    Dado un nombre de archivo como 'chuwicha__eva_01.wav' o 'chatuchay.wav',
    retorna (palabra_id, nombre_limpio, info_locutor).
    Ejemplo:
      'chuwicha__eva_01.wav' -> ('chuwicha', 'chuwicha.wav', 'eva_01')
      'chatuchay.wav'        -> ('chatuchay', 'chatuchay.wav', 'directo')
    """
    base, ext = os.path.splitext(nombre_archivo)
    if ext.lower() != ".wav":
        return None, None, None

    if "__" in base:
        partes = base.split("__", 1)
        palabra_id = partes[0].strip().lower()
        info_locutor = partes[1].strip()
    else:
        palabra_id = base.strip().lower()
        info_locutor = "directo"

    nombre_limpio = f"{palabra_id}.wav"
    return palabra_id, nombre_limpio, info_locutor


def obtener_palabras_faltantes_del_reporte(ruta_reporte: str) -> list:
    """Extrae la lista de IDs de palabras faltantes desde la Sección 1 del reporte."""
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

    ids_faltantes = []
    for line in lineas:
        line = line.strip()
        if not line or line.startswith("ID") or line.startswith("-") or line.startswith("="):
            continue
        if "¡100% de palabras tienen su archivo de audio" in line:
            continue
        partes = line.split()
        if partes:
            word_id = partes[0].strip().lower()
            if word_id not in ids_faltantes:
                ids_faltantes.append(word_id)

    return ids_faltantes


def buscar_audio_en_asr(word_id: str, locutores: list, asr_dir: str) -> tuple:
    """Busca audio en ASR como fallback en caso de palabras no seleccionadas aún."""
    candidatos_nombres = [
        f"{word_id}_01.wav",
        f"{word_id}_02.wav",
        f"{word_id}_03.wav",
        f"{word_id}_04.wav",
        f"{word_id}.wav",
    ]
    if word_id in ALIASES:
        for alias in ALIASES[word_id]:
            candidatos_nombres.extend([
                f"{alias}_01.wav",
                f"{alias}_02.wav",
                f"{alias}_03.wav",
                f"{alias}_04.wav",
                f"{alias}.wav",
            ])

    for locutor in locutores:
        loc_dir = os.path.join(asr_dir, locutor)
        if not os.path.isdir(loc_dir):
            continue
        for nombre_cand in candidatos_nombres:
            ruta_cand = os.path.join(loc_dir, nombre_cand)
            if os.path.exists(ruta_cand) and os.path.getsize(ruta_cand) > 1000:
                return ruta_cand, locutor, nombre_cand

    return None, None, None


def main():
    parser = argparse.ArgumentParser(
        description="Copia audios seleccionados de audios_faltantes_revision a UNITY/audios_palabras limpiando sus nombres"
    )
    parser.add_argument(
        "--revision-dir",
        default=DEFAULT_REVISION_DIR,
        help="Carpeta donde están los audios seleccionados (default: audios_faltantes_revision)"
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta destino de audios para la app (default: UNITY/audios_palabras)"
    )
    parser.add_argument(
        "--reporte",
        default=REPORT_FILE,
        help="Ruta al reporte de audios (UNITY/reportes/reporte_audios_app.txt)"
    )
    parser.add_argument(
        "--completar-asr-pendientes",
        action="store_true",
        help="Si falta alguna palabra en la revisión, buscarla automáticamente en ASR/audios_palabras"
    )
    parser.add_argument(
        "--prioridad",
        default=",".join(DEFAULT_PRIORITY),
        help="Prioridad de locutores para fallback ASR (ej: eva,pedro,sofia)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué archivos se copiarían sin modificar el disco"
    )
    parser.add_argument(
        "--sin-verificar",
        action="store_true",
        help="No ejecuta verificar_audios_app.py tras completar los audios"
    )

    args = parser.parse_args()

    print("=" * 90)
    print("🔄 COPIADOR Y NORMALIZADOR DE AUDIOS SELECCIONADOS PARA LA APP")
    print("=" * 90)
    print(f"  Carpeta origen (Revisión) : {args.revision_dir}")
    print(f"  Carpeta destino (Unity)   : {args.output_dir}")
    if args.dry_run:
        print("  MODO                      : SIMULACIÓN (--dry-run)")
    print("=" * 90)

    if not os.path.isdir(args.revision_dir):
        print(f"[INFO] No se encontró el directorio de revisión: {args.revision_dir}")
        print("       (Es normal si ya se procesaron y eliminaron las revisiones temporales).")
        archivos_revision = []
    else:
        # 1. Obtener archivos de audio .wav de la carpeta de revisión
        archivos_revision = sorted([
            f for f in os.listdir(args.revision_dir)
            if f.lower().endswith(".wav") and not f.startswith(".")
        ])

    if not archivos_revision and not args.completar_asr_pendientes:
        print(f"[INFO] No hay archivos .wav pendientes en {args.revision_dir} para copiar.")
        return

    print(f"\n[INFO] Se encontraron {len(archivos_revision)} audios seleccionados para copiar.\n")
    print(f"{'#':<4} {'ARCHIVO EN REVISIÓN':<32} {'->':<3} {'NOMBRE FINAL':<25} {'ORIGEN/TOMA':<15} {'ESTADO'}")
    print("-" * 90)

    palabras_copiadas = set()
    copiados = 0

    for idx, f_name in enumerate(archivos_revision, 1):
        palabra_id, nombre_limpio, info_locutor = limpiar_nombre_audio(f_name)
        if not nombre_limpio:
            continue

        ruta_origen = os.path.join(args.revision_dir, f_name)
        ruta_destino = os.path.join(args.output_dir, nombre_limpio)

        estado = "SIMULADO" if args.dry_run else "COPIADO"
        print(f"{idx:<4} {f_name:<32} ->  {nombre_limpio:<25} {info_locutor:<15} {estado}")

        if not args.dry_run:
            shutil.copy2(ruta_origen, ruta_destino)

        palabras_copiadas.add(palabra_id)
        copiados += 1

    # 2. Cotejar con reporte si existe
    faltantes_reporte = obtener_palabras_faltantes_del_reporte(args.reporte)
    pendientes_totales = [w for w in faltantes_reporte if w not in palabras_copiadas]

    # Fallback ASR opcional si el usuario lo activa
    completados_asr = 0
    if args.completar_asr_pendientes and pendientes_totales and os.path.isdir(ASR_PALABRAS_DIR):
        prioridad_loc = [p.strip().lower() for p in args.prioridad.split(",") if p.strip()]
        print("\n" + "-" * 90)
        print("[INFO] Buscando palabras pendientes en ASR como fallback...")
        print("-" * 90)
        for w in list(pendientes_totales):
            r_origen, loc, n_arch = buscar_audio_en_asr(w, prioridad_loc, ASR_PALABRAS_DIR)
            if r_origen:
                dest_file = f"{w}.wav"
                dest_p = os.path.join(args.output_dir, dest_file)
                estado = "SIMULADO (ASR)" if args.dry_run else "COPIADO (ASR)"
                print(f"  • {w:<20} -> {dest_file:<20} {loc} ({n_arch}) [{estado}]")
                if not args.dry_run:
                    shutil.copy2(r_origen, dest_p)
                pendientes_totales.remove(w)
                completados_asr += 1

    print("\n" + "=" * 90)
    print("RESUMEN DE PROCESAMIENTO:")
    print(f"  • Audios seleccionados copiados desde revisión : {copiados}")
    if args.completar_asr_pendientes:
        print(f"  • Audios completados desde fallback ASR       : {completados_asr}")
    if faltantes_reporte:
        print(f"  • Faltantes reportados originalmente         : {len(faltantes_reporte)}")
        print(f"  • Faltantes restantes sin audio              : {len(pendientes_totales)}")
        if pendientes_totales:
            print(f"    Pendientes: {', '.join(pendientes_totales)}")
    print("=" * 90)

    # 3. Actualizar reporte de la app automáticamente ejecutando verificar_audios_app.py
    if not args.dry_run and not args.sin_verificar and os.path.exists(VERIFICAR_SCRIPT):
        print("\n[INFO] Actualizando reporte de verificación (verificar_audios_app.py)...")
        try:
            res = subprocess.run([sys.executable, VERIFICAR_SCRIPT], capture_output=True, text=True)
            if res.returncode == 0:
                print("  ✅ Reporte de audios de la app actualizado exitosamente.")
            else:
                print(f"  ⚠️ Advertencia al ejecutar verificar_audios_app.py:\n{res.stderr}")
        except Exception as e:
            print(f"  ⚠️ No se pudo ejecutar verificar_audios_app.py: {e}")

    print("\n[OK] Proceso finalizado.")


if __name__ == "__main__":
    main()
