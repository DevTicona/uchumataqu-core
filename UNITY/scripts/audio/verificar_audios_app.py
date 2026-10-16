#!/usr/bin/env python3
"""
verificar_audios_app.py
Verificación exhaustiva de audios para la Aplicación Móvil (Unity) y normalización de volumen.

Compara los archivos de audio en:
  - UNITY/audios_palabras/  -> contra ID de excel/palabras_app.xlsx
  - UNITY/audios_oraciones/ -> contra columna Uchumataqu normalizada a slug de excel/oraciones.xlsx

Genera un reporte detallado en UNITY/reportes/reporte_audios_app.txt indicando:
  - Audios presentes y faltantes.
  - Elementos sobrantes en Excel (sin audio).
  - Archivos de audio sobrantes en carpetas (sin correspondencia en Excel).

Posteriormente, normaliza el volumen pico de todos los audios individuales (palabras y oraciones)
al estándar de -3 dBFS utilizando SoX o ffmpeg.

Uso:
  python3 UNITY/scripts/verificar_audios_app.py
  python3 UNITY/scripts/verificar_audios_app.py --dry-run
  python3 UNITY/scripts/verificar_audios_app.py --sin-normalizar
  python3 UNITY/scripts/verificar_audios_app.py --target-db -3.0
"""

import os
import re
import sys
import shutil
import argparse
import subprocess
import unicodedata

script_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(script_dir)
unity_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(unity_dir)

if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
try:
    from UNITY.scripts.corpus.lector_xlsx import leer_xlsx
except ImportError:
    try:
        from corpus.lector_xlsx import leer_xlsx
    except ImportError:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("lector_xlsx", os.path.join(scripts_dir, "corpus", "lector_xlsx.py"))
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        leer_xlsx = _mod.leer_xlsx

EXCEL_DIR = os.path.join(project_root, "excel")
OUTPUT_FILE = os.path.join(unity_dir, "reportes", "reporte_audios_app.txt")


def normalizar_oracion_slug(texto: str) -> str:
    """
    Normaliza el texto en Uchumataqu a formato slug para matching con audios.
    Ejemplo: 'Wilk chhuñiqasi, uwapinichay, amthü' -> 'wilk_chhuniqasi_uwapinichay_amthu'
    """
    if not texto:
        return ""
    # 1. Descomponer diacríticos Unicode (tildes, diéresis, etc.)
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # 2. Eliminar apóstrofes y eyectivas (no generan guion bajo)
    t = re.sub(r"['ʼ`´\^]", "", t)
    # 3. Reemplazar signos de puntuación por espacios
    t = re.sub(r'[¿?!¡.,;:\"()_\-]', " ", t)
    # 4. Minúsculas, recortar y convertir espacios a '_'
    t = t.strip().lower()
    return re.sub(r"\s+", "_", t)


def generar_variantes_slug_oracion(uch_texto: str) -> set:
    """Genera variantes de slug para matching robusto de nombres de archivo de oraciones."""
    base = normalizar_oracion_slug(uch_texto)
    variantes = {base}
    # Variantes con palabras compuestas unidas frecuentemente encontradas en grabaciones
    compacto = (
        base.replace("irohito_urus", "irohitourus")
        .replace("chhuni_pichuchay", "chhunipichuchay")
        .replace("thuni_seschay", "thuniseschay")
        .replace("ti_wiyanichay", "tiwiyanichay")
        .replace("wilk_tho", "wilktho")
        .replace("chhuni_pichu", "chhunipichu")
    )
    variantes.add(compacto)
    return variantes


def cargar_palabras_app(ruta_excel: str) -> list:
    """Carga todas las unidades léxicas de palabras_app.xlsx usando su ID como clave principal."""
    rows = leer_xlsx(ruta_excel)
    palabras = []
    for r in rows[1:]:
        if len(r) > 0 and r[0]:
            pid = r[0].strip().lower()
            uch = r[1].strip() if len(r) > 1 else ""
            es = r[2].strip() if len(r) > 2 else ""
            cat = r[3].strip() if len(r) > 3 else ""
            # Variantes de ID (ej: thuni_seschay y thuniseschay)
            variantes_id = {pid, pid.replace("_", "")}
            palabras.append({
                "id": pid,
                "uch": uch,
                "es": es,
                "categoria": cat,
                "variantes_id": variantes_id
            })
    return palabras


def cargar_oraciones_app(ruta_excel: str) -> list:
    """Carga las 130 oraciones de oraciones.xlsx normalizando la columna Uchumataqu."""
    rows = leer_xlsx(ruta_excel)
    oraciones = []
    for r in rows[1:]:
        if len(r) > 0 and r[0]:
            oid = r[0].strip()
            uch = r[1].strip() if len(r) > 1 else ""
            es = r[2].strip() if len(r) > 2 else ""
            lec = r[3].strip() if len(r) > 3 else ""

            try:
                num = int(oid.replace("O_", ""))
                es_reserva = num > 120
            except:
                es_reserva = False

            slug_principal = normalizar_oracion_slug(uch)
            slugs_variantes = generar_variantes_slug_oracion(uch) | {oid.lower()}

            oraciones.append({
                "id": oid,
                "uch": uch,
                "es": es,
                "leccion": lec,
                "es_reserva": es_reserva,
                "slug_principal": slug_principal,
                "slugs": slugs_variantes
            })
    return oraciones


def indexar_archivos_carpeta(directorio: str) -> dict:
    """
    Indexa archivos .wav asociando la base del archivo y la base limpia sin sufijo de locutor (_01, _02).
    """
    if not os.path.exists(directorio):
        return {}
    archivos = {}
    for f in os.listdir(directorio):
        if f.lower().endswith(".wav") and not f.endswith(":Zone.Identifier"):
            base = os.path.splitext(f)[0].lower()
            base_limpio = re.sub(r"_0[1-9]$", "", base)
            archivos[base] = f
            archivos[base_limpio] = f
    return archivos


def normalizar_audio_a_db(ruta_archivo: str, target_db: float = -3.0, dry_run: bool = False) -> bool:
    """
    Normaliza el volumen pico de un archivo WAV a target_db (ej: -3.0 dBFS).
    Usa SoX si está disponible (óptimo y sin pérdidas) o ffmpeg como fallback.
    """
    if dry_run:
        return True

    ruta_tmp = f"{ruta_archivo}.tmp.wav"

    # 1. SoX (norm -3)
    if shutil.which("sox"):
        cmd = ["sox", ruta_archivo, ruta_tmp, "norm", str(target_db)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(ruta_tmp) and os.path.getsize(ruta_tmp) > 100:
                os.replace(ruta_tmp, ruta_archivo)
                return True
        except Exception:
            pass

    # 2. Fallback con ffmpeg
    if shutil.which("ffmpeg"):
        cmd_measure = [
            "ffmpeg", "-hide_banner", "-i", ruta_archivo,
            "-af", "volumedetect", "-f", "null", "/dev/null"
        ]
        try:
            res_m = subprocess.run(cmd_measure, capture_output=True, text=True)
            match = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", res_m.stderr)
            if match:
                max_vol = float(match.group(1))
                diff = target_db - max_vol
                if abs(diff) < 0.1:
                    return True
                gain_str = f"{diff:+.2f}dB"
                cmd_norm = [
                    "ffmpeg", "-y", "-loglevel", "error", "-i", ruta_archivo,
                    "-af", f"volume={gain_str}",
                    "-c:a", "pcm_s16le", ruta_tmp
                ]
                res_n = subprocess.run(cmd_norm, capture_output=True, text=True)
                if res_n.returncode == 0 and os.path.exists(ruta_tmp) and os.path.getsize(ruta_tmp) > 100:
                    os.replace(ruta_tmp, ruta_archivo)
                    return True
        except Exception:
            pass

    if os.path.exists(ruta_tmp):
        try:
            os.remove(ruta_tmp)
        except OSError:
            pass

    return False


def normalizar_volumen_directorio(directorio: str, target_db: float = -3.0, dry_run: bool = False) -> tuple:
    """
    Normaliza todos los archivos .wav de un directorio a target_db.
    Retorna (total_archivos, exitosos).
    """
    if not os.path.exists(directorio):
        return 0, 0

    archivos = sorted([
        f for f in os.listdir(directorio)
        if f.lower().endswith(".wav") and not f.endswith(":Zone.Identifier") and not f.startswith(".")
    ])

    exitosos = 0
    for f in archivos:
        ruta = os.path.join(directorio, f)
        if normalizar_audio_a_db(ruta, target_db=target_db, dry_run=dry_run):
            exitosos += 1

    return len(archivos), exitosos


def main():
    parser = argparse.ArgumentParser(
        description="Verifica los audios de la app (palabras y oraciones) y normaliza su volumen a -3dB."
    )
    parser.add_argument(
        "--target-db",
        type=float,
        default=-3.0,
        help="Nivel de normalización de pico en dBFS (default: -3.0 dB)"
    )
    parser.add_argument(
        "--sin-normalizar",
        action="store_true",
        help="Solo ejecuta la verificación y reporte sin modificar el volumen de los audios"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la normalización sin modificar los archivos en disco"
    )

    args = parser.parse_args()

    ruta_palabras = os.path.join(EXCEL_DIR, "palabras_app.xlsx")
    ruta_oraciones = os.path.join(EXCEL_DIR, "oraciones.xlsx")
    dir_palabras = os.path.join(unity_dir, "audios_palabras")
    dir_oraciones = os.path.join(unity_dir, "audios_oraciones")

    palabras_excel = cargar_palabras_app(ruta_palabras)
    oraciones_excel = cargar_oraciones_app(ruta_oraciones)

    audios_palabras = indexar_archivos_carpeta(dir_palabras)
    audios_oraciones = indexar_archivos_carpeta(dir_oraciones)

    # 1. Análisis de Palabras App (Cruce por ID)
    palabras_presentes = []
    palabras_faltantes = []
    archivos_usados_palabras = set()

    for p in palabras_excel:
        match_audio = None
        for vid in p["variantes_id"]:
            if vid in audios_palabras:
                match_audio = audios_palabras[vid]
                archivos_usados_palabras.add(match_audio)
                break
        if match_audio:
            palabras_presentes.append((p, match_audio))
        else:
            palabras_faltantes.append(p)

    archivos_palabras_reales = sorted([
        f for f in os.listdir(dir_palabras)
        if f.lower().endswith(".wav") and not f.endswith(":Zone.Identifier")
    ]) if os.path.exists(dir_palabras) else []

    audios_palabras_sobrantes = sorted([
        f for f in archivos_palabras_reales if f not in archivos_usados_palabras
    ])

    # 2. Análisis de Oraciones App (Cruce por Uchumataqu normalizado a slug)
    oraciones_curr = [o for o in oraciones_excel if not o["es_reserva"]]
    oraciones_res = [o for o in oraciones_excel if o["es_reserva"]]

    curr_presentes = []
    curr_faltantes = []
    archivos_usados_oraciones = set()

    for o in oraciones_curr:
        match_audio = None
        for s in o["slugs"]:
            if s in audios_oraciones:
                match_audio = audios_oraciones[s]
                archivos_usados_oraciones.add(match_audio)
                break
        if match_audio:
            curr_presentes.append((o, match_audio))
        else:
            curr_faltantes.append(o)

    res_presentes = []
    res_faltantes = []
    for o in oraciones_res:
        match_audio = None
        for s in o["slugs"]:
            if s in audios_oraciones:
                match_audio = audios_oraciones[s]
                archivos_usados_oraciones.add(match_audio)
                break
        if match_audio:
            res_presentes.append((o, match_audio))
        else:
            res_faltantes.append(o)

    archivos_oraciones_reales = sorted([
        f for f in os.listdir(dir_oraciones)
        if f.lower().endswith(".wav") and not f.endswith(":Zone.Identifier")
    ]) if os.path.exists(dir_oraciones) else []

    audios_oraciones_sobrantes = sorted([
        f for f in archivos_oraciones_reales if f not in archivos_usados_oraciones
    ])

    # 3. Construcción del Reporte
    lines = []
    lines.append("=" * 85)
    lines.append("REPORTE DETALLADO DE AUDIOS PARA LA APLICACIÓN MÓVIL (UNITY)")
    lines.append("=" * 85)
    lines.append(f"Excel Palabras    : {ruta_palabras} ({len(palabras_excel)} unidades léxicas)")
    lines.append(f"Excel Oraciones   : {ruta_oraciones} ({len(oraciones_excel)} oraciones: 120 curriculares + 10 reserva)")
    lines.append(f"Carpeta Palabras  : {dir_palabras} ({len(archivos_palabras_reales)} archivos .wav)")
    lines.append(f"Carpeta Oraciones : {dir_oraciones} ({len(archivos_oraciones_reales)} archivos .wav)\n")

    lines.append("--- RESUMEN EJECUTIVO DE COBERTURA ---")
    lines.append(f"  • Palabras App (Cruce por ID)    : {len(palabras_presentes)} / {len(palabras_excel)} presentes ({len(palabras_faltantes)} faltantes)")
    lines.append(f"  • Oraciones Curriculares (Slug) : {len(curr_presentes)} / 120 presentes ({len(curr_faltantes)} faltantes)")
    lines.append(f"  • Oraciones de Reserva (Slug)   : {len(res_presentes)} / 10 presentes (Audio opcional por ser distractores)")
    lines.append(f"  • Total archivos .wav en App    : {len(archivos_palabras_reales)} palabras, {len(archivos_oraciones_reales)} oraciones")
    lines.append(f"  • Audios Sobrantes Palabras     : {len(audios_palabras_sobrantes)} archivos")
    lines.append(f"  • Audios Sobrantes Oraciones    : {len(audios_oraciones_sobrantes)} archivos\n")

    # Sección Palabras Faltantes
    lines.append("=" * 85)
    lines.append(f"1. PALABRAS EN EXCEL QUE FALTAN EN UNITY/audios_palabras/ ({len(palabras_faltantes)})")
    lines.append("=" * 85)
    if palabras_faltantes:
        lines.append(f"{'ID':<30} {'UCHUMATAQU':<25} {'ESPAÑOL':<25} CATEGORÍA")
        lines.append("-" * 85)
        for p in palabras_faltantes:
            lines.append(f"{p['id']:<30} {p['uch']:<25} {p['es']:<25} {p['categoria']}")
    else:
        lines.append("  ✅ ¡100% de palabras tienen su archivo de audio en UNITY/audios_palabras/!")
    lines.append("")

    # Sección Oraciones Curriculares Faltantes
    lines.append("=" * 85)
    lines.append(f"2. ORACIONES CURRICULARES (O_001..O_120) QUE FALTAN EN UNITY/audios_oraciones/ ({len(curr_faltantes)})")
    lines.append("=" * 85)
    if curr_faltantes:
        lines.append(f"{'ID':<8} {'LECCIÓN':<8} {'SLUG ESPERADO':<45} UCHUMATAQU")
        lines.append("-" * 85)
        for o in curr_faltantes:
            lines.append(f"{o['id']:<8} {o['leccion']:<8} {o['slug_principal']:<45} {o['uch']}")
    else:
        lines.append("  ✅ ¡100% de oraciones curriculares tienen su archivo de audio!")
    lines.append("")

    # Sección Oraciones de Reserva
    lines.append("=" * 85)
    lines.append(f"3. ORACIONES DE RESERVA (O_121..O_130) [AUDIO OPCIONAL] ({len(res_presentes)} con audio, {len(res_faltantes)} sin audio)")
    lines.append("=" * 85)
    for o in oraciones_res:
        estado = "CON AUDIO" if o in [x[0] for x in res_presentes] else "SIN AUDIO (Opcional - Distractor textual)"
        lines.append(f"  {o['id']}: {o['uch']:<35} (slug: {o['slug_principal']}) -> {estado}")
    lines.append("")

    # Sección Audios Sobrantes en Palabras
    lines.append("=" * 85)
    lines.append(f"4. AUDIOS SOBRANTES EN UNITY/audios_palabras/ (Sin ID en Excel) ({len(audios_palabras_sobrantes)})")
    lines.append("=" * 85)
    if audios_palabras_sobrantes:
        for s in audios_palabras_sobrantes:
            lines.append(f"  • {s}")
    else:
        lines.append("  (Ninguno)")
    lines.append("")

    # Sección Audios Sobrantes en Oraciones
    lines.append("=" * 85)
    lines.append(f"5. AUDIOS SOBRANTES EN UNITY/audios_oraciones/ (Sin correspondencia en Excel) ({len(audios_oraciones_sobrantes)})")
    lines.append("=" * 85)
    if audios_oraciones_sobrantes:
        for s in audios_oraciones_sobrantes:
            lines.append(f"  • {s}")
    else:
        lines.append("  (Ninguno)")
    lines.append("")

    report = "\n".join(lines)
    print(report)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\n[OK] Reporte guardado en: {OUTPUT_FILE}")

    # 4. Normalización de Volumen a target_db (-3.0 dBFS)
    if not args.sin_normalizar:
        print("\n" + "=" * 85)
        modo_str = " (SIMULACIÓN)" if args.dry_run else ""
        print(f"🔊 NORMALIZACIÓN DE VOLUMEN A {args.target_db} dBFS{modo_str}")
        print("=" * 85)

        print(f"  • Normalizando audios de palabras ({dir_palabras})...")
        tot_palabras, ok_palabras = normalizar_volumen_directorio(
            dir_palabras, target_db=args.target_db, dry_run=args.dry_run
        )
        print(f"    ✅ Palabras: {ok_palabras}/{tot_palabras} archivos normalizados a {args.target_db} dBFS.")

        print(f"  • Normalizando audios de oraciones ({dir_oraciones})...")
        tot_oraciones, ok_oraciones = normalizar_volumen_directorio(
            dir_oraciones, target_db=args.target_db, dry_run=args.dry_run
        )
        print(f"    ✅ Oraciones: {ok_oraciones}/{tot_oraciones} archivos normalizados a {args.target_db} dBFS.")
        print("=" * 85)


if __name__ == "__main__":
    main()
