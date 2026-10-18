"""
renombrar_oraciones_roberto.py
Compara los audios originales en ASR/audios_originales/oraciones/roberto con
el Excel excel/oraciones.xlsx. Usa normalización + mapeo manual de excepciones
para renombrar archivos de nombre Uchumataqu a ID.

Uso:
  python3 ASR/scripts/limpieza/renombrar_oraciones_roberto.py [--dry-run]
"""
import os
import sys
import unicodedata

script_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)
entrenamiento_dir = os.path.join(scripts_dir, "entrenamiento")

sys.path.insert(0, entrenamiento_dir)
from lector_xlsx import leer_xlsx

excel_path = os.path.join(project_root, "excel", "oraciones.xlsx")
audio_dir = os.path.join(asr_dir, "audios_originales", "oraciones", "roberto")

# ─── Mapeo manual para archivos cuyo nombre difiere del Excel ───
# Formato: nombre_archivo_sin_extension (minúsculas) -> ID del Excel
MANUAL_MAP = {
    # Archivos cuyos nombres en el Excel cambiaron significativamente
    "chhuljama_amchay":                          "O_008",   # Excel: Chhuljamachay pedro
    "ew_taki_urkhuchay":                         "O_042",   # Excel: Taki urkhu ewchay
    "jasiksta_am_pichuchay":                     "O_015",   # Excel: Jasiktam pichuchay pedro
    "ni_axtal_satschay_lasnuchay":               "O_037",   # Excel: Nï axtal lasnuchay
    "ni_sanqo_choq_iwisanaka_wistakchay":        "O_087",   # Excel: Nï sanqo chiw iwisanaka wistakchay
    "pedro_chhep_achasinakachay":                "O_058",   # Excel: Pedro chhep achasinaka wistakchay
    "pedro_qotni_xawariski_tuchay":              "O_078",   # Excel: Juana qotñi xawariski tuchay
    "pedro_sanqo_uninaka_uyuwichay":             "O_084",   # Excel: Juana sanqo uñinaka uyuwichay
    "pedro_sininaka_qhorskchay":                 "O_097",   # Excel: Pedro soqna siñinaka qhorskchay
    "taki_chiw_qala_chhaqwaypini_layschay":      "O_096",   # Excel: Taki qala chhaqwaypini layschay
    "taki_maska_ewchay":                         "O_063",   # Excel: Taki mäska chhukchay
    "thuni_taxacharku_tekschay":                 "O_115",   # Excel: Thuñi taxacharku thikuchay
    "tiku_anachhulu_chhiri_anachay":             "O_113",   # Excel: Tiku anachhulu chhiri ana selschay
    "uchumik_sitsninaka_anachay":                "O_020",   # Excel: Uchumik sitsñinakachay
    "wilk_anachhuni":                            "O_013",   # Excel: Ana wilk anachhuñi
    "wilk_qhoya_piwachay":                       "O_053",   # Excel: Wilk wiyani piwachay
    "wilk_waki_pichuchay":                       "O_017",   # Excel: Wilk tï watha waki pichuchay
    "wilk_wiyani_sana_khitschay":                "O_052",   # Excel: Wilk säna khitschay
    "wist_qhoya_chhep_phetanakachay":            "O_048",   # Excel: Wist qhoya chhep phetanaka wistakchay
    "chhullayku_qoqnaka_anachay":                "O_108",   # Excel: Chhullayku qoqnaka ana selschay
    "lorenzo_thosa_qachina_qhoychay":            "O_119",   # Excel: Lorenzo thosa qachina phawschay
    "taki_phesqona_tekschay":                    "O_091",   # Excel: Taki phesqoña lowalowapini satschay
    "taki_qetsi_lowalowapini_satschay":          "O_092",   # Excel: Taki qetsi wiyanichay ulanchay
    "amchuki_parentiña_arusha_taxsnakichay":     "O_080",   # Excel: Amchuki parentiña arusha taxsnakichay (diacrítico ñ)
    "amchuki-palitaknaka_chhuni_pichuchay":      "O_022",   # Excel: Amchuki palitaknaka, chhuñi pichuchay
    "wilk_peske_karpinisanaka_wistakchay":       "O_123",   # Excel: Wilk karpinisa jaxchay (mejor match disponible)
    "wist_malqoy_chiwkisnaka_tuchay":            "O_070",   # Excel: Wist malaqoy chiwkisnaka tuchay
    "wist_malaqoy_qa\u00f1awi_achuchay":               "O_107",   # Excel: Wist malaqoy qañawi achuchay (ñ en filename)
}

# ─── Archivos que NO tienen correspondencia en el Excel y se deben eliminar ───
# (grabaciones antiguas que ya no corresponden a ninguna oración actual)
FILES_TO_DELETE = {
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


def normalize_name(text: str) -> str:
    """Normaliza texto Uchumataqu para compararlo como nombre de archivo."""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    replacements = {
        'ʼ': '', '\u2019': '', "'": '', ',': '', '.': '',
        '¿': '', '?': '', '"': '',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.lower().strip().replace(' ', '_').replace('-', '_')
    while '__' in text:
        text = text.replace('__', '_')
    return text


def main():
    dry_run = '--dry-run' in sys.argv

    print(f"📂 Excel: {excel_path}")
    print(f"📂 Audio dir: {audio_dir}")
    if dry_run:
        print("🔍 MODO DRY-RUN: no se harán cambios")

    if not os.path.exists(excel_path):
        print(f"[ERROR] Excel no encontrado: {excel_path}")
        return
    if not os.path.exists(audio_dir):
        print(f"[ERROR] Carpeta de audios no encontrada: {audio_dir}")
        return

    # Leer Excel
    rows = leer_xlsx(excel_path)
    excel_entries = []
    for row in rows[1:]:
        if len(row) >= 2 and row[0] and row[1]:
            id_val = str(row[0]).strip()
            uch_val = str(row[1]).strip()
            normalized = normalize_name(uch_val)
            excel_entries.append((id_val, uch_val, normalized))

    # Mapeo normalizado -> ID
    norm_to_id = {e[2]: e[0] for e in excel_entries}
    valid_ids = {e[0] for e in excel_entries}

    print(f"\n📊 Oraciones en Excel: {len(excel_entries)}")

    # Leer archivos de audio
    existing_files = sorted(
        f for f in os.listdir(audio_dir)
        if f.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg'))
        and not f.endswith(':Zone.Identifier')
    )
    print(f"📊 Audios en carpeta: {len(existing_files)}")

    # Construir mapeo archivo -> ID
    file_to_id = {}     # filename -> ID
    to_delete = []       # filenames a eliminar
    unresolved = []      # filenames sin match

    for f in existing_files:
        name = os.path.splitext(f)[0].lower()

        # 1. Verificar mapeo manual
        if name in MANUAL_MAP:
            target_id = MANUAL_MAP[name]
            if target_id in valid_ids:
                file_to_id[f] = target_id
            else:
                print(f"  ⚠️ Mapeo manual inválido: {name} -> {target_id}")
                unresolved.append(f)
            continue

        # 2. Verificar si debe eliminarse
        if name in FILES_TO_DELETE:
            to_delete.append(f)
            continue

        # 3. Match por normalización directa (normalizar también el nombre del archivo)
        name_normalized = normalize_name(name)
        if name_normalized in norm_to_id:
            file_to_id[f] = norm_to_id[name_normalized]
            continue

        # 3b. Match sin normalizar (por si el nombre ya coincide exacto)
        if name in norm_to_id:
            file_to_id[f] = norm_to_id[name]
            continue

        # 4. Sin match
        unresolved.append(f)

    # Verificar IDs asignados
    assigned_ids = set(file_to_id.values())
    missing_ids = valid_ids - assigned_ids

    print(f"\n✅ Coinciden (se renombrarán): {len(file_to_id)}")
    print(f"🗑️ Sobran (se eliminarán): {len(to_delete)}")
    print(f"❓ Sin resolver: {len(unresolved)}")
    print(f"⚠️ IDs del Excel sin audio: {len(missing_ids)}")

    if to_delete:
        print("\n=== SE ELIMINARÁN ===")
        for f in sorted(to_delete):
            print(f"  🗑️ {f}")

    if unresolved:
        print("\n=== SIN RESOLVER (requieren mapeo manual) ===")
        for f in sorted(unresolved):
            print(f"  ❓ {f}")

    if missing_ids:
        print("\n=== IDs SIN AUDIO ===")
        for id_val in sorted(missing_ids):
            entry = next((e for e in excel_entries if e[0] == id_val), None)
            if entry:
                print(f"  ⚠️ {id_val}: {entry[1]}")

    print(f"\n=== RENOMBRAMIENTOS ===")
    for f, new_id in sorted(file_to_id.items(), key=lambda x: x[1]):
        ext = os.path.splitext(f)[1]
        print(f"  {f} -> {new_id}{ext}")

    if dry_run:
        print("\n🔍 DRY-RUN completado. No se realizaron cambios.")
        return

    # Ejecutar cambios
    print(f"\n{'='*60}")
    print("🚀 Ejecutando cambios...")

    # Paso 1: Eliminar extras
    deleted = 0
    for f in to_delete:
        path = os.path.join(audio_dir, f)
        os.remove(path)
        deleted += 1

    # Paso 2: Renombrar con nombres temporales
    temp_map = {}
    for f, new_id in file_to_id.items():
        ext = os.path.splitext(f)[1]
        temp_name = f'__temp__{new_id}{ext}'
        src = os.path.join(audio_dir, f)
        tmp = os.path.join(audio_dir, temp_name)
        os.rename(src, tmp)
        temp_map[temp_name] = f'{new_id}{ext}'

    # Paso 3: Renombrar de temporal a final
    for temp_name, final_name in temp_map.items():
        src = os.path.join(audio_dir, temp_name)
        dst = os.path.join(audio_dir, final_name)
        os.rename(src, dst)

    # Verificar resultado
    final_files = sorted(os.listdir(audio_dir))
    print(f"\n✅ Renombrados: {len(file_to_id)}")
    print(f"🗑️ Eliminados: {deleted}")
    print(f"📁 Archivos finales: {len(final_files)}")
    if final_files:
        print(f"   Primeros: {final_files[:5]}")
        print(f"   Últimos:  {final_files[-5:]}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
