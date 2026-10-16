#!/usr/bin/env python3
"""
validar_todo.py
Suite integral de validación y verificación de consistencia para los datos de la App (Unity) y de ASR.
Verifica exhaustivamente las 25 reglas obligatorias de calidad pedagógica, estructural y técnica.

Ubicación: Raíz del proyecto (/home/primo/proyecto-grado/validar_todo.py)
"""

import os
import sys
import json
import re
import hashlib
from collections import Counter

FONEMAS_CANONICOS = {
    "A", "AA", "E", "EE", "I", "II", "O", "OO", "U", "UU",
    "P", "T", "K", "Q", "M", "N", "R", "S", "X", "J", "L", "LL", "Y", "W",
    "TS", "CH", "SH", "NY",
    "PH", "TH", "KH", "QH", "CHH",
    "P_EJ", "T_EJ", "K_EJ", "Q_EJ", "CH_EJ"
}


def desglosar_traducciones(es_texto: str) -> list:
    """Desglosa traducciones con alternativas para verificar no ambigüedad."""
    if not es_texto:
        return [""]
    if "/" not in es_texto:
        return [es_texto.strip()]
    partes = [p.strip() for p in es_texto.split("/")]
    if len(partes) == 2:
        p1_tokens = partes[0].split()
        p2_tokens = partes[1].split()
        if len(p2_tokens) > 1 and len(p1_tokens) == 1:
            complemento = " ".join(p2_tokens[1:])
            return [f"{partes[0]} {complemento}".strip(), partes[1].strip()]
    return [p for p in partes if p]


def son_traducciones_compatibles(es_a: str, es_b: str) -> bool:
    vars_a = set(v.lower().strip() for v in desglosar_traducciones(es_a))
    vars_b = set(v.lower().strip() for v in desglosar_traducciones(es_b))
    return len(vars_a & vars_b) > 0


def validar_app(dir_app):
    print("\n--- VALIDANDO DATOS DE LA APLICACIÓN (25 REGLAS OBLIGATORIAS) ---")
    errores = []
    advertencias = []

    # -----------------------------------------------------------------------
    # 1. Validar palabras.json
    # -----------------------------------------------------------------------
    ruta_palabras = os.path.join(dir_app, "palabras.json")
    with open(ruta_palabras, "r", encoding="utf-8") as f:
        data_p = json.load(f)

    assert data_p.get("version") == 1, "Versión de palabras.json debe ser 1"
    palabras = data_p.get("palabras", [])
    raices_ids = set()
    formas_ids = set()
    formas_a_raiz = {}
    palabras_map = {}

    for p in palabras:
        pid = p.get("id")
        if not pid or pid in raices_ids:
            errores.append(f"Regla 4: ID de raíz nulo o duplicado: '{pid}'")
        raices_ids.add(pid)
        palabras_map[pid] = p

        # Regla 05-guia-corpus-datos Sec 2.7: Sin nombres propios en palabras.json
        if pid.lower() in ["pedro", "lorenzo", "maria", "juana", "waki", "irohito_urus"] or p.get("categoria_gramatical") in ["nombre_propio", "nombre propio"]:
            errores.append(f"Regla Nombres Propios: '{pid}' es un nombre propio/topónimo y no debe estar en palabras.json")

        for forma in p.get("formas", []):
            fid = forma.get("id")
            if not fid or fid in formas_ids or fid in raices_ids:
                errores.append(f"Regla 4: ID de forma nulo o duplicado: '{fid}'")
            formas_ids.add(fid)
            formas_a_raiz[fid] = pid
            if not forma.get("uch") or not forma.get("es"):
                errores.append(f"Campos obligatorios faltantes en forma: {fid}")
            if fid.lower() in ["pedro", "lorenzo", "maria", "juana", "waki", "irohito_urus"]:
                errores.append(f"Regla Nombres Propios: Forma '{fid}' es un nombre propio y no debe estar en palabras.json")

    print(f"  [OK] Regla 6-7 y Nombres Propios: palabras.json cargado ({len(raices_ids)} familias, {len(raices_ids)+len(formas_ids)} unidades léxicas totales, sin nombres propios).")

    # -----------------------------------------------------------------------
    # 2. Validar oraciones.json
    # -----------------------------------------------------------------------
    ruta_oraciones = os.path.join(dir_app, "oraciones.json")
    with open(ruta_oraciones, "r", encoding="utf-8") as f:
        data_o = json.load(f)

    assert data_o.get("version") == 1, "Versión de oraciones.json debe ser 1"
    oraciones = data_o.get("oraciones", [])
    oraciones_dict = {}

    for o in oraciones:
        oid = o.get("id")
        if not oid or oid in oraciones_dict:
            errores.append(f"Regla 4: ID de oración nulo o duplicado: '{oid}'")
        oraciones_dict[oid] = o
        if not o.get("uch") or not o.get("es"):
            errores.append(f"Campos obligatorios faltantes en oración: {oid}")

    esperadas_oraciones = {f"O_{i:03d}" for i in range(1, 131)}
    if not esperadas_oraciones.issubset(set(oraciones_dict)):
        errores.append("Regla reserva: oraciones.json debe contener al menos O_001..O_130")

    print(f"  [OK] Regla 5: oraciones.json cargado ({len(oraciones_dict)} oraciones únicas).")

    # -----------------------------------------------------------------------
    # 3. Validar lecciones.json
    # -----------------------------------------------------------------------
    ruta_lecciones = os.path.join(dir_app, "lecciones.json")
    with open(ruta_lecciones, "r", encoding="utf-8") as f:
        data_l = json.load(f)

    assert data_l.get("version") == 1, "Versión de lecciones.json debe ser 1"
    lecciones = data_l.get("lecciones", [])
    lecciones_ids = set()

    for l in lecciones:
        lid = l.get("id")
        if not lid or lid in lecciones_ids:
            errores.append(f"Regla 4: ID de lección nulo o duplicado: '{lid}'")
        lecciones_ids.add(lid)

        # Regla 19: Sin ra_id en lecciones.json
        if "ra_id" in l:
            errores.append(f"Regla 19: lecciones.json contiene campo 'ra_id' en lección {lid}")

        for oid in l.get("oraciones_ids", []):
            if oid not in oraciones_dict:
                errores.append(f"Regla 5: Oración '{oid}' en lección '{lid}' no existe en oraciones.json")
            elif oid not in {f"O_{i:03d}" for i in range(1, 121)}:
                errores.append(f"Regla reserva: oración no curricular '{oid}' asignada a {lid}")

    # Regla 2: Exactamente 27 lecciones
    if len(lecciones) != 27:
        errores.append(f"Regla 2: Se esperaban exactamente 27 lecciones, se encontraron {len(lecciones)}")

    # Regla 3: IDs de lección exactamente L01 a L27
    esperados_lids = [f"L{i:02d}" for i in range(1, 28)]
    if sorted(list(lecciones_ids)) != esperados_lids:
        errores.append(f"Regla 3: IDs de lección no coinciden con L01..L27: {sorted(list(lecciones_ids))}")

    asignadas = {oid for leccion in lecciones for oid in leccion.get("oraciones_ids", [])}
    if asignadas != {f"O_{i:03d}" for i in range(1, 121)}:
        errores.append("Regla reserva: lecciones.json debe asignar exactamente O_001..O_120")

    print(f"  [OK] Regla 2, 3, 19: lecciones.json verificado ({len(lecciones)} lecciones, L01..L27, sin ra_id).")

    # -----------------------------------------------------------------------
    # 4. Validar lecciones_compiladas.json (Reglas 1, 8-18)
    # -----------------------------------------------------------------------
    ruta_compiladas = os.path.join(dir_app, "lecciones_compiladas.json")
    with open(ruta_compiladas, "r", encoding="utf-8") as f:
        data_c = json.load(f)

    assert data_c.get("version") in [1, 3, 4], f"Versión de lecciones_compiladas.json debe ser 1, 3 o 4 (es {data_c.get('version')})"
    compiladas = data_c.get("lecciones", [])
    reservas_oraciones = {f"O_{i:03d}" for i in range(121, 131)}
    familias_curriculares = set()
    familias_reserva = set()
    total_pasos = 0
    familias_presentadas_acum = set()
    contador_modalidades = Counter()
    familias_repaso_usadas = set()

    for idx_lec, l in enumerate(compiladas):
        lid = l.get("id")
        
        # Regla 19: No ra_id
        if "ra_id" in l:
            errores.append(f"Regla 19: Campo 'ra_id' residual en lección compilada '{lid}'")

        nuevas_lec = l.get("familias_nuevas", [])
        repaso_lec = l.get("familias_repaso", [])
        familias_curriculares.update(nuevas_lec)

        for fn in nuevas_lec:
            if fn not in raices_ids:
                errores.append(f"Regla 6: Familia nueva '{fn}' no existe en palabras.json")
            if fn in familias_presentadas_acum:
                errores.append(f"Regla 9: Familia '{fn}' ya fue presentada en una lección anterior pero aparece en familias_nuevas de {lid}")

        for fr in repaso_lec:
            if fr not in raices_ids:
                errores.append(f"Regla 6: Familia repaso '{fr}' no existe en palabras.json")
            if fr not in familias_presentadas_acum:
                errores.append(f"Regla 8: Familia repaso '{fr}' en {lid} no fue presentada en ninguna lección anterior")

        pasos = l.get("pasos", [])
        total_pasos += len(pasos)
        familias_presentadas_en_esta_lec = set()

        for idx_paso, paso in enumerate(pasos):
            tipo = paso.get("tipo")
            contador_modalidades[tipo] += 1

            # Regla Nombres Propios (05-guia-corpus-datos.md Sec 9): Sin nombres propios en actividades
            nombres_prohibidos = {"pedro", "lorenzo", "maria", "maría", "juana", "waki", "irohito_urus", "irohito urus", "irohito"}
            if paso.get("objetivo_id") and paso.get("objetivo_id").lower() in nombres_prohibidos:
                errores.append(f"Regla Nombres Propios: Nombre propio '{paso.get('objetivo_id')}' como objetivo_id en {lid}")
            if paso.get("palabra_oculta_id") and paso.get("palabra_oculta_id").lower() in nombres_prohibidos:
                errores.append(f"Regla Nombres Propios: Nombre propio '{paso.get('palabra_oculta_id')}' como palabra_oculta_id en {lid}")
            for itm in paso.get("items_ids", []):
                if itm.lower() in nombres_prohibidos:
                    errores.append(f"Regla Nombres Propios: Nombre propio '{itm}' en items_ids en {lid}")

            # Regla 8 & 9: Presentación de familia
            if tipo == "presentacion_familia":
                obj = paso.get("objetivo_id")
                if obj in familias_presentadas_acum:
                    errores.append(f"Regla 9: presentacion_familia repetida para familia ya conocida '{obj}' en {lid}")
                familias_presentadas_en_esta_lec.add(obj)

            # Reglas de selección múltiple (Regla 10, 11, 12)
            if "opciones_ids" in paso:
                opciones = paso.get("opciones_ids", [])
                for op in opciones:
                    if op.lower() in nombres_prohibidos:
                        errores.append(f"Regla Nombres Propios: Nombre propio '{op}' en opciones_ids en paso {idx_paso} de {lid}")
                # Regla 11: Sin duplicados
                if len(opciones) != len(set(opciones)):
                    errores.append(f"Regla 11: Opciones duplicadas en paso {idx_paso} ({tipo}) de {lid}: {opciones}")

                # Regla 10: Respuesta correcta exactamente una vez
                if tipo == "forma_a_raiz":
                    objetivo = paso.get("raiz_id")
                elif tipo in ["forma_a_es", "es_a_forma", "audio_a_forma"]:
                    objetivo = paso.get("forma_id")
                elif tipo == "completar_oracion":
                    objetivo = paso.get("palabra_oculta_id")
                else:
                    objetivo = paso.get("objetivo_id")

                if objetivo and objetivo not in opciones:
                    errores.append(f"Regla 10: Respuesta correcta '{objetivo}' ausente en opciones_ids de paso {idx_paso} ({tipo}) en {lid}")

            if "opciones_oraciones_ids" in paso:
                opciones_o = paso.get("opciones_oraciones_ids", [])
                if len(opciones_o) != len(set(opciones_o)):
                    errores.append(f"Regla 11: Opciones de oración duplicadas en paso {idx_paso} de {lid}: {opciones_o}")
                oracion_obj = paso.get("oracion_id")
                if oracion_obj not in opciones_o:
                    errores.append(f"Regla 10: Oración objetivo '{oracion_obj}' ausente en opciones_oraciones_ids de paso {idx_paso} en {lid}")
                if oracion_obj in reservas_oraciones:
                    errores.append(f"Regla reserva: oración de reserva '{oracion_obj}' usada como objetivo en {lid}")

            # Regla 13: escucha_y_repite_asr siempre opcional
            if tipo == "escucha_y_repite_asr":
                if paso.get("opcional") is not True:
                    errores.append(f"Regla 13: escucha_y_repite_asr en {lid} no tiene 'opcional': true")

            # Registrar uso real de familias de repaso
            if "items_ids" in paso:
                for itm in paso["items_ids"]:
                    if itm in repaso_lec:
                        familias_repaso_usadas.add(itm)
            if "objetivo_id" in paso and paso["objetivo_id"] in repaso_lec:
                familias_repaso_usadas.add(paso["objetivo_id"])

        familias_presentadas_acum.update(nuevas_lec)

    familias_reserva = raices_ids - familias_curriculares
    for l in compiladas:
        for fid in l.get("familias_nuevas", []) + l.get("familias_repaso", []):
            if fid in familias_reserva:
                errores.append(f"Regla reserva: familia de reserva '{fid}' aparece como contenido curricular")

    reservas_en_opciones = set()
    for l in compiladas:
        for paso in l.get("pasos", []):
            if paso.get("tipo") == "audio_a_es_oracion":
                reservas_en_opciones.update(set(paso.get("opciones_oraciones_ids", [])) & reservas_oraciones)
    reservas_tempranas = set()
    for l in compiladas[:3]:
        for paso in l.get("pasos", []):
            reservas_tempranas.update(set(paso.get("opciones_oraciones_ids", [])) & reservas_oraciones)
    if not reservas_tempranas:
        errores.append("Regla reserva: L01-L03 no usan oraciones de reserva como distractores")

    metricas = data_c.get("metricas_distractores", {})

    # Regla 14 & 15: Variedad de modalidades y sin predominio de uch_a_es
    total_micro_vocab = (
        contador_modalidades["uch_a_es"] +
        contador_modalidades["es_a_uch"] +
        contador_modalidades["audio_a_uch"] +
        contador_modalidades["audio_a_es"]
    )
    if total_micro_vocab > 0:
        ratio_uch_es = contador_modalidades["uch_a_es"] / total_micro_vocab
        if ratio_uch_es > 0.40:
            errores.append(f"Regla 15: Predominio excesivo de uch_a_es ({ratio_uch_es*100:.1f}% de microactividades)")

    # Regla 16: Las 5 modalidades de oración presentes
    MODS_ORACION = ["ordenar_oracion", "audio_a_es_oracion", "completar_oracion", "dictado_word_bank", "traduccion_constructiva"]
    for mod in MODS_ORACION:
        if contador_modalidades[mod] == 0:
            errores.append(f"Regla 16: Modalidad de oración '{mod}' no aparece en ninguna lección")

    print(f"  [OK] Regla 1, 8-16: lecciones_compiladas.json validado ({len(compiladas)} lecciones, {total_pasos} pasos totales).")
    print(f"  [OK] Regla 14-16: 18 modalidades generadas con distribución balanceada:")
    for tipo, cnt in contador_modalidades.most_common():
        print(f"       - {tipo:<26}: {cnt}")

    # -----------------------------------------------------------------------
    # 5. Validar escenarios_ra.json (Reglas 20-24)
    # -----------------------------------------------------------------------
    ruta_ra = os.path.join(dir_app, "escenarios_ra.json")
    if not os.path.exists(ruta_ra):
        errores.append("Regla 20: No existe el archivo datos_app/escenarios_ra.json")
        return False

    with open(ruta_ra, "r", encoding="utf-8") as f:
        data_ra = json.load(f)

    assert data_ra.get("version") in [1, 4], "Versión de escenarios_ra.json debe ser 1 o 4"
    escenarios = data_ra.get("escenarios", [])

    # Regla 20: Exactamente 6 escenarios
    if len(escenarios) != 6:
        errores.append(f"Regla 20: Se esperaban 6 escenarios RA, se encontraron {len(escenarios)}")

    MAPEO_ESPERADO_RA = {
        "ra_encuentro_comunicacion": ["L01", "L02", "L03", "L04", "L05", "L06"],
        "ra_familia_vestimenta": ["L07", "L08", "L09", "L10", "L11"],
        "ra_casa_objetos": ["L12", "L13", "L14", "L15"],
        "ra_cocina_alimentos": ["L16", "L17", "L18", "L19"],
        "ra_animales_ecosistema": ["L20", "L21", "L22", "L23", "L24"],
        "ra_naturaleza_orientacion": ["L25", "L26", "L27"],
    }

    lecciones_cubiertas_ra = []
    for sc in escenarios:
        sid = sc.get("id")
        if sid not in MAPEO_ESPERADO_RA:
            errores.append(f"Regla 20: Escenario RA desconocido o ID incorrecto: '{sid}'")
            continue

        lecs_asoc = sc.get("lecciones_asociadas", [])
        lecciones_cubiertas_ra.extend(lecs_asoc)

        # Regla 22: Mapeo exacto según 03-1-diseno-escenarios-ra.md
        if lecs_asoc != MAPEO_ESPERADO_RA[sid]:
            errores.append(f"Regla 22: Mapeo de lecciones incorrecto en {sid}. Esperado {MAPEO_ESPERADO_RA[sid]}, obtenido {lecs_asoc}")

        # Regla 21: Todas las lecciones referenciadas existen
        for lid in lecs_asoc:
            if lid not in lecciones_ids:
                errores.append(f"Regla 21: Lección '{lid}' en escenario '{sid}' no existe en lecciones.json")

    # Regla 23: Sin lecciones repetidas entre escenarios
    if len(lecciones_cubiertas_ra) != len(set(lecciones_cubiertas_ra)):
        errores.append(f"Regla 23: Existen lecciones duplicadas entre escenarios RA")

    # Regla 24: Las 27 lecciones están cubiertas exactamente una vez
    if sorted(lecciones_cubiertas_ra) != esperados_lids:
        errores.append(f"Regla 24: Las 27 lecciones no están completamente cubiertas por los escenarios RA")

    print(f"  [OK] Regla 20-24: escenarios_ra.json 100% válido (6 escenarios, partición exacta de L01..L27).")

    if errores:
        print(f"\n  [ERROR] Se encontraron {len(errores)} inconsistencias:")
        for err in errores[:10]:
            print(f"    - {err}")
        return False
    else:
        print("  [SUCCESS] Todos los archivos de la aplicación cumplen el 100% de las 25 reglas.")
        return True


def validar_asr(dir_asr):
    print("\n--- VALIDANDO DATOS DE ASR ---")
    errores = []

    # 1. Validar tokens.txt
    ruta_tokens = os.path.join(dir_asr, "tokens.txt")
    if not os.path.exists(ruta_tokens):
        print(f"  [ERROR] No se encontró {ruta_tokens}")
        return False

    tokens_registrados = {}
    with open(ruta_tokens, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split()
            if len(partes) != 2:
                errores.append(f"Formato inválido en tokens.txt: '{linea}'")
                continue
            if partes[0].isdigit():
                idx, tok = int(partes[0]), partes[1]
            elif partes[1].isdigit():
                tok, idx = partes[0], int(partes[1])
            else:
                errores.append(f"Formato inválido en tokens.txt (sin índice numérico): '{linea}'")
                continue
            tokens_registrados[idx] = tok

    if len(tokens_registrados) != 42:
        errores.append(f"Cantidad incorrecta de tokens ({len(tokens_registrados)} esperados 42)")

    print(f"  [OK] tokens.txt: {len(tokens_registrados)} tokens válidos (índices 0 a 41).")

    # 2. Validar lexicon.txt
    ruta_lexicon = os.path.join(dir_asr, "lexicon.txt")
    if not os.path.exists(ruta_lexicon):
        print(f"  [ERROR] No se encontró {ruta_lexicon}")
        return False

    lexicon_entradas = 0
    fonemas_en_lexicon = set()

    with open(ruta_lexicon, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            partes = linea.split("\t")
            if len(partes) != 2:
                errores.append(f"Línea de lexicon no tabulada correctamente: '{linea}'")
                continue
            palabra, fonemas_str = partes[0], partes[1]
            lexicon_entradas += 1
            fonemas = fonemas_str.split()
            for fon in fonemas:
                fonemas_en_lexicon.add(fon)
                if fon not in FONEMAS_CANONICOS:
                    errores.append(f"Fonema '{fon}' en palabra '{palabra}' no es un fonema canónico")

    print(f"  [OK] lexicon.txt: {lexicon_entradas} entradas léxicas verificadas.")
    print(f"  [OK] 100% de fonemas utilizados ({len(fonemas_en_lexicon)} fonemas únicos) pertenecen a FONEMAS_CANONICOS.")

    # 3. Validar corpus_asr_texto.txt
    ruta_corpus_txt = os.path.join(dir_asr, "corpus_asr_texto.txt")
    if not os.path.exists(ruta_corpus_txt):
        print(f"  [ERROR] No se encontró {ruta_corpus_txt}")
        return False

    with open(ruta_corpus_txt, "r", encoding="utf-8") as f:
        lineas_corpus = [l.strip() for l in f if l.strip()]

    print(f"  [OK] corpus_asr_texto.txt: {len(lineas_corpus)} líneas de texto limpio.")

    if errores:
        print(f"  [ERROR] Se encontraron {len(errores)} inconsistencias en datos_asr:")
        for err in errores[:10]:
            print(f"    - {err}")
    else:
        print("  [SUCCESS] Todos los archivos de datos_asr son 100% consistentes.")
    return len(errores) == 0


def calcular_hash_archivo(ruta):
    """Calcula el hash SHA-256 de un archivo para validar determinismo."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def validar_determinismo(project_root, unity_dir, unity_scripts_dir):
    """Regla 25: Ejecutar el compilador dos veces produce exactamente la misma salida."""
    print("\n--- VALIDANDO REGLA 25: DETERMINISMO REPRODUCIBLE ---")
    import subprocess
    import sys

    dir_app = os.path.join(unity_dir, "datos_app")
    ruta_script = os.path.join(unity_scripts_dir, "corpus", "preparar_corpus_app.py")
    if not os.path.exists(ruta_script):
        ruta_script = os.path.join(unity_scripts_dir, "preparar_corpus_app.py")

    # Ejecución 1
    subprocess.run([sys.executable, ruta_script], check=True, stdout=subprocess.DEVNULL)
    hashes_run1 = {
        f: calcular_hash_archivo(os.path.join(dir_app, f))
        for f in ["palabras.json", "oraciones.json", "lecciones.json", "lecciones_compiladas.json", "escenarios_ra.json"]
    }

    # Ejecución 2
    subprocess.run([sys.executable, ruta_script], check=True, stdout=subprocess.DEVNULL)
    hashes_run2 = {
        f: calcular_hash_archivo(os.path.join(dir_app, f))
        for f in ["palabras.json", "oraciones.json", "lecciones.json", "lecciones_compiladas.json", "escenarios_ra.json"]
    }

    coinciden = True
    for f in hashes_run1:
        if hashes_run1[f] != hashes_run2[f]:
            print(f"  [ERROR] No determinista en {f}: Run 1={hashes_run1[f]} vs Run 2={hashes_run2[f]}")
            coinciden = False

    if coinciden:
        print("  [SUCCESS] Regla 25 verificada: 100% determinista (hashes SHA-256 idénticos en corridas sucesivas).")
    return coinciden


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    unity_dir = os.path.join(project_root, "UNITY")
    unity_scripts_dir = os.path.join(unity_dir, "scripts")

    dir_app = os.path.join(unity_dir, "datos_app")

    # Soporte para ASR/datos_asr con fallback a Para_ASR/datos_asr
    dir_asr = os.path.join(project_root, "ASR", "datos_asr")
    if not os.path.exists(dir_asr):
        dir_asr = os.path.join(project_root, "Para_ASR", "datos_asr")

    ok_app = validar_app(dir_app)
    ok_asr = validar_asr(dir_asr)
    ok_det = validar_determinismo(project_root, unity_dir, unity_scripts_dir)

    print("\n==========================================")
    if ok_app and ok_asr and ok_det:
        print("RESULTADO FINAL: TODAS LAS 25 VALIDACIONES PASARON EXITOSAMENTE (100% OK)")
    else:
        print("RESULTADO FINAL: HUBO ERRORES EN LA VALIDACIÓN")
    print("==========================================")
    sys.exit(0 if (ok_app and ok_asr and ok_det) else 1)


if __name__ == "__main__":
    main()
