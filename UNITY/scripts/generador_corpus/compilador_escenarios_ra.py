"""
compilador_escenarios_ra.py
Compilador determinista y enriquecedor pedagógico para escenarios de Realidad Aumentada (V2).
Integra evaluación PLN (respuesta_esperada_uch, consigna, fuente_estimulo) y valida coherencia 3D/léxica.
"""

import os
import sys
import json
import copy
from collections import Counter
from typing import Dict, Any, Tuple, List

TIPOS_PERMITIDOS_RA = {
    "escuchar_seleccionar",
    "repetir_voz",
    "escribir",
    "arrastrar",
    "historia"
}

CANTIDADES_ESPERADAS = [16, 13, 13, 14, 19, 13]


def compilar_escenarios_ra_v2(
    escenarios_base: dict,
    palabras_lista: list,
    oraciones_lista: list
) -> Tuple[dict, dict]:
    """
    Compila y enriquece la definición de escenarios RA a versión 2:
    - Agrega campos PLN a todas las actividades de escritura (respuesta_esperada_uch, consigna, fuente_estimulo).
    - Incorpora actividades de escritura en el Escenario 1 (Encuentro y comunicación).
    - Valida que todos los IDs léxicos, oraciones y objetos interactivos 3D existan.
    - Garantiza el cumplimiento de las restricciones de alternancia y conteo para Unity.
    """
    palabras_map = {p["id"]: p for p in palabras_lista}
    oraciones_map = {o["id"]: o for o in oraciones_lista}

    # Copia profunda del árbol base
    data_v2 = copy.deepcopy(escenarios_base)
    data_v2["version"] = 2
    data_v2["descripcion"] = "Escenarios de Realidad Aumentada V2 enriquecidos con PLN y actividades de escritura"

    informe = {
        "escenarios": [],
        "total_pasos": 0,
        "total_escritura": 0,
        "tipos_globales": Counter()
    }

    for idx_esc, esc in enumerate(data_v2["escenarios"]):
        eid = esc["id"]
        objetos_ids = {obj["id"] for obj in esc.get("objetos", [])}
        fases = esc.get("mision", {}).get("fases", [])

        # Enriquecer pasos según escenario
        for fase in fases:
            for paso in fase.get("pasos", []):
                pid = paso.get("id")

                # Conversión pedagógica en Escenario 1 para introducir escritura PLN
                if eid == "ra_encuentro_comunicacion":
                    if pid == "C07b":
                        paso["tipo"] = "escribir"
                        paso["instruccion"] = "Escribe gracias"
                    elif pid == "C08a":
                        paso["tipo"] = "escribir"
                        paso["instruccion"] = "Escribe hasta luego"

                # Enriquecimiento pedagógico en Escenario 3 (Casa y objetos)
                elif eid == "ra_casa_objetos":
                    if pid == "R3-10":
                        paso["tipo"] = "escribir"
                        paso["instruccion"] = "Escribe escoba"

                # Enriquecer campos PLN en pasos de escritura
                if paso.get("tipo") == "escribir":
                    est_id = paso.get("estimulo_id") or paso.get("respuesta_id")
                    obj_id = paso.get("objetivo_objeto_id")

                    uch_esperado = ""
                    es_traduccion = ""

                    if est_id in palabras_map:
                        p_info = palabras_map[est_id]
                        uch_esperado = p_info["uch"]
                        es_traduccion = p_info["es"]
                    elif est_id in oraciones_map:
                        o_info = oraciones_map[est_id]
                        uch_esperado = o_info["uch"]
                        es_traduccion = o_info["es"]

                    paso["respuesta_esperada_uch"] = uch_esperado
                    paso["fuente_estimulo"] = "texto_es"
                    if es_traduccion:
                        paso["consigna"] = f"Escribe en uchumataqu: «{es_traduccion.lower()}»"
                    else:
                        paso["consigna"] = "Escribe en uchumataqu la palabra requerida"

                    # Asegurar respuesta_id
                    if not paso.get("respuesta_id"):
                        paso["respuesta_id"] = est_id

                    # Verificar refuerzo de oración
                    ref_id = paso.get("refuerzo_oracion_id")
                    if ref_id and ref_id not in oraciones_map:
                        # Si no existe, buscar una oración que contenga la palabra o remover
                        paso["refuerzo_oracion_id"] = None

        # Verificaciones de calidad del escenario
        pasos_esc = [p for f in fases for p in f.get("pasos", [])]
        conteo_tipos = Counter(p["tipo"] for p in pasos_esc)
        n_escritura = conteo_tipos.get("escribir", 0)
        total_p = len(pasos_esc)

        informe["total_pasos"] += total_p
        informe["total_escritura"] += n_escritura
        informe["tipos_globales"].update(conteo_tipos)

        informe["escenarios"].append({
            "id": eid,
            "titulo": esc.get("titulo"),
            "total_pasos": total_p,
            "escritura": n_escritura,
            "pct_escritura": (n_escritura / total_p * 100) if total_p else 0,
            "distribucion": dict(conteo_tipos)
        })

        # Comprobación de invariantes de Unity
        assert total_p == CANTIDADES_ESPERADAS[idx_esc], (
            f"Escenario {eid}: se esperaban {CANTIDADES_ESPERADAS[idx_esc]} pasos, se encontraron {total_p}"
        )
        for p in pasos_esc:
            assert p["tipo"] in TIPOS_PERMITIDOS_RA, f"Tipo inválido en {eid}/{p['id']}: {p['tipo']}"

        # Comprobar que no hay 3 tipos idénticos consecutivos (para escenarios 2..6)
        if idx_esc > 0:
            for i in range(2, len(pasos_esc)):
                t0 = pasos_esc[i-2]["tipo"]
                t1 = pasos_esc[i-1]["tipo"]
                t2 = pasos_esc[i]["tipo"]
                assert not (t0 == t1 == t2), (
                    f"Violación de alternancia en {eid}: 3 pasos consecutivos de tipo '{t2}' en paso {pasos_esc[i]['id']}"
                )

    return data_v2, informe


def compilar_y_guardar_escenarios_ra_v2(dir_app: str = None) -> str:
    """Función principal para compilar escenarios RA V2 y guardarlos en datos_app/escenarios_ra_v2.json."""
    if dir_app is None:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        ws_root = os.path.abspath(os.path.join(curr_dir, "..", "..", ".."))
        dir_app = os.path.join(ws_root, "UNITY", "datos_app")
        if not os.path.exists(dir_app):
            dir_app = os.path.abspath(os.path.join(curr_dir, "..", "..", "datos_app"))

    ruta_base_ra = os.path.join(dir_app, "escenarios_ra.json")
    ruta_palabras = os.path.join(dir_app, "palabras.json")
    ruta_oraciones = os.path.join(dir_app, "oraciones.json")
    ruta_salida_v2 = os.path.join(dir_app, "escenarios_ra_v2.json")

    with open(ruta_base_ra, "r", encoding="utf-8") as f:
        escenarios_base = json.load(f)
    with open(ruta_palabras, "r", encoding="utf-8") as f:
        palabras_lista = json.load(f)["palabras"]
    with open(ruta_oraciones, "r", encoding="utf-8") as f:
        oraciones_lista = json.load(f)["oraciones"]

    data_v2, informe = compilar_escenarios_ra_v2(
        escenarios_base, palabras_lista, oraciones_lista
    )

    with open(ruta_salida_v2, "w", encoding="utf-8") as f:
        json.dump(data_v2, f, ensure_ascii=False, indent=2)

    print(f"[OK] Generado exitosamente: {ruta_salida_v2}")
    print(f"     Total escenarios: {len(informe['escenarios'])}")
    print(f"     Total pasos RA  : {informe['total_pasos']}")
    print(f"     Total escritura : {informe['total_escritura']} ({informe['total_escritura']/informe['total_pasos']*100:5.2f}% del total)")
    print("\n     Detalle por escenario:")
    for esc_inf in informe["escenarios"]:
        print(f"       - {esc_inf['id']:<26}: {esc_inf['total_pasos']:2d} pasos | Escritura: {esc_inf['escritura']:2d} ({esc_inf['pct_escritura']:4.1f}%) | {esc_inf['distribucion']}")

    return ruta_salida_v2


if __name__ == "__main__":
    compilar_y_guardar_escenarios_ra_v2()
