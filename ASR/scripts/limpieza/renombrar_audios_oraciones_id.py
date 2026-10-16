#!/usr/bin/env python3
"""
renombrar_audios_oraciones_id.py
Renombra los archivos de audio en ASR/audios_oraciones/pedro/ usando el ID de cada oración
de excel/oraciones.xlsx (ej: O_001_01.wav, O_001_02.wav, O_001_03.wav).
Elimina los archivos sobrantes que no corresponden a ninguna oración del Excel.

Uso:
  python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py --dry-run
  python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py
"""

import os
import re
import sys
import unicodedata
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIMPIEZA_DIR = SCRIPT_DIR
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
ASR_DIR = os.path.dirname(SCRIPTS_DIR)
PROJECT_ROOT = os.path.dirname(ASR_DIR)
ENTRENAMIENTO_DIR = os.path.join(SCRIPTS_DIR, "entrenamiento")

sys.path.insert(0, ENTRENAMIENTO_DIR)
from lector_xlsx import leer_xlsx


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


def cargar_oraciones(ruta_excel: str):
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


def main():
    parser = argparse.ArgumentParser(description="Renombra audios de oraciones en ASR según su ID y elimina sobrantes.")
    parser.add_argument("--dry-run", action="store_true", help="Simula el renombrado y eliminación sin modificar disco")
    parser.add_argument("--locutor", default="pedro", help="Nombre de la carpeta de locutor (default: pedro)")
    args = parser.parse_args()

    excel_path = os.path.join(PROJECT_ROOT, "excel", "oraciones.xlsx")
    pedro_dir = os.path.join(ASR_DIR, "audios_oraciones", args.locutor)

    if not os.path.exists(excel_path):
        print(f"[ERROR] No existe el archivo Excel: {excel_path}")
        sys.exit(1)

    if not os.path.exists(pedro_dir):
        print(f"[ERROR] No existe el directorio de audios: {pedro_dir}")
        sys.exit(1)

    oraciones = cargar_oraciones(excel_path)
    print(f"Cargadas {len(oraciones)} oraciones desde {excel_path}")

    files = sorted([f for f in os.listdir(pedro_dir) if f.endswith(".wav") and not f.endswith(":Zone.Identifier")])
    print(f"Archivos encontrados en {pedro_dir}: {len(files)}")

    renombrar = []
    eliminar = []

    for f in files:
        m = re.match(r"^(.*?)(?:_0([1-9]))?\.wav$", f)
        if not m:
            eliminar.append(f)
            continue

        base = m.group(1).lower()
        toma = f"_0{m.group(2)}" if m.group(2) else "_01"

        matched_oid = None
        for o in oraciones:
            if base in o["slugs"]:
                matched_oid = o["id"]
                break

        if matched_oid:
            nuevo_nombre = f"{matched_oid}{toma}.wav"
            renombrar.append((f, nuevo_nombre))
        else:
            eliminar.append(f)

    print("\n" + "=" * 80)
    print(f"PLAN DE ACCIÓN ({'SIMULACIÓN --dry-run' if args.dry_run else 'EJECUCIÓN REAL'}):")
    print(f"  • Archivos a renombrar: {len(renombrar)}")
    print(f"  • Archivos sobrantes a eliminar: {len(eliminar)}")
    print("=" * 80)

    if args.dry_run:
        print("\nEjemplos de renombrado (primeros 10):")
        for orig, nuevo in renombrar[:10]:
            print(f"  [RENOMBRAR] {orig} -> {nuevo}")

        print(f"\nArchivos sobrantes a eliminar ({len(eliminar)}):")
        for f in eliminar[:15]:
            print(f"  [ELIMINAR] {f}")
        if len(eliminar) > 15:
            print(f"  ... y {len(eliminar) - 15} archivos más.")
        print("\nSimulación finalizada. Ejecuta sin --dry-run para aplicar los cambios.")
        return

    # Ejecutar renombrado
    exitos_renombrados = 0
    for orig, nuevo in renombrar:
        src = os.path.join(pedro_dir, orig)
        dst = os.path.join(pedro_dir, nuevo)
        try:
            os.rename(src, dst)
            exitos_renombrados += 1
        except Exception as e:
            print(f"[ERROR] No se pudo renombrar {orig} a {nuevo}: {e}")

    # Ejecutar eliminación
    exitos_eliminados = 0
    for f in eliminar:
        path = os.path.join(pedro_dir, f)
        try:
            os.remove(path)
            exitos_eliminados += 1
        except Exception as e:
            print(f"[ERROR] No se pudo eliminar {f}: {e}")

    print(f"\n✅ Proceso completado:")
    print(f"  • {exitos_renombrados} archivos renombrados correctamente.")
    print(f"  • {exitos_eliminados} archivos sobrantes eliminados.")


if __name__ == "__main__":
    main()
