"""
verificar_audios_asr.py
Verificación exhaustiva de audios para el módulo ASR (Reconocimiento Automático de Voz).
Compara los archivos de audio en Para_ASR/ contra:
  - excel/palabras_pln.xlsx (325 entradas léxicas de entrenamiento/evaluación)
  - excel/oraciones.xlsx (130 oraciones completas con transcripción)

Genera un reporte detallado en Para_ASR/reportes/reporte_audios_asr.txt indicando por locutor:
  - Cobertura completa (3 tomas por item: _01, _02, _03).
  - Cobertura parcial (1 o 2 tomas).
  - Items faltantes en audios.
  - Archivos de audio sobrantes en las carpetas (sin correspondencia en Excel).
"""

import os
import re
import sys
import unicodedata

script_dir = os.path.dirname(os.path.abspath(__file__))
limpieza_dir = script_dir
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)
entrenamiento_dir = os.path.join(scripts_dir, "entrenamiento")

sys.path.insert(0, entrenamiento_dir)
from lector_xlsx import leer_xlsx

EXCEL_DIR = os.path.join(project_root, "excel")
OUTPUT_FILE = os.path.join(asr_dir, "reportes", "reporte_audios_asr.txt")
VARIANTES_ESPERADAS = ["_01", "_02", "_03", "_04"]


def normalizar_texto(txt):
    if not txt:
        return ""
    t = re.sub(r"[^\w\sʼ']", "", txt).strip().lower()
    return re.sub(r"\s+", " ", t)


def normalizar_oracion_slug(texto: str) -> str:
    """Normaliza el texto en Uchumataqu a formato slug para matching con audios."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"['ʼ`´\^]", "", t)
    t = re.sub(r'[¿?!¡.,;:\"()_\-]', " ", t)
    t = t.strip().lower()
    return re.sub(r"\s+", "_", t)


def generar_variantes_slug_oracion(uch_texto: str) -> set:
    """Genera variantes de slug para matching robusto de nombres de archivo de oraciones."""
    base = normalizar_oracion_slug(uch_texto)
    variantes = {base}
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


def cargar_palabras_pln(ruta_excel):
    """Carga las 325 entradas léxicas de palabras_pln.xlsx."""
    rows = leer_xlsx(ruta_excel)
    palabras = []
    for r in rows[1:]:
        if len(r) > 0 and r[0]:
            pid = r[0].strip().lower()
            uch = r[1].strip() if len(r) > 1 else ""
            es = r[2].strip() if len(r) > 2 else ""
            palabras.append({
                "id": pid,
                "uch": uch,
                "es": es
            })
    return palabras


def cargar_oraciones_pln(ruta_excel):
    """Carga las 130 oraciones de oraciones.xlsx."""
    rows = leer_xlsx(ruta_excel)
    oraciones = []
    for r in rows[1:]:
        if len(r) > 0 and r[0]:
            oid = r[0].strip()
            uch = r[1].strip() if len(r) > 1 else ""
            es = r[2].strip() if len(r) > 2 else ""
            slug = normalizar_oracion_slug(uch)
            variantes = generar_variantes_slug_oracion(uch) | {oid.lower()}
            oraciones.append({
                "id": oid,
                "uch": uch,
                "es": es,
                "slug": slug,
                "slugs": variantes
            })
    return oraciones


def indexar_audios(directorio):
    """Retorna dict: base_id -> set de variantes encontradas ('_01', '_02', etc.)."""
    if not os.path.exists(directorio):
        return {}
    archivos_por_id = {}
    for f in os.listdir(directorio):
        if f.lower().endswith(".wav") and not f.endswith(":Zone.Identifier"):
            nombre = os.path.splitext(f)[0]
            m = re.match(r"^(.*?)(?:_0([1-9]))?$", nombre)
            if m:
                bid = m.group(1).lower()
                var = f"_0{m.group(2)}" if m.group(2) else "_01"
                archivos_por_id.setdefault(bid, set()).add(var)
    return archivos_por_id


def obtener_variantes_esperadas(locutor: str) -> list:
    """Retorna las variantes esperadas según el locutor (Eva usa 4 tomas, los demás 3)."""
    if locutor.lower() == "eva":
        return ["_01", "_02", "_03", "_04"]
    return ["_01", "_02", "_03"]


def auditar_locutor_palabras(palabras_excel, dir_locutor, variantes_esperadas=None):
    if variantes_esperadas is None:
        variantes_esperadas = ["_01", "_02", "_03"]
    audios = indexar_audios(dir_locutor)
    ids_excel = {p["id"] for p in palabras_excel}

    completas = []
    parciales = []
    sin_audio = []

    for p in palabras_excel:
        pid = p["id"]
        presentes = audios.get(pid, set())
        faltantes = [v for v in variantes_esperadas if v not in presentes]
        
        if not presentes:
            sin_audio.append(p)
        elif faltantes:
            parciales.append((p, presentes, faltantes))
        else:
            completas.append(p)

    sobrantes = sorted([b for b in audios if b not in ids_excel])
    total_wavs = sum(len(v) for v in audios.values())

    return {
        "completas": completas,
        "parciales": parciales,
        "sin_audio": sin_audio,
        "sobrantes": sobrantes,
        "total_wavs": total_wavs,
        "total_excel": len(palabras_excel),
        "variantes_esperadas": variantes_esperadas,
    }


def auditar_locutor_oraciones(oraciones_excel, dir_locutor, variantes_esperadas=None):
    if variantes_esperadas is None:
        variantes_esperadas = ["_01", "_02", "_03"]
    audios = indexar_audios(dir_locutor)

    completas = []
    parciales = []
    sin_audio = []
    audios_asignados = set()

    for o in oraciones_excel:
        match_slug = None
        for s in o["slugs"]:
            if s in audios:
                match_slug = s
                break

        if match_slug:
            presentes = audios[match_slug]
            audios_asignados.add(match_slug)
            faltantes = [v for v in variantes_esperadas if v not in presentes]
            if faltantes:
                parciales.append((o, presentes, faltantes))
            else:
                completas.append(o)
        else:
            sin_audio.append(o)

    sobrantes = sorted([b for b in audios if b not in audios_asignados])
    total_wavs = sum(len(v) for v in audios.values())

    return {
        "completas": completas,
        "parciales": parciales,
        "sin_audio": sin_audio,
        "sobrantes": sobrantes,
        "total_wavs": total_wavs,
        "total_excel": len(oraciones_excel),
        "variantes_esperadas": variantes_esperadas,
    }


def main():
    ruta_palabras = os.path.join(EXCEL_DIR, "palabras_pln.xlsx")
    ruta_oraciones = os.path.join(EXCEL_DIR, "oraciones.xlsx")

    palabras_excel = cargar_palabras_pln(ruta_palabras)
    oraciones_excel = cargar_oraciones_pln(ruta_oraciones)

    dir_palabras_asr = os.path.join(asr_dir, "audios_palabras")
    dir_oraciones_asr = os.path.join(asr_dir, "audios_oraciones")

    locutores_palabras = sorted([d for d in os.listdir(dir_palabras_asr) if os.path.isdir(os.path.join(dir_palabras_asr, d))]) if os.path.exists(dir_palabras_asr) else []
    locutores_oraciones = sorted([d for d in os.listdir(dir_oraciones_asr) if os.path.isdir(os.path.join(dir_oraciones_asr, d))]) if os.path.exists(dir_oraciones_asr) else []

    lines = []
    lines.append("=" * 85)
    lines.append("REPORTE DETALLADO DE AUDIOS PARA MÓDULO ASR (PARA_ASR)")
    lines.append("=" * 85)
    lines.append(f"Excel Palabras PLN : {ruta_palabras} ({len(palabras_excel)} entradas léxicas)")
    lines.append(f"Excel Oraciones PLN: {ruta_oraciones} ({len(oraciones_excel)} oraciones)")
    lines.append(f"Carpeta ASR        : {asr_dir}")
    lines.append(f"Locutores Palabras : {', '.join(locutores_palabras)}")
    lines.append(f"Locutores Oraciones: {', '.join(locutores_oraciones)}\n")

    # =========================================================================
    # 1. AUDIOS DE PALABRAS POR LOCUTOR
    # =========================================================================
    lines.append("=" * 85)
    lines.append("1. AUDIOS DE PALABRAS POR LOCUTOR (ASR)")
    lines.append("=" * 85)

    for loc in locutores_palabras:
        loc_dir = os.path.join(dir_palabras_asr, loc)
        variantes = obtener_variantes_esperadas(loc)
        res = auditar_locutor_palabras(palabras_excel, loc_dir, variantes_esperadas=variantes)

        n_tomas = len(variantes)
        tomas_desc = f"{n_tomas} tomas"
        parcial_desc = f"1-{n_tomas - 1} tomas" if n_tomas > 2 else "1 toma"

        lines.append("-" * 85)
        lines.append(f"LOCUTOR: {loc.upper()} (Palabras)")
        lines.append("-" * 85)
        lines.append(f"  • Total archivos .wav : {res['total_wavs']}")
        lines.append(f"  • Cobertura total     : {len(res['completas']) + len(res['parciales'])} / {res['total_excel']} palabras")
        lines.append(f"  • Completas ({tomas_desc}) : {len(res['completas'])}")
        lines.append(f"  • Parciales ({parcial_desc}): {len(res['parciales'])}")
        lines.append(f"  • Sin audio           : {len(res['sin_audio'])}")
        lines.append(f"  • Audios sobrantes    : {len(res['sobrantes'])}")

        if res['sin_audio']:
            lines.append(f"\n  Palabras que faltan para {loc} ({len(res['sin_audio'])}):")
            lines.append(f"    {'ID':<30} {'UCHUMATAQU':<25} {'ESPAÑOL'}")
            lines.append("    " + "-" * 75)
            for p in res['sin_audio']:
                lines.append(f"    {p['id']:<30} {p['uch']:<25} {p['es']}")

        if res['sobrantes']:
            lines.append(f"\n  Audios sobrantes en {loc} (Sin entrada en Excel):")
            for s in res['sobrantes']:
                lines.append(f"    • {s}")
        lines.append("")

    # =========================================================================
    # 2. AUDIOS DE ORACIONES POR LOCUTOR
    # =========================================================================
    lines.append("=" * 85)
    lines.append("2. AUDIOS DE ORACIONES POR LOCUTOR (ASR)")
    lines.append("=" * 85)

    for loc in locutores_oraciones:
        loc_dir = os.path.join(dir_oraciones_asr, loc)
        variantes = obtener_variantes_esperadas(loc)
        res = auditar_locutor_oraciones(oraciones_excel, loc_dir, variantes_esperadas=variantes)

        n_tomas = len(variantes)
        tomas_desc = f"{n_tomas} tomas"
        parcial_desc = f"1-{n_tomas - 1} tomas" if n_tomas > 2 else "1 toma"

        lines.append("-" * 85)
        lines.append(f"LOCUTOR: {loc.upper()} (Oraciones)")
        lines.append("-" * 85)
        lines.append(f"  • Total archivos .wav : {res['total_wavs']}")
        lines.append(f"  • Cobertura total     : {len(res['completas']) + len(res['parciales'])} / {res['total_excel']} oraciones")
        lines.append(f"  • Completas ({tomas_desc}) : {len(res['completas'])}")
        lines.append(f"  • Parciales ({parcial_desc}): {len(res['parciales'])}")
        lines.append(f"  • Sin audio           : {len(res['sin_audio'])}")
        lines.append(f"  • Audios sobrantes    : {len(res['sobrantes'])}")

        if res['sin_audio']:
            lines.append(f"\n  Oraciones que faltan para {loc} ({len(res['sin_audio'])}):")
            lines.append(f"    {'SLUG ID':<35} {'UCHUMATAQU'}")
            lines.append("    " + "-" * 75)
            for o in res['sin_audio']:
                lines.append(f"    {o['slug']:<35} {o['uch']}")

        if res['sobrantes']:
            lines.append(f"\n  Audios sobrantes en {loc} (Sin entrada en Excel):")
            for s in res['sobrantes']:
                lines.append(f"    • {s}")
        lines.append("")

    report = "\n".join(lines)
    print(report)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\n[OK] Reporte guardado en: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
