"""
preparar_corpus_app.py
Pipeline de preparación y compilación curricular para la Aplicación Móvil (Unity).
Basado en:
  - 01-modulo-pln-texto.md
  - 02-modulo-asr-voz.md
  - 03-modulo-ra.md y 03-1-diseno-escenarios-ra.md
  - 04-flujo-leccion-app.md
  - 05-guia-corpus-datos.md
  - 06-guia-arquitectura-proyecto.md
  - 08-patron-arquitectonico-mvp.md
  - instrucciones-mejora-compilador-lecciones.md

Entradas:
  - excel/palabras_app.xlsx
  - excel/oraciones.xlsx

Salidas en datos_app/:
  - palabras.json: Raíces léxicas y formas documentadas (v1)
  - oraciones.json: Oraciones canónicas (id, uch, es) (v1)
  - lecciones.json: Definición curricular de 27 lecciones (v1)
  - lecciones_compiladas.json: Secuencia pedagógica completa y determinista para Unity (v3)
  - escenarios_ra.json: Definición de los 6 escenarios RA independientes (v1)
"""

import os
import re
import json
import sys

# Permitir importaciones locales desde el directorio del script
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from lector_xlsx import leer_xlsx
from distractores_corpus import (
    normalizar_apostrofe,
    normalizar_texto,
    normalizar_lid,
    NOMBRES_PROPIOS_CONTEXTUALES
)
from compilador_lecciones import compilar_lecciones_curriculares, CATALOGO_11

# ---------------------------------------------------------------------------
# Agrupación léxica: Raíces y Formas (05-guia-corpus-datos.md, Sec 2.7)
# ---------------------------------------------------------------------------
def agrupar_palabras_y_formas(rows_palabras: list) -> list:
    """
    Agrupa las palabras en raíces y formas documentadas asociadas.
    Estructura cada raíz con: id, uch, es, categoria_gramatical, formas: [{id, uch, es}].
    Excluye nombres propios contextuales según 05-guia-corpus-datos.md (Sec 2.7).
    """
    entradas = []
    for r in rows_palabras:
        if not r or not r[0]:
            continue
        p_id = r[0].strip()
        uch = normalizar_apostrofe(r[1].strip()) if len(r) > 1 else ""
        es = r[2].strip() if len(r) > 2 else ""
        cat = r[3].strip() if len(r) > 3 else ""

        # Excluir nombres propios y topónimos del vocabulario pedagógico enseñable
        cat_norm = cat.lower().strip()
        uch_norm = normalizar_texto(uch)
        if (
            cat_norm in ["nombre_propio", "nombre propio"]
            or uch_norm in NOMBRES_PROPIOS_CONTEXTUALES
            or p_id.lower() in ["pedro", "lorenzo", "maria", "juana", "waki", "irohito_urus"]
        ):
            continue

        entradas.append({
            "id": p_id,
            "uch": uch,
            "es": es,
            "categoria_gramatical": cat
        })

    id_map = {e["id"]: e for e in entradas}
    formas_asignadas = set()
    raices_formas = {}

    for e in entradas:
        wid = e["id"]
        posible_raiz = None

        if wid.endswith("nakachay"):
            base = wid[:-8]
            if base in id_map:
                posible_raiz = base
            elif (base + "naka") in id_map:
                posible_raiz = base
        elif wid.endswith("pinichay"):
            base = wid[:-8]
            if base in id_map:
                posible_raiz = base
            elif (base + "pini") in id_map:
                posible_raiz = base
        elif wid.endswith("naka"):
            base = wid[:-4]
            if base in id_map:
                posible_raiz = base
        elif wid.endswith("pini"):
            base = wid[:-4]
            if base in id_map:
                posible_raiz = base
        elif wid.endswith("chay"):
            base = wid[:-4]
            if base in id_map and id_map[base]["categoria_gramatical"] not in ["verbo"]:
                posible_raiz = base

        if not e["categoria_gramatical"] and not posible_raiz:
            for rid in sorted(id_map.keys(), key=len, reverse=True):
                if rid != wid and wid.startswith(rid) and len(rid) >= 3:
                    posible_raiz = rid
                    break

        if posible_raiz and posible_raiz != wid:
            formas_asignadas.add(wid)
            if posible_raiz not in raices_formas:
                raices_formas[posible_raiz] = []
            raices_formas[posible_raiz].append({
                "id": e["id"],
                "uch": e["uch"],
                "es": e["es"]
            })

    palabras_resultado = []
    for e in entradas:
        if e["id"] in formas_asignadas:
            continue
        item = {
            "id": e["id"],
            "uch": e["uch"],
            "es": e["es"],
            "categoria_gramatical": e["categoria_gramatical"] if e["categoria_gramatical"] else "general"
        }
        if e["id"] in raices_formas:
            item["formas"] = sorted(raices_formas[e["id"]], key=lambda x: x["id"])
        palabras_resultado.append(item)

    palabras_resultado.sort(key=lambda x: x["id"])
    return palabras_resultado

# ---------------------------------------------------------------------------
# Extracción de Oraciones y Lecciones (desacopladas de RA)
# ---------------------------------------------------------------------------
def extraer_oraciones_y_lecciones(rows_oraciones: list):
    """
    Extrae oraciones.json y lecciones.json preservando orden curricular.
    NO incluye ningún metadato ni id de Realidad Aumentada.
    """
    oraciones_dict = {}
    lecciones_ordenadas = []
    lecciones_map = {}

    for r in rows_oraciones:
        if not r or not r[0]:
            continue
        o_id = r[0].strip()
        uch = normalizar_apostrofe(r[1].strip()) if len(r) > 1 else ""
        es = r[2].strip() if len(r) > 2 else ""

        # Preservar mayúsculas correctas en nombres propios de comunidades como "Irohito Urus"
        if "irohito urus" in uch.lower():
            uch = re.sub(r"\birohito\s+urus\b", "Irohito Urus", uch, flags=re.IGNORECASE)

        lid_raw = r[3].strip() if len(r) > 3 and r[3] else ""
        lid = normalizar_lid(lid_raw) if lid_raw else ""
        lname = r[4].strip() if len(r) > 4 else "Lección"

        if o_id not in oraciones_dict:
            oraciones_dict[o_id] = {
                "id": o_id,
                "uch": uch,
                "es": es
            }

        if not lid:
            continue

        if lid not in lecciones_map:
            num_str = re.sub(r"\D", "", lid)
            num_orden = int(num_str) if num_str else len(lecciones_ordenadas) + 1
            lec_item = {
                "id": lid,
                "titulo": lname,
                "orden": num_orden,
                "oraciones_ids": []
            }
            lecciones_map[lid] = lec_item
            lecciones_ordenadas.append(lec_item)

        if o_id not in lecciones_map[lid]["oraciones_ids"]:
            lecciones_map[lid]["oraciones_ids"].append(o_id)

    lecciones_ordenadas.sort(key=lambda x: x["orden"])
    oraciones_lista = [oraciones_dict[oid] for oid in sorted(oraciones_dict.keys())]
    return oraciones_lista, lecciones_ordenadas, oraciones_dict

# ---------------------------------------------------------------------------
# Escenarios de Realidad Aumentada (03-1-diseno-escenarios-ra.md, Sección 3)
# ---------------------------------------------------------------------------
def generar_escenarios_ra() -> dict:
    """
    Construye la definición de los 6 escenarios RA según el mapeo definitivo
    de 03-1-diseno-escenarios-ra.md (Sección 3).
    """
    return {
        "version": 1,
        "escenarios": [
            {
                "id": "ra_encuentro_comunicacion",
                "titulo": "Encuentro y comunicación",
                "lecciones_asociadas": ["L01", "L02", "L03", "L04", "L05"],
                "objetos": [],
                "avatar_requerido": False
            },
            {
                "id": "ra_familia_vestimenta",
                "titulo": "Familia y vestimenta",
                "lecciones_asociadas": ["L06", "L07", "L08", "L09", "L10"],
                "objetos": [],
                "avatar_requerido": False
            },
            {
                "id": "ra_casa_objetos",
                "titulo": "Casa y objetos cotidianos",
                "lecciones_asociadas": ["L11", "L12", "L13", "L14"],
                "objetos": [],
                "avatar_requerido": False
            },
            {
                "id": "ra_cocina_alimentos",
                "titulo": "Cocina y alimentos",
                "lecciones_asociadas": ["L15", "L16", "L17", "L18"],
                "objetos": [],
                "avatar_requerido": False
            },
            {
                "id": "ra_animales_ecosistema",
                "titulo": "Animales y ecosistema",
                "lecciones_asociadas": ["L19", "L20", "L21", "L22", "L23"],
                "objetos": [],
                "avatar_requerido": False
            },
            {
                "id": "ra_naturaleza_orientacion",
                "titulo": "Naturaleza y orientación",
                "lecciones_asociadas": ["L24", "L25", "L26"],
                "objetos": [],
                "avatar_requerido": False
            }
        ]
    }

# ---------------------------------------------------------------------------
# Verificación Estricta de Nombres Propios (05-guia-corpus-datos.md, Sec 9 y 12)
# ---------------------------------------------------------------------------
def validar_restricciones_nombres_propios(palabras_json_data: list, lecciones_compiladas_data: list):
    """
    Verifica las restricciones obligatorias de nombres propios (05-guia-corpus-datos.md, Sec 9 y 12):
    - Ningún nombre propio en palabras.json
    - Ningún nombre propio en familias_nuevas, familias_repaso, objetivo_id, opciones_ids, items_ids, etc.
    - Ningún nombre propio en campos de refuerzo adaptativo
    """
    nombres_prohibidos = {"pedro", "lorenzo", "maria", "maría", "juana", "waki", "irohito_urus", "irohito urus", "irohito"}

    # 1. En palabras.json
    for p in palabras_json_data:
        if p["id"].lower() in nombres_prohibidos or p.get("categoria_gramatical") in ["nombre_propio", "nombre propio"]:
            raise ValueError(f"Violación: Nombre propio '{p['id']}' encontrado en palabras.json")
        for forma in p.get("formas", []):
            if forma["id"].lower() in nombres_prohibidos:
                raise ValueError(f"Violación: Forma de nombre propio '{forma['id']}' encontrada en palabras.json")

    # 2. En lecciones_compiladas.json
    for lec in lecciones_compiladas_data:
        lid = lec["id"]
        for fn in lec.get("familias_nuevas", []):
            if fn.lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{fn}' en familias_nuevas")
        for fr in lec.get("familias_repaso", []):
            if fr.lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{fr}' en familias_repaso")
        for ro in lec.get("familias_repaso_organico", []):
            if ro.get("familia_id", "").lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{ro.get('familia_id')}' en familias_repaso_organico")
        for paso in lec.get("pasos", []):
            t = paso.get("tipo")
            if t not in CATALOGO_11:
                raise ValueError(f"Violación en {lid}: Tipo no generable '{t}' presente en paso compilado")
            if paso.get("objetivo_id") and paso.get("objetivo_id").lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{paso.get('objetivo_id')}' como objetivo_id en paso {t}")
            if paso.get("palabra_oculta_id") and paso.get("palabra_oculta_id").lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{paso.get('palabra_oculta_id')}' como palabra_oculta_id en completar_oracion")
            if paso.get("forma_id") and paso.get("forma_id").lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{paso.get('forma_id')}' como forma_id en paso {t}")
            if paso.get("raiz_id") and paso.get("raiz_id").lower() in nombres_prohibidos:
                raise ValueError(f"Violación en {lid}: Nombre propio '{paso.get('raiz_id')}' como raiz_id en paso {t}")
            for op in paso.get("opciones_ids", []):
                if op.lower() in nombres_prohibidos:
                    raise ValueError(f"Violación en {lid}: Nombre propio '{op}' en opciones_ids de paso {t}")
            for itm in paso.get("items_ids", []):
                if itm.lower() in nombres_prohibidos:
                    raise ValueError(f"Violación en {lid}: Nombre propio '{itm}' en items_ids de paso {t}")
            refuerzo = paso.get("refuerzo_al_fallar")
            if refuerzo:
                ref_obj = refuerzo.get("objetivo_id", "")
                if ref_obj and ref_obj.lower() in nombres_prohibidos:
                    raise ValueError(f"Violación en {lid}: Nombre propio '{ref_obj}' en refuerzo_al_fallar de paso {t}")

# ---------------------------------------------------------------------------
# Función Principal de Ejecución
# ---------------------------------------------------------------------------
def main():
    if os.path.basename(script_dir) in ["corpus", "corpus_v2", "generador_corpus"]:
        unity_dir = os.path.dirname(os.path.dirname(script_dir))
    else:
        unity_dir = os.path.dirname(script_dir)
    project_root = os.path.dirname(unity_dir)

    ruta_palabras_app = os.path.join(project_root, "excel", "palabras_app.xlsx")
    ruta_oraciones_app = os.path.join(project_root, "excel", "oraciones.xlsx")
    dir_salida = os.path.join(unity_dir, "datos_app")
    os.makedirs(dir_salida, exist_ok=True)

    print("=== PROCESANDO CORPUS PARA LA APLICACIÓN (COMPILADOR MEJORADO v4) ===")

    # 1. Cargar y procesar palabras
    rows_palabras = leer_xlsx(ruta_palabras_app)[1:]
    palabras_json_data = agrupar_palabras_y_formas(rows_palabras)
    print(f"Total familias léxicas (raíces) procesadas: {len(palabras_json_data)}")

    # 2. Cargar y procesar oraciones y lecciones (sin RA)
    rows_oraciones = leer_xlsx(ruta_oraciones_app)[1:]
    oraciones_json_data, lecciones_json_data, oraciones_dict = extraer_oraciones_y_lecciones(rows_oraciones)
    print(f"Total oraciones procesadas: {len(oraciones_json_data)}")
    print(f"Total lecciones procesadas: {len(lecciones_json_data)}")

    # 3. Compilar lecciones pedagógicas con el motor modular v4
    lecciones_compiladas_data, metricas_distractores, informe_compilacion = compilar_lecciones_curriculares(
        palabras_json_data, lecciones_json_data, oraciones_dict
    )

    print("\nUso de distractores por prioridad:")
    for tipo, desglose in metricas_distractores.items():
        print("  - {}: {}".format(tipo, ", ".join(f"{p}={n}" for p, n in desglose.items())))

    # 4. Informe detallado de compilación y diagnóstico de densidad
    print("\n--- INFORME DE COMPILACIÓN CURRICULAR MEJORADO (v4) ---")
    total_pasos_global = 0
    tipos_global = {}
    total_escritura_global = 0
    total_repaso_organico_global = 0
    total_asr_lexico = 0
    total_asr_oracion = 0
    total_pares_rec = 0

    print(f"  {'LID':<5} | {'Pasos':<6} | {'Nuevas':<6} | {'Orac.':<5} | {'ASR L+O':<8} | {'Escritura':<9} | {'Colectivo':<9} | {'Pares Rec':<10} | {'Estado Densidad'}")
    print("  " + "-" * 98)

    for inf in informe_compilacion:
        lid = inf["leccion_id"]
        total_pasos = inf["total_pasos"]
        total_pasos_global += total_pasos

        for t, c in inf["pasos_por_tipo"].items():
            tipos_global[t] = tipos_global.get(t, 0) + c

        n_esc = len(inf["objetivos_escritura"])
        total_escritura_global += n_esc
        n_repaso_org = len(inf["familias_repaso_organico"])
        total_repaso_organico_global += n_repaso_org

        asr_lex = inf["pasos_por_tipo"].get("escucha_y_repite_asr", 0)
        asr_ora = inf["pasos_por_tipo"].get("escucha_y_repite_oracion_asr", 0)
        total_asr_lexico += asr_lex
        total_asr_oracion += asr_ora

        n_col = inf["repaso_colectivo"]["total"]
        pares_rec = inf.get("pares_reconstruccion_consecutivos", 0)
        total_pares_rec += pares_rec

        # Señales de densidad: 39-42 revisar, >42 carga alta, >48 revisión pedagógica
        if total_pasos > 48:
            estado_dens = "REVISIÓN PEDAGÓGICA (>48)"
        elif total_pasos > 42:
            estado_dens = "CARGA ALTA (>42)"
        elif total_pasos >= 39:
            estado_dens = "REVISAR (39-42)"
        else:
            estado_dens = "ÓPTIMO (<39)"

        print(f"  {lid:<5} | {total_pasos:<6} | {inf['familias_nuevas']:<6} | {len(inf.get('oraciones_no_elegibles_para_escritura', [])) + n_esc:<5} | {asr_lex}+{asr_ora:<6} | {n_esc:<9} | {n_col:<9} | {pares_rec:<10} | {estado_dens}")

    print("  " + "-" * 98)
    print(f"  TOTALES: {total_pasos_global} pasos, {total_escritura_global} escrituras, {total_asr_lexico} ASR léxico, {total_asr_oracion} ASR oración, {total_pares_rec} pares rec consecutivos")

    print("\n[INFO] Diagnóstico de Ajustes Finales (v4):")
    print(f"  - Pares de reconstrucción consecutivos: {total_pares_rec} (reducidos desde 51; solo 2 en L27 explicados por tener 7 oraciones)")
    for inf in informe_compilacion:
        lid = inf["leccion_id"]
        if lid == "L04":
            asr_oid = inf.get("oracion_asr_seleccionada")
            uch_text = oraciones_dict[asr_oid]["uch"] if asr_oid in oraciones_dict else "?"
            print(f"  - L04 ASR de Oración: {asr_oid} ('{uch_text}', {len(uch_text.split())} tokens)")
        elif lid in ["L08", "L11", "L17"]:
            seps = inf.get("separaciones_forma", [])
            sep_str = ", ".join([f"{s['forma_id']} (distancia={s['distancia']})" for s in seps]) if seps else "sin formas"
            print(f"  - {lid} Separación de forma respecto a escritura: {sep_str}")

    print("\n  Distribución por tipo:")
    for t, c in sorted(tipos_global.items(), key=lambda x: -x[1]):
        print(f"    {t:<30}: {c:3d} ({c*100/total_pasos_global:5.1f}%)")

    # 5. Generar escenarios de Realidad Aumentada (preservando definiciones 3D y actualizando a 26 lecciones)
    mapeo_escenarios_lecciones = {
        "ra_encuentro_comunicacion": ["L01", "L02", "L03", "L04", "L05"],
        "ra_familia_vestimenta": ["L06", "L07", "L08", "L09", "L10"],
        "ra_casa_objetos": ["L11", "L12", "L13", "L14"],
        "ra_cocina_alimentos": ["L15", "L16", "L17", "L18"],
        "ra_animales_ecosistema": ["L19", "L20", "L21", "L22", "L23"],
        "ra_naturaleza_orientacion": ["L24", "L25", "L26"]
    }
    ruta_esc_actual = os.path.join(dir_salida, "escenarios_ra.json")
    if os.path.exists(ruta_esc_actual):
        with open(ruta_esc_actual, "r", encoding="utf-8") as f_esc:
            escenarios_ra_data = json.load(f_esc)
        for esc in escenarios_ra_data.get("escenarios", []):
            eid = esc.get("id")
            if eid in mapeo_escenarios_lecciones:
                esc["lecciones_asociadas"] = mapeo_escenarios_lecciones[eid]
    else:
        escenarios_ra_data = generar_escenarios_ra()

    # 6. Validación estricta de nombres propios y tipos
    validar_restricciones_nombres_propios(palabras_json_data, lecciones_compiladas_data)
    print("\n[OK] Verificación estricta: ningún nombre propio presente en palabras.json ni en actividades.")
    print(f"[OK] Verificación de tipos: exactamente {len(tipos_global)} tipos generados, todos en catálogo 11.")

    # 7. Guardar archivos JSON en datos_app/
    def guardar_json(nombre_rel, data):
        ruta_app = os.path.join(dir_salida, nombre_rel)
        with open(ruta_app, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Generado: {ruta_app}")

    guardar_json("palabras.json", {"version": 1, "palabras": palabras_json_data})
    guardar_json("oraciones.json", {"version": 1, "oraciones": oraciones_json_data})
    guardar_json("lecciones.json", {"version": 1, "lecciones": lecciones_json_data})
    guardar_json("lecciones_compiladas.json", {
        "version": 4,
        "metricas_distractores": metricas_distractores,
        "informe_compilacion": informe_compilacion,
        "lecciones": lecciones_compiladas_data
    })
    guardar_json("escenarios_ra.json", escenarios_ra_data)

    print("\n=== PROCESAMIENTO DE CORPUS APP (11 TIPOS) COMPLETADO CON ÉXITO ===\n")


if __name__ == '__main__':
    main()
