#!/usr/bin/env python3
"""
renombrar_audios_oraciones_id.py
Renombra y procesa los archivos de audio de oraciones en ASR según el ID de cada oración
de excel/oraciones.xlsx (ej: O_001_01.wav, O_002_01.wav, etc.).

Soporta procesar grabaciones originales con nombres en texto Uchumataqu
(como las de Roberto en ASR/audios_originales/oraciones/roberto/) y copiarlas
directamente con su nomenclatura estándar a ASR/audios_oraciones/roberto/.

IMPORTANTE:
  - NO aplica ninguna normalización de volumen acústico (preserva el audio intacto).
  - Descarta/omite archivos obsoletos o sin correspondencia en el catálogo actual.

Uso:
  python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py --locutor roberto
  python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py --locutor roberto --dry-run
  python3 ASR/scripts/limpieza/renombrar_audios_oraciones_id.py --locutor pedro --dry-run
"""

import argparse
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LIMPIEZA_DIR = SCRIPT_DIR
SCRIPTS_DIR = SCRIPT_DIR.parent
ASR_DIR = SCRIPTS_DIR.parent
PROJECT_ROOT = ASR_DIR.parent
ENTRENAMIENTO_DIR = SCRIPTS_DIR / "entrenamiento"
EXCEL_PATH = PROJECT_ROOT / "excel" / "oraciones.xlsx"

sys.path.insert(0, str(ENTRENAMIENTO_DIR))
from lector_xlsx import leer_xlsx


# Mapeo manual para Roberto (archivos con diferencias ortográficas o léxicas frente al Excel)
MANUAL_MAP_ROBERTO = {
    "chhuljama_amchay":                          "O_008",   # Chhuljamachay Pedro
    "ew_taki_urkhuchay":                         "O_042",   # Taki urkhu ewchay
    "jasiksta_am_pichuchay":                     "O_015",   # Jasiktam pichuchay Pedro
    "ni_axtal_satschay_lasnuchay":               "O_037",   # Nï axtal lasnuchay
    "ni_sanqo_choq_iwisanaka_wistakchay":        "O_087",   # Nï sanqo chiw iwisanaka wistakchay
    "pedro_chhep_achasinakachay":                "O_058",   # Pedro chhep achasinaka wistakchay
    "pedro_qotni_xawariski_tuchay":              "O_078",   # Juana qotñi xawariski tuchay
    "pedro_sanqo_uninaka_uyuwichay":             "O_084",   # Juana sanqo uñinaka uyuwichay
    "pedro_sininaka_qhorskchay":                 "O_097",   # Pedro soqna siñinaka qhorskchay
    "taki_chiw_qala_chhaqwaypini_layschay":      "O_096",   # Taki qala chhaqwaypini layschay
    "taki_maska_ewchay":                         "O_063",   # Taki mäska chhukchay
    "thuni_taxacharku_tekschay":                 "O_115",   # Thuñi taxacharku thikuchay
    "tiku_anachhulu_chhiri_anachay":             "O_113",   # Tiku anachhulu chhiri ana selschay
    "uchumik_sitsninaka_anachay":                "O_020",   # Uchumik sitsñinakachay
    "wilk_anachhuni":                            "O_013",   # Ana, wilk anachhuñi
    "wilk_qhoya_piwachay":                       "O_053",   # Wilk wiyani piwachay
    "wilk_waki_pichuchay":                       "O_017",   # Wilk tï watha waki pichuchay
    "wilk_wiyani_sana_khitschay":                "O_052",   # Wilk säna khitschay
    "wist_qhoya_chhep_phetanakachay":            "O_048",   # Wist qhoya chhep phetanaka wistakchay
    "chhullayku_qoqnaka_anachay":                "O_108",   # Chhullayku qoqnaka ana selschay
    "lorenzo_thosa_qachina_qhoychay":            "O_119",   # Lorenzo thosa qachina phawschay
    "taki_phesqona_tekschay":                    "O_091",   # Taki phesqoña lowalowapini satschay
    "taki_qetsi_lowalowapini_satschay":          "O_092",   # Taki qetsi wiyanichay ulanchay
    "amchuki_parentiña_arusha_taxsnakichay":     "O_080",   # Amchuki parentiña arusha taxsnakichay
    "amchuki-palitaknaka_chhuni_pichuchay":      "O_022",   # Amchuki palitaknaka, chhuñi pichuchay
    "wilk_peske_karpinisanaka_wistakchay":       "O_123",   # Wilk karpinisa jaxchay
    "wist_malqoy_chiwkisnaka_tuchay":            "O_070",   # Wist malaqoy chiwkisnaka tuchay
    "wist_malaqoy_qañawi_achuchay":              "O_107",   # Wist malaqoy qañawi achuchay
}

# Grabaciones antiguas descartadas / obsoletas para Roberto
FILES_TO_DELETE_ROBERTO = {
    "am_pedro_chay",                      # Sin match en nuevo Excel
    "maria_chhi_teskana_qhawschay",       # Sin match
    "maria_taxsnuku_chhaxrañanaka_wistakchay",  # Sin match
    "ni_lloqa_qalpu_chirsnachay",         # Sin match
    "pedro_juwa_thosa_wistakchay",        # Sin match
    "qawi_usachay",                       # Sin match
    "qhasumpek_chers_walchay",            # Sin match
    "qhaumpek_chers_walchay",             # Sin match
    "shila_wilk_tho_pedro",              # Sin match
    "tiksi_am_malaqoy_siluchay",          # Sin match
    "uchums_achichay_sitsnizonipinchay",  # Duplicado con typo
    "wilk_watha_irohito_urus",            # Sin match
}


def normalizar_oracion_slug(texto: str) -> str:
    """Normaliza texto Uchumataqu a formato slug estricto para matching de nombres."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"['ʼ`´\^\"ʻʽ’]", "", t)
    t = re.sub(r'[¿?!¡.,;:\"()_\-]', " ", t)
    t = t.strip().lower()
    return re.sub(r"\s+", "_", t)


def generar_variantes_slug_oracion(uch_texto: str) -> set:
    """Genera variantes de slug para matching robusto de nombres de archivo."""
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
    sin_guion = base.replace("_", "")
    variantes.add(sin_guion)
    return variantes


def cargar_oraciones(ruta_excel: Path) -> list:
    """Carga oraciones desde el Excel curricular."""
    rows = leer_xlsx(str(ruta_excel))
    oraciones = []
    for r in rows[1:]:
        if len(r) > 0 and r[0]:
            oid = str(r[0]).strip()
            uch = str(r[1]).strip() if len(r) > 1 else ""
            es = str(r[2]).strip() if len(r) > 2 else ""
            slug = normalizar_oracion_slug(uch)
            variantes = generar_variantes_slug_oracion(uch) | {oid.lower(), oid.lower().replace("_", "")}
            oraciones.append({
                "id": oid,
                "uch": uch,
                "es": es,
                "slug": slug,
                "slugs": variantes
            })
    return oraciones


def procesar_locutor_oraciones(
    locutor: str,
    dir_origen: Path,
    dir_destino: Path,
    oraciones: list,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Procesa, renombra y transfiere los archivos de audio de un locutor hacia audios_oraciones/{locutor}/.
    """
    if not dir_origen.exists():
        print(f"[ERROR] No existe directorio de origen: {dir_origen}")
        return {"total": 0, "renombrados": 0, "descartados": 0, "errores": 0}

    dir_destino.mkdir(parents=True, exist_ok=True)

    archivos = sorted([
        f for f in dir_origen.iterdir()
        if f.suffix.lower() == ".wav" and not f.name.endswith(":Zone.Identifier") and not f.name.startswith(".")
    ])

    print(f"\n📂 Locutor: '{locutor}'")
    print(f"   Origen:  {dir_origen} ({len(archivos)} archivos .wav)")
    print(f"   Destino: {dir_destino}")
    print("-" * 75)

    es_roberto = (locutor.lower() == "roberto")
    renombrar = []
    descartar = []

    for f_path in archivos:
        filename = f_path.name
        stem = f_path.stem.lower()

        # 1. Reglas específicas de Roberto si aplica
        if es_roberto:
            if stem in FILES_TO_DELETE_ROBERTO:
                descartar.append((f_path, "Obsoleto / sin correspondencia en Excel actual"))
                continue
            if stem in MANUAL_MAP_ROBERTO:
                target_id = MANUAL_MAP_ROBERTO[stem]
                nuevo_nombre = f"{target_id}_01.wav"
                renombrar.append((f_path, nuevo_nombre, target_id))
                continue

        # 2. Extracción de ID y toma
        m = re.match(r"^(.*?)(?:_0([1-9]))?$", stem)
        base = m.group(1).lower() if m else stem
        toma = f"_0{m.group(2)}" if (m and m.group(2)) else "_01"

        base_slug = normalizar_oracion_slug(base)
        base_sin_guion = base_slug.replace("_", "")

        matched_oid = None
        for o in oraciones:
            if base in o["slugs"] or base_slug in o["slugs"] or base_sin_guion in o["slugs"]:
                matched_oid = o["id"]
                break

        if matched_oid:
            nuevo_nombre = f"{matched_oid}{toma}.wav"
            renombrar.append((f_path, nuevo_nombre, matched_oid))
        else:
            descartar.append((f_path, "Sin coincidencia en catálogo de oraciones"))

    print(f"  • Coincidentes a procesar: {len(renombrar)}")
    print(f"  • Descartados / sobrantes: {len(descartar)}")

    stats = {
        "total": len(archivos),
        "renombrados": len(renombrar),
        "descartados": len(descartar),
        "errores": 0,
    }

    if verbose or dry_run:
        print("\n  Ejemplos de asignación (primeros 10):")
        for orig, nuevo, oid in renombrar[:10]:
            print(f"    [OK] {orig.name:<45} -> {nuevo}")
        if descartar:
            print("\n  Archivos descartados:")
            for orig, motivo in descartar[:10]:
                print(f"    [DESCARTADO] {orig.name:<40} ({motivo})")
            if len(descartar) > 10:
                print(f"    ... y {len(descartar) - 10} archivos descartados más.")

    if dry_run:
        print("\n  [SIMULACIÓN] No se realizaron modificaciones en disco.")
        return stats

    # Ejecutar transferencia / renombrado
    mismo_directorio = (dir_origen.resolve() == dir_destino.resolve())
    exitosos = 0

    for orig_path, nuevo_nombre, _ in renombrar:
        dest_path = dir_destino / nuevo_nombre
        try:
            if mismo_directorio:
                if orig_path != dest_path:
                    # Renombrado seguro en el mismo directorio
                    temp_path = orig_path.with_name(f"__tmp_ren_{nuevo_nombre}")
                    orig_path.rename(temp_path)
                    temp_path.replace(dest_path)
                exitosos += 1
            else:
                # Copia binaria fiel preservando audio sin normalizar
                shutil.copy2(orig_path, dest_path)
                exitosos += 1
        except Exception as e:
            print(f"  [ERROR] Al procesar {orig_path.name} -> {nuevo_nombre}: {e}")
            stats["errores"] += 1

    # Si es el mismo directorio, eliminar archivos descartados
    if mismo_directorio:
        for orig_path, _ in descartar:
            try:
                orig_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"  [ERROR] Al eliminar {orig_path.name}: {e}")

    stats["renombrados"] = exitosos
    print(f"  ✅ {exitosos} archivos procesados correctamente hacia {dir_destino.name}/")
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Renombra audios de oraciones en ASR según su ID en Excel y los coloca en audios_oraciones/."
    )
    parser.add_argument(
        "--locutor",
        default="roberto",
        help="Nombre del locutor a procesar (default: roberto)",
    )
    parser.add_argument(
        "--input-dir",
        help="Directorio de origen de los audios (opcional, se detecta automáticamente)",
    )
    parser.add_argument(
        "--output-dir",
        help="Directorio de destino de los audios (default: ASR/audios_oraciones/{locutor})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo simulación: no modifica archivos en disco",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra detalle archivo por archivo",
    )

    args = parser.parse_args()

    if not EXCEL_PATH.exists():
        print(f"[ERROR] No existe el archivo Excel: {EXCEL_PATH}")
        sys.exit(1)

    oraciones = cargar_oraciones(EXCEL_PATH)
    print(f"Cargadas {len(oraciones)} oraciones curriculares desde {EXCEL_PATH.name}")

    locutor = args.locutor.strip().lower()

    # Determinar carpeta de origen
    if args.input_dir:
        dir_origen = Path(args.input_dir).resolve()
    else:
        # Si es roberto, busca preferentemente en audios_originales
        if locutor == "roberto":
            candidato_orig = ASR_DIR / "audios_originales" / "oraciones" / "roberto"
            candidato_proc = ASR_DIR / "audios_oraciones" / "roberto"
            dir_origen = candidato_orig if candidato_orig.exists() else candidato_proc
        else:
            candidato_proc = ASR_DIR / "audios_oraciones" / locutor
            candidato_orig = ASR_DIR / "audios_originales" / "oraciones" / locutor
            dir_origen = candidato_proc if candidato_proc.exists() else candidato_orig

    # Determinar carpeta de destino
    if args.output_dir:
        dir_destino = Path(args.output_dir).resolve()
    else:
        dir_destino = ASR_DIR / "audios_oraciones" / locutor

    print("=" * 75)
    print("🏷️ RENOMBRADOR DE AUDIOS DE ORACIONES (ASR)")
    print(f"  • Locutor:      {locutor}")
    print(f"  • Normalizar:   NO (sin normalización de volumen)")
    print(f"  • Simulación:   {'SÍ (--dry-run)' if args.dry_run else 'NO (ejecución real)'}")
    print("=" * 75)

    stats = procesar_locutor_oraciones(
        locutor=locutor,
        dir_origen=dir_origen,
        dir_destino=dir_destino,
        oraciones=oraciones,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print("\n" + "=" * 75)
    print(f"RESUMEN FINAL - {locutor.upper()}")
    print("=" * 75)
    print(f"  Total audios origen:       {stats['total']}")
    print(f"  Renombrados y transferidos: {stats['renombrados']}")
    print(f"  Descartados/sobrantes:     {stats['descartados']}")
    print(f"  Errores:                   {stats['errores']}")
    print("=" * 75)

    if stats["errores"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
