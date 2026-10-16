"""
compilador_lecciones_v2.py
Motor de compilación curricular determinista V2 para Uchumataqu con ~40% de actividades de escritura
y predominio de morfología (escribir_forma) y sintaxis (escribir_oracion).
"""

import os
import sys
import json
import random
from collections import Counter
from typing import Optional, Tuple, List, Dict, Set

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

try:
    from generador_corpus.distractores_corpus import (
        resolver_familias_en_oracion,
        resolver_tokens_detalle_oracion,
        seleccionar_distractores_por_prioridad,
        generar_distractores_oracion,
        normalizar_texto,
        NOMBRES_PROPIOS_CONTEXTUALES,
        seleccionar_distractores_completar
    )
except ImportError:
    from distractores_corpus import (
        resolver_familias_en_oracion,
        resolver_tokens_detalle_oracion,
        seleccionar_distractores_por_prioridad,
        generar_distractores_oracion,
        normalizar_texto,
        NOMBRES_PROPIOS_CONTEXTUALES,
        seleccionar_distractores_completar
    )

CATALOGO_22 = {
    "presentacion_familia",
    "uch_a_es",
    "es_a_uch",
    "audio_a_uch",
    "audio_a_es",
    "forma_a_raiz",
    "forma_a_es",
    "es_a_forma",
    "audio_a_forma",
    "familia_completa",
    "emparejar_uch_es",
    "emparejar_audio_uch",
    "ordenar_oracion",
    "dictado_word_bank",
    "traduccion_constructiva",
    "completar_oracion",
    "audio_a_es_oracion",
    "escribir_palabra",
    "escribir_forma",
    "escribir_oracion",
    "escucha_y_repite_asr",
    "escucha_y_repite_oracion_asr"
}

RECONSTRUCCION_TIPOS = {"ordenar_oracion", "dictado_word_bank", "traduccion_constructiva"}

MECANICA_POR_TIPO = {
    "presentacion_familia":         "presentacion",
    "uch_a_es":                     "seleccion_visual",
    "es_a_uch":                     "seleccion_visual",
    "forma_a_raiz":                 "seleccion_visual",
    "forma_a_es":                   "seleccion_visual",
    "es_a_forma":                   "seleccion_visual",
    "audio_a_uch":                  "seleccion_auditiva",
    "audio_a_es":                   "seleccion_auditiva",
    "audio_a_forma":                "seleccion_auditiva",
    "emparejar_uch_es":             "emparejamiento_visual",
    "emparejar_audio_uch":          "emparejamiento_auditivo",
    "familia_completa":             "morfologia_grupo",
    "ordenar_oracion":              "reconstruccion_oracion",
    "dictado_word_bank":            "reconstruccion_oracion",
    "traduccion_constructiva":      "reconstruccion_oracion",
    "audio_a_es_oracion":           "comprension_oracion",
    "completar_oracion":            "contexto_oracion",
    "escribir_palabra":             "escritura",
    "escribir_forma":               "escritura",
    "escribir_oracion":             "escritura",
    "escucha_y_repite_asr":         "asr",
    "escucha_y_repite_oracion_asr": "asr"
}

FUENTE_ESTIMULO_POR_TIPO = {
    "presentacion_familia":         "audio",
    "uch_a_es":                     "texto_uch",
    "es_a_uch":                     "texto_es",
    "audio_a_uch":                  "audio",
    "audio_a_es":                   "audio",
    "forma_a_raiz":                 "texto_uch",
    "forma_a_es":                   "texto_uch",
    "es_a_forma":                   "texto_es",
    "audio_a_forma":                "audio",
    "familia_completa":             "texto_uch",
    "emparejar_uch_es":             "texto_uch",
    "emparejar_audio_uch":          "audio",
    "ordenar_oracion":              "texto_es",
    "dictado_word_bank":            "audio",
    "traduccion_constructiva":      "texto_es",
    "completar_oracion":            "texto_uch",
    "audio_a_es_oracion":           "audio",
    "escribir_palabra":             "texto_es",
    "escribir_forma":               "texto_es",
    "escribir_oracion":             "texto_es",
    "escucha_y_repite_asr":         "audio",
    "escucha_y_repite_oracion_asr": "audio"
}

CONSIGNAS_PALABRA = [
    ("Escribe en uchumataqu: «{es}»", "texto_es"),
    ("Escucha y escribe la palabra en uchumataqu", "audio")
]

CONSIGNAS_FORMA = [
    ("Escribe en uchumataqu la forma: «{es}»", "texto_es"),
    ("Escucha y escribe la forma en uchumataqu", "audio")
]

CONSIGNAS_ORACION = [
    ("Traduce al uchumataqu: «{es}»", "texto_es"),
    ("Escucha atentamente y escribe la oración en uchumataqu", "audio")
]

REFUERZO_MAP = {
    "escribir_palabra": ["audio_a_uch", "uch_a_es"],
    "escribir_forma": ["audio_a_forma", "es_a_forma"],
    "escribir_oracion": ["ordenar_oracion", "dictado_word_bank"]
}

MODOS_RECONSTRUCCION = ["ordenar_oracion", "dictado_word_bank", "traduccion_constructiva"]


class EstadoLeccionV2:
    """Gestiona el estado y presupuesto V2 para alcanzar un ~40% de escritura pedagógica."""

    def __init__(self, leccion_id: str, rng: random.Random, familias_nuevas: list,
                 familias_repaso: list, familias_futuras: set, oraciones_ids: list):
        self.leccion_id = leccion_id
        self.rng = rng
        self.familias_nuevas = familias_nuevas
        self.familias_repaso = familias_repaso
        self.familias_futuras = familias_futuras
        self.oraciones_ids = oraciones_ids

        self.pasos = []
        self.familias_presentadas = set()
        self.ultimo_paso_objetivo = {}
        self.pares_tipo_objetivo = set()
        self.conjuntos_colectivos = []

        n_nuevas = len(familias_nuevas)
        if n_nuevas <= 3:
            self.presupuesto_escritura_lexica = 6
        elif n_nuevas <= 6:
            self.presupuesto_escritura_lexica = 8
        elif n_nuevas <= 9:
            self.presupuesto_escritura_lexica = 10
        else:
            self.presupuesto_escritura_lexica = 12

        self.escrituras_lexicas_realizadas = 0
        self.asr_lexico_realizados = 0
        self.asr_oracion_realizados = 0
        self.colectivos_realizados = 0

        self.pares_reconstruccion_consecutivos = 0
        self.excepciones_reconstruccion = []
        self.separaciones_forma = []
        self.posiciones_asr = []
        self.objetivos_escritura = []
        self.relajaciones_separacion = []
        self.opciones_reducidas = []

    def distancia_desde_evaluacion(self, objetivo_id: str) -> int:
        if objetivo_id not in self.ultimo_paso_objetivo:
            return 999
        return len(self.pasos) - 1 - self.ultimo_paso_objetivo[objetivo_id]

    def ultima_mecanica(self) -> str:
        if not self.pasos:
            return ""
        return MECANICA_POR_TIPO.get(self.pasos[-1].get("tipo", ""), "")

    def agregar_paso(self, paso: dict, es_evaluacion: bool = True):
        tipo = paso["tipo"]
        assert tipo in CATALOGO_22, f"Tipo no permitido en catálogo 22: {tipo}"

        if tipo in RECONSTRUCCION_TIPOS:
            if self.pasos and self.pasos[-1].get("tipo") in RECONSTRUCCION_TIPOS:
                self.pares_reconstruccion_consecutivos += 1
                self.excepciones_reconstruccion.append({
                    "leccion": self.leccion_id,
                    "pos_previa": len(self.pasos) - 1,
                    "pos_actual": len(self.pasos),
                    "tipo_previo": self.pasos[-1]["tipo"],
                    "tipo_actual": tipo,
                    "oracion_id": paso.get("oracion_id")
                })

        if "fuente_estimulo" not in paso:
            paso["fuente_estimulo"] = FUENTE_ESTIMULO_POR_TIPO.get(tipo, "texto_uch")

        obj_id = paso.get("objetivo_id") or paso.get("forma_id") or paso.get("oracion_id")
        if obj_id:
            self.pares_tipo_objetivo.add((tipo, obj_id))

        if es_evaluacion and obj_id:
            self.ultimo_paso_objetivo[obj_id] = len(self.pasos)

        if "asr" in tipo:
            self.posiciones_asr.append(len(self.pasos))

        self.pasos.append(paso)


def compilar_lecciones_curriculares_v2(
    lecciones_lista: list,
    palabras_lista: list,
    oraciones_lista: list
) -> Tuple[list, dict, list]:
    """Compila las 27 lecciones con ~40% de escritura y predominio morfológico/sintáctico."""
    indice_raices = {}
    indice_formas = {}
    multi_palabras = []
    palabras_map = {p["id"]: p for p in palabras_lista}
    formas_map = {}
    oraciones_dict = {o["id"]: o for o in oraciones_lista}

    for p in palabras_lista:
        uch_norm = normalizar_texto(p["uch"])
        indice_raices[uch_norm] = p["id"]
        if " " in uch_norm:
            multi_palabras.append((uch_norm, p["id"]))

        for forma in p.get("formas", []):
            f_norm = normalizar_texto(forma["uch"])
            indice_formas[f_norm] = {
                "familia_id": p["id"],
                "forma_id": forma["id"]
            }
            formas_map[forma["id"]] = {
                **forma,
                "categoria_gramatical": p.get("categoria_gramatical", "general"),
                "familia_id": p["id"]
            }
            if " " in f_norm:
                multi_palabras.append((f_norm, p["id"]))

    multi_palabras.sort(key=lambda x: len(x[0].split()), reverse=True)

    oraciones_curriculares = {
        oid for leccion in lecciones_lista for oid in leccion["oraciones_ids"]
    }
    oraciones_reserva = set(oraciones_dict) - oraciones_curriculares
    familias_curriculares = set()
    for oid in oraciones_curriculares:
        if oid in oraciones_dict:
            familias_curriculares.update(
                resolver_familias_en_oracion(
                    oraciones_dict[oid]["uch"], indice_raices, indice_formas, multi_palabras
                )
            )

    familias_reserva = set(palabras_map) - familias_curriculares
    familias_presentadas_global = set()
    leccion_origen_familia = {}
    formas_por_familia = {
        p["id"]: {f["id"] for f in p.get("formas", [])} for p in palabras_lista
    }

    metricas = {"distractores_fallidos": 0, "distractores_usados": 0}
    uso_oraciones_reserva = Counter()

    def familias_recientes(n_lecciones=4):
        recientes = set()
        for lec_prev in lecciones_lista[max(0, lec_idx - n_lecciones):lec_idx]:
            recientes.update(lec_prev.get("familias_nuevas", []))
        return recientes & familias_presentadas_global

    def distractores_raiz(objetivo_id, familias_leccion, familias_futuras, rng):
        recientes = familias_recientes()
        antiguas_y_reserva = (familias_presentadas_global - recientes) | familias_reserva
        return seleccionar_distractores_por_prioridad(
            objetivo_id, palabras_map,
            [familias_leccion, recientes, antiguas_y_reserva, familias_futuras],
            rng, metricas, "palabras"
        )

    def distractores_forma(objetivo_id, familias_leccion, familias_futuras, rng):
        recientes = familias_recientes()
        conocidas_recientes = set().union(*(formas_por_familia[f] for f in recientes)) if recientes else set()
        antiguas_fams = (familias_presentadas_global - recientes) | familias_reserva
        antiguas = set().union(*(formas_por_familia[f] for f in antiguas_fams)) if antiguas_fams else set()
        actuales = set().union(*(formas_por_familia[f] for f in familias_leccion)) if familias_leccion else set()
        futuras = set().union(*(formas_por_familia[f] for f in familias_futuras)) if familias_futuras else set()
        return seleccionar_distractores_por_prioridad(
            objetivo_id, formas_map,
            [conocidas_recientes, antiguas, actuales, futuras],
            rng, metricas, "formas"
        )

    MICRO_MODALIDADES = ["uch_a_es", "audio_a_uch", "es_a_uch", "audio_a_es"]
    MODOS_FORMAS = ["forma_a_raiz", "forma_a_es", "es_a_forma", "audio_a_forma"]
    idx_micro_global = 0
    idx_forma_global = 0

    lecciones_compiladas = []
    informe_compilacion = []

    for lec_idx, lec in enumerate(lecciones_lista):
        lid = lec["id"]
        semilla = sum(ord(c) * (i + 1) for i, c in enumerate(lid))
        rng = random.Random(semilla)

        familias_en_leccion = set()
        for oid in lec["oraciones_ids"]:
            if oid in oraciones_dict:
                familias_en_leccion.update(resolver_familias_en_oracion(
                    oraciones_dict[oid]["uch"], indice_raices, indice_formas, multi_palabras
                ))

        familias_nuevas = sorted(list(familias_en_leccion - familias_presentadas_global))
        familias_repaso = sorted(list(familias_en_leccion & familias_presentadas_global))
        familias_futuras = familias_curriculares - familias_presentadas_global - set(familias_en_leccion)

        estado = EstadoLeccionV2(
            leccion_id=lid,
            rng=rng,
            familias_nuevas=familias_nuevas,
            familias_repaso=familias_repaso,
            familias_futuras=familias_futuras,
            oraciones_ids=lec["oraciones_ids"]
        )

        n_nuevas = len(familias_nuevas)
        punto_asr1 = max(1, round(n_nuevas * 0.35)) if n_nuevas > 0 else 0

        # ETAPA 1: Presentación de Familias y Microactividades
        familias_evaluadas_en_orden = []
        for fn_idx, fid in enumerate(familias_nuevas):
            if fid not in palabras_map:
                continue
            p_data = palabras_map[fid]
            estado.familias_presentadas.add(fid)
            tiene_formas = "formas" in p_data and len(p_data["formas"]) > 0

            estado.agregar_paso({
                "tipo": "presentacion_familia",
                "objetivo_id": fid,
                "tiene_formas": tiene_formas,
                "seccion": "palabras_nuevas"
            }, es_evaluacion=False)

            usar_forma_en_micro = tiene_formas and (fn_idx % 3 == 1)
            if usar_forma_en_micro:
                forma_sel = p_data["formas"][0]
                mod_forma = MODOS_FORMAS[idx_forma_global % len(MODOS_FORMAS)]
                idx_forma_global += 1
                opciones_f = distractores_forma(forma_sel["id"], familias_en_leccion, familias_futuras, rng)
                estado.agregar_paso({
                    "tipo": mod_forma,
                    "forma_id": forma_sel["id"],
                    "raiz_id": fid,
                    "opciones_ids": opciones_f,
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)
            else:
                mod_micro = MICRO_MODALIDADES[idx_micro_global % len(MICRO_MODALIDADES)]
                idx_micro_global += 1
                opciones_micro = distractores_raiz(fid, familias_en_leccion, familias_futuras, rng)
                estado.agregar_paso({
                    "tipo": mod_micro,
                    "objetivo_id": fid,
                    "opciones_ids": opciones_micro,
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)

            familias_evaluadas_en_orden.append(fid)

            # ASR Léxico 1
            if estado.asr_lexico_realizados == 0 and (fn_idx + 1) == punto_asr1:
                cands_asr = [f for f in familias_evaluadas_en_orden if estado.distancia_desde_evaluacion(f) >= 2]
                if cands_asr and estado.ultima_mecanica() != "asr":
                    target_asr = cands_asr[0]
                    estado.agregar_paso({
                        "tipo": "escucha_y_repite_asr",
                        "objetivo_id": target_asr,
                        "opcional": True,
                        "seccion": "practica_oral"
                    }, es_evaluacion=True)
                    estado.asr_lexico_realizados += 1

            # Intercalado de escritura léxica v2
            def distancia_minima_escritura(fid: str) -> int:
                p_info = palabras_map.get(fid, {})
                dist_raiz = estado.distancia_desde_evaluacion(fid)
                if "formas" in p_info and p_info["formas"]:
                    dists = [estado.distancia_desde_evaluacion(frm["id"]) for frm in p_info["formas"]]
                    return min([dist_raiz] + dists)
                return dist_raiz

            def buscar_candidato_escritura():
                # Prioridad 1: Formas de familias evaluadas en esta lección
                for f in familias_evaluadas_en_orden:
                    p_info = palabras_map.get(f, {})
                    for frm in p_info.get("formas", []):
                        if ("escribir_forma", frm["id"]) not in estado.pares_tipo_objetivo and distancia_minima_escritura(f) >= 2:
                            return ("escribir_forma", f, frm)
                # Prioridad 2: Formas de repaso morfológico de lecciones previas
                for f in (familias_repaso + sorted(familias_recientes())):
                    p_info = palabras_map.get(f, {})
                    for frm in p_info.get("formas", []):
                        if ("escribir_forma", frm["id"]) not in estado.pares_tipo_objetivo:
                            return ("escribir_forma", f, frm)
                # Prioridad 3: Raíces nuevas (máximo 2 por lección para que predominen formas y oraciones)
                palabras_escritas_en_lec = sum(1 for p in estado.pasos if p.get("tipo") == "escribir_palabra")
                if palabras_escritas_en_lec < 2:
                    for f in familias_evaluadas_en_orden:
                        if ("escribir_palabra", f) not in estado.pares_tipo_objetivo and distancia_minima_escritura(f) >= 2:
                            return ("escribir_palabra", f, None)
                # Prioridad 4: Más formas de cualquier familia previa presentada
                for f in sorted(familias_presentadas_global):
                    p_info = palabras_map.get(f, {})
                    for frm in p_info.get("formas", []):
                        if ("escribir_forma", frm["id"]) not in estado.pares_tipo_objetivo:
                            return ("escribir_forma", f, frm)
                return None

            if estado.escrituras_lexicas_realizadas < estado.presupuesto_escritura_lexica:
                cand = buscar_candidato_escritura()
                if cand and estado.ultima_mecanica() != "escritura":
                    tipo_cand, f_cand, frm_cand = cand
                    if tipo_cand == "escribir_forma":
                        consigna, fuente_esc = CONSIGNAS_FORMA[0]
                        consigna = consigna.format(es=frm_cand["es"])
                        ref_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_lexicas_realizadas % 2]
                        estado.agregar_paso({
                            "tipo": "escribir_forma",
                            "forma_id": frm_cand["id"],
                            "raiz_id": f_cand,
                            "respuesta_esperada_uch": frm_cand["uch"],
                            "consigna": consigna,
                            "fuente_estimulo": fuente_esc,
                            "refuerzo_al_fallar": {"tipo": ref_mod, "objetivo_id": frm_cand["id"]},
                            "seccion": "palabras_nuevas"
                        }, es_evaluacion=True)
                        estado.objetivos_escritura.append({"tipo": "escribir_forma", "objetivo": frm_cand["id"]})
                    else:
                        p_esc_data = palabras_map[f_cand]
                        consigna, fuente_esc = CONSIGNAS_PALABRA[estado.escrituras_lexicas_realizadas % len(CONSIGNAS_PALABRA)]
                        consigna = consigna.format(es=p_esc_data["es"])
                        ref_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_lexicas_realizadas % 2]
                        estado.agregar_paso({
                            "tipo": "escribir_palabra",
                            "objetivo_id": f_cand,
                            "respuesta_esperada_uch": p_esc_data["uch"],
                            "consigna": consigna,
                            "fuente_estimulo": fuente_esc,
                            "refuerzo_al_fallar": {"tipo": ref_mod, "objetivo_id": f_cand},
                            "seccion": "palabras_nuevas"
                        }, es_evaluacion=True)
                        estado.objetivos_escritura.append({"tipo": "escribir_palabra", "objetivo": f_cand})
                    estado.escrituras_lexicas_realizadas += 1

        # Completar presupuesto léxico intercalando microactividad si es necesario
        while estado.escrituras_lexicas_realizadas < estado.presupuesto_escritura_lexica:
            cand = buscar_candidato_escritura()
            if not cand:
                break
            if estado.ultima_mecanica() == "escritura":
                f_alt = familias_evaluadas_en_orden[0] if familias_evaluadas_en_orden else (familias_repaso[0] if familias_repaso else None)
                if f_alt:
                    estado.agregar_paso({
                        "tipo": "uch_a_es",
                        "objetivo_id": f_alt,
                        "opciones_ids": distractores_raiz(f_alt, familias_en_leccion, familias_futuras, rng),
                        "seccion": "palabras_nuevas"
                    }, es_evaluacion=True)
            tipo_cand, f_cand, frm_cand = cand
            if tipo_cand == "escribir_forma":
                consigna, fuente_esc = CONSIGNAS_FORMA[0]
                consigna = consigna.format(es=frm_cand["es"])
                ref_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_lexicas_realizadas % 2]
                estado.agregar_paso({
                    "tipo": "escribir_forma",
                    "forma_id": frm_cand["id"],
                    "raiz_id": f_cand,
                    "respuesta_esperada_uch": frm_cand["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {"tipo": ref_mod, "objetivo_id": frm_cand["id"]},
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)
                estado.objetivos_escritura.append({"tipo": "escribir_forma", "objetivo": frm_cand["id"]})
            else:
                p_esc_data = palabras_map[f_cand]
                consigna, fuente_esc = CONSIGNAS_PALABRA[estado.escrituras_lexicas_realizadas % len(CONSIGNAS_PALABRA)]
                consigna = consigna.format(es=p_esc_data["es"])
                ref_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_lexicas_realizadas % 2]
                estado.agregar_paso({
                    "tipo": "escribir_palabra",
                    "objetivo_id": f_cand,
                    "respuesta_esperada_uch": p_esc_data["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {"tipo": ref_mod, "objetivo_id": f_cand},
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)
                estado.objetivos_escritura.append({"tipo": "escribir_palabra", "objetivo": f_cand})
            estado.escrituras_lexicas_realizadas += 1

        # ETAPA 2: Repaso Colectivo (Emparejamiento)
        fams_disp_col = [f for f in familias_evaluadas_en_orden if estado.distancia_desde_evaluacion(f) >= 2]
        if len(fams_disp_col) >= 3 and estado.colectivos_realizados == 0:
            grupo_col = fams_disp_col[:3]
            estado.agregar_paso({
                "tipo": "emparejar_uch_es",
                "items_ids": grupo_col,
                "seccion": "repaso_colectivo"
            }, es_evaluacion=True)
            estado.colectivos_realizados += 1

        # ETAPA 3: Oraciones y Sintaxis
        oraciones_en_leccion = [oid for oid in lec["oraciones_ids"] if oid in oraciones_dict]
        todas_presentadas = familias_presentadas_global | set(familias_nuevas)

        oraciones_escritura_elegibles = []
        for oid in oraciones_en_leccion:
            o_data = oraciones_dict[oid]
            n_tokens = len(o_data["uch"].split())
            if 2 <= n_tokens <= 6:
                try:
                    fams = resolver_familias_en_oracion(o_data["uch"], indice_raices, indice_formas, multi_palabras)
                    if fams.issubset(todas_presentadas):
                        oraciones_escritura_elegibles.append(oid)
                except ValueError:
                    pass

        cuota_escritura_oracion = len(oraciones_escritura_elegibles)
        oraciones_escritas_lec = oraciones_escritura_elegibles[:cuota_escritura_oracion]

        pasos_oraciones = []
        # Reconstrucción guiada de scaffolding (1 o 2 pasos)
        for o_idx, oid in enumerate(oraciones_en_leccion[:2]):
            pasos_oraciones.append({
                "tipo": MODOS_RECONSTRUCCION[o_idx % len(MODOS_RECONSTRUCCION)],
                "oracion_id": oid,
                "seccion": "practica_oracion"
            })

        # ASR de oración
        if oraciones_en_leccion:
            pasos_oraciones.append({
                "tipo": "escucha_y_repite_oracion_asr",
                "oracion_id": oraciones_en_leccion[-1],
                "opcional": True,
                "seccion": "practica_oral"
            })

        # Escritura de oraciones (sintaxis y PLN)
        for o_esc_idx, oid_esc in enumerate(oraciones_escritas_lec):
            o_data = oraciones_dict[oid_esc]
            consigna, fuente_esc = CONSIGNAS_ORACION[o_esc_idx % len(CONSIGNAS_ORACION)]
            consigna = consigna.format(es=o_data["es"])
            ref_mod = REFUERZO_MAP["escribir_oracion"][o_esc_idx % 2]
            pasos_oraciones.append({
                "tipo": "escribir_oracion",
                "oracion_id": oid_esc,
                "respuesta_esperada_uch": o_data["uch"],
                "consigna": consigna,
                "fuente_estimulo": fuente_esc,
                "refuerzo_al_fallar": {"tipo": ref_mod, "oracion_id": oid_esc},
                "seccion": "practica_oracion"
            })

        for p_ora in pasos_oraciones:
            estado.agregar_paso(p_ora, es_evaluacion=True)

        lecciones_compiladas.append({
            "id": lid,
            "titulo": lec["titulo"],
            "orden": lec["orden"],
            "familias_nuevas": familias_nuevas,
            "familias_repaso": familias_repaso,
            "familias_repaso_organico": [],
            "oraciones_ids": lec["oraciones_ids"],
            "pasos": estado.pasos
        })

        familias_presentadas_global.update(familias_nuevas)
        for fid in familias_nuevas:
            leccion_origen_familia[fid] = lid

        pasos_por_tipo = Counter(p["tipo"] for p in estado.pasos)
        informe_compilacion.append({
            "leccion_id": lid,
            "familias_nuevas": len(familias_nuevas),
            "total_pasos": len(estado.pasos),
            "pasos_por_tipo": dict(pasos_por_tipo),
            "objetivos_escritura": estado.objetivos_escritura
        })

    return lecciones_compiladas, metricas, informe_compilacion


def compilar_y_guardar_v2(dir_app: str = None) -> str:
    """Función principal para compilar lecciones V2 y guardarlas en datos_app/lecciones_compiladas_v2.json."""
    if dir_app is None:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        ws_root = os.path.abspath(os.path.join(curr_dir, "..", "..", ".."))
        dir_app = os.path.join(ws_root, "UNITY", "datos_app")
        if not os.path.exists(dir_app):
            dir_app = os.path.abspath(os.path.join(curr_dir, "..", "..", "datos_app"))

    ruta_palabras = os.path.join(dir_app, "palabras.json")
    ruta_oraciones = os.path.join(dir_app, "oraciones.json")
    ruta_lecciones = os.path.join(dir_app, "lecciones.json")
    ruta_salida_v2 = os.path.join(dir_app, "lecciones_compiladas_v2.json")

    with open(ruta_palabras, "r", encoding="utf-8") as f:
        palabras_lista = json.load(f)["palabras"]
    with open(ruta_oraciones, "r", encoding="utf-8") as f:
        oraciones_lista = json.load(f)["oraciones"]
    with open(ruta_lecciones, "r", encoding="utf-8") as f:
        lecciones_lista = json.load(f)["lecciones"]

    lecciones_comp, metricas, informe = compilar_lecciones_curriculares_v2(
        lecciones_lista, palabras_lista, oraciones_lista
    )

    salida_data = {
        "version": 2,
        "descripcion": "Lecciones compiladas V2: ~40% escritura con predominio de escribir_forma y escribir_oracion",
        "metricas_distractores": metricas,
        "informe_compilacion": informe,
        "lecciones": lecciones_comp
    }

    with open(ruta_salida_v2, "w", encoding="utf-8") as f:
        json.dump(salida_data, f, ensure_ascii=False, indent=2)

    total_pasos = sum(len(l["pasos"]) for l in lecciones_comp)
    conteo_tipos = Counter(p["tipo"] for l in lecciones_comp for p in l["pasos"])
    n_forma = conteo_tipos.get("escribir_forma", 0)
    n_ora = conteo_tipos.get("escribir_oracion", 0)
    n_pal = conteo_tipos.get("escribir_palabra", 0)
    n_esc = n_forma + n_ora + n_pal

    print(f"[OK] Generado exitosamente: {ruta_salida_v2}")
    print(f"     Total lecciones : {len(lecciones_comp)}")
    print(f"     Total pasos     : {total_pasos}")
    print(f"     Total escritura : {n_esc} ({n_esc/total_pasos*100:5.2f}% del total)")
    print(f"       - escribir_forma  : {n_forma:3d} ({n_forma/n_esc*100:5.1f}% de la escritura)")
    print(f"       - escribir_oracion: {n_ora:3d} ({n_ora/n_esc*100:5.1f}% de la escritura)")
    print(f"       - escribir_palabra: {n_pal:3d} ({n_pal/n_esc*100:5.1f}% de la escritura)")
    print(f"     Predominio forma + oración: {n_forma + n_ora} de {n_esc} ({(n_forma + n_ora)/n_esc*100:5.1f}%)")

    return ruta_salida_v2


if __name__ == "__main__":
    compilar_y_guardar_v2()
