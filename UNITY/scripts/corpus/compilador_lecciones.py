"""
compilador_lecciones.py (Versión 11 Tipos - Refactorización Curricular Uchumataqu)
Compilador curricular determinista basado estrictamente en INSTRUCCIONES_AGENTE_RECOMPILACION_LECCIONES_UCHUMATAQU.md:
  - Exactamente 11 tipos permitidos (1 presentación + 10 actividades).
  - Sustitución de tipos redundantes por escritura libre y dictado por teclado.
  - Sin duplicación de objetivos escritos ni de oraciones por modalidad en una misma lección.
  - Cobertura del 100% de las 27 lecciones (L01 a L27) y 120 oraciones curriculares.
  - Menos de 804 pasos globales (reducción de redundancia sin inflar la lección).
  - 4 a 6 actividades de escritura libre por lección cuando sea viable.
  - Salida 100% reproducible y determinista.
"""

import os
import sys
import random
import hashlib
import re
from typing import Optional, List, Dict, Set, Tuple

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

try:
    from distractores_corpus import (
        resolver_familias_en_oracion,
        resolver_tokens_detalle_oracion,
        seleccionar_distractores_por_prioridad,
        generar_distractores_oracion,
        son_traducciones_compatibles,
        normalizar_texto,
        NOMBRES_PROPIOS_CONTEXTUALES
    )
except ImportError:
    from corpus.distractores_corpus import (
        resolver_familias_en_oracion,
        resolver_tokens_detalle_oracion,
        seleccionar_distractores_por_prioridad,
        generar_distractores_oracion,
        son_traducciones_compatibles,
        normalizar_texto,
        NOMBRES_PROPIOS_CONTEXTUALES
    )

# ---------------------------------------------------------------------------
# Contrato cerrado: exactamente 11 tipos permitidos
# ---------------------------------------------------------------------------
CATALOGO_11 = {
    "presentacion_familia",
    "uch_a_es",
    "audio_a_uch",
    "audio_a_forma",
    "emparejar_uch_es",
    "escribir_palabra",
    "escribir_forma",
    "escribir_oracion",
    "ordenar_oracion",
    "escucha_y_repite_asr",
    "escucha_y_repite_oracion_asr"
}

# Tipos formalmente retirados (prohibidos en lecciones y en refuerzos)
TIPOS_RETIRADOS = {
    "es_a_uch",
    "audio_a_es",
    "audio_a_es_oracion",
    "forma_a_es",
    "es_a_forma",
    "forma_a_raiz",
    "familia_completa",
    "emparejar_audio_uch",
    "traduccion_constructiva",
    "dictado_word_bank",
    "completar_oracion",
    "memoria_uch_es"
}

# Clasificación de mecánicas para evitar contigüidad monótona
MECANICA_POR_TIPO = {
    "presentacion_familia":         "presentacion",
    "uch_a_es":                     "seleccion_visual",
    "audio_a_uch":                  "seleccion_auditiva",
    "audio_a_forma":                "seleccion_auditiva",
    "emparejar_uch_es":             "emparejamiento_visual",
    "ordenar_oracion":             "reconstruccion_oracion",
    "escribir_palabra":            "escritura",
    "escribir_forma":              "escritura",
    "escribir_oracion":            "escritura",
    "escucha_y_repite_asr":        "asr",
    "escucha_y_repite_oracion_asr": "asr"
}

FUENTE_ESTIMULO_POR_TIPO = {
    "presentacion_familia":         "audio",
    "uch_a_es":                     "texto_uch",
    "audio_a_uch":                  "audio",
    "audio_a_forma":                "audio",
    "emparejar_uch_es":             "texto_uch",
    "ordenar_oracion":             "texto_es",
    "escribir_palabra":            "texto_es",
    "escribir_forma":              "texto_es",
    "escribir_oracion":            "texto_es",
    "escucha_y_repite_asr":        "audio",
    "escucha_y_repite_oracion_asr": "audio"
}

CONSIGNAS_PALABRA = [
    ("Escribe en uchumataqu: «{es}»", "texto_es"),
    ("Escucha y escribe la palabra en uchumataqu", "audio")
]

CONSIGNAS_FORMA = [
    ("Escribe en uchumataqu la forma: «{es}»", "texto_es")
]

CONSIGNAS_ORACION_TRADUCCION = "Traduce al uchumataqu: «{es}»"
CONSIGNAS_ORACION_DICTADO = "Escucha y escribe la oración en uchumataqu"

# Refuerzos estrictamente dentro de CATALOGO_11
REFUERZO_MAP = {
    "escribir_palabra": ["audio_a_uch", "uch_a_es"],
    "escribir_forma": ["audio_a_forma"],
    "escribir_oracion": ["ordenar_oracion"]
}

MAPA_CONSIGNAS_LIMPIAS = {
    "Es/esta grande": "Es grande",
    "Es/está grande": "Es grande",
    "Es/está muy grande": "Es muy grande",
    "Es/está muy bonito": "Es muy bonito",
    "Está sucio/a": "Está sucio",
    "Bueno/a o Bien": "Bueno",
    "Es/está muy bueno/a": "Es muy bueno",
    "Es/está nuevo": "Es nuevo",
    "Está contento/a": "Está contento",
    "Su (de él/ella)": "Su",
    "Está enfermo/a": "Está enfermo",
    "Es/está azul": "Es azul",
    "Es/está viejo": "Es viejo",
    "Es/está curandero": "Es curandero",
}

def limpiar_texto_consigna(texto: str) -> str:
    """Retorna una versión natural y sin barras '/' para la consigna en español."""
    if not texto:
        return ""
    t = texto.strip()
    if t in MAPA_CONSIGNAS_LIMPIAS:
        return MAPA_CONSIGNAS_LIMPIAS[t]
    if "/" in t:
        t = re.sub(r"\bEs/está\b", "Es", t, flags=re.IGNORECASE)
        t = re.sub(r"\bEs/esta\b", "Es", t, flags=re.IGNORECASE)
        t = re.sub(r"o/a\b", "o", t)
        t = re.sub(r"/a\b", "", t)
        if "/" in t:
            t = t.split("/")[0].strip()
    return t

def obtener_semilla_estable(leccion_id: str, proposito: str, revision: str = "v4") -> int:
    """Genera una semilla determinista estable e independiente de la plataforma."""
    clave = f"{leccion_id}_{revision}_{proposito}".encode("utf-8")
    return int(hashlib.sha256(clave).hexdigest()[:16], 16)

def items_validos_emparejamiento(candidatos: list, palabras_map: dict, max_items: int = 5) -> list:
    """Selecciona de forma determinista entre 2 y 5 IDs de raíces únicas con significados distinguibles."""
    seleccion = []
    for cid in candidatos:
        if cid not in palabras_map:
            continue
        if cid in NOMBRES_PROPIOS_CONTEXTUALES or cid.lower() in NOMBRES_PROPIOS_CONTEXTUALES:
            continue
        c_es = palabras_map[cid]["es"]
        incompatible = False
        for sid in seleccion:
            s_es = palabras_map[sid]["es"]
            if son_traducciones_compatibles(c_es, s_es):
                incompatible = True
                break
        if not incompatible:
            seleccion.append(cid)
            if len(seleccion) == max_items:
                break
    return seleccion


class EstadoLeccion:
    """Gestiona el estado local de compilación para una lección individual (11 tipos)."""

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

        # Registro estricto contra duplicación de respuestas escritas libres
        self.escrituras_usadas_ids = set()
        self.escrituras_usadas_uch_norm = set()

        # Metas de escritura de palabras para balancear 4-6 escrituras por lección
        n_nuevas = len(familias_nuevas)
        if n_nuevas <= 4:
            self.presupuesto_escritura_palabras = 2
        elif n_nuevas <= 8:
            self.presupuesto_escritura_palabras = 2
        else:
            self.presupuesto_escritura_palabras = 3

        # Presupuesto de emparejamiento: exactamente 2 por lección según contrato curricular v2
        self.presupuesto_emparejar = 2

        self.meta_asr_lexico = 2 if n_nuevas >= 8 else 1
        self.meta_asr_oracion = 1 if len(oraciones_ids) > 0 else 0

        self.escrituras_palabras_realizadas = 0
        self.escrituras_formas_realizadas = 0
        self.escrituras_oraciones_realizadas = 0
        self.asr_lexico_realizados = 0
        self.asr_oracion_realizados = 0
        self.emparejar_realizados = 0
        self.audio_forma_realizados = 0

        # Diagnóstico y métricas
        self.posiciones_asr = []
        self.objetivos_escritura = []
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
        assert tipo in CATALOGO_11, f"Tipo prohibido o no permitido: {tipo}"

        # Validar refuerzo si existe
        if "refuerzo_al_fallar" in paso and paso["refuerzo_al_fallar"]:
            r_tipo = paso["refuerzo_al_fallar"].get("tipo")
            assert r_tipo in CATALOGO_11, f"Tipo de refuerzo no permitido en catálogo 11: {r_tipo}"

        # Asignar fuente_estimulo si falta
        if "fuente_estimulo" not in paso:
            paso["fuente_estimulo"] = FUENTE_ESTIMULO_POR_TIPO.get(tipo, "texto_uch")

        obj_id = paso.get("objetivo_id") or paso.get("forma_id") or paso.get("oracion_id")
        if obj_id:
            self.pares_tipo_objetivo.add((tipo, obj_id))

        # Control estricto de no repetición de objetivos escritos libres
        if tipo in {"escribir_palabra", "escribir_forma", "escribir_oracion"}:
            resp_uch = paso.get("respuesta_esperada_uch", "")
            norm_uch = normalizar_texto(resp_uch)
            assert obj_id not in self.escrituras_usadas_ids, (
                f"Violación en {self.leccion_id}: ID '{obj_id}' duplicado en escritura libre"
            )
            assert norm_uch not in self.escrituras_usadas_uch_norm, (
                f"Violación en {self.leccion_id}: Respuesta superficial '{norm_uch}' duplicada en escritura libre"
            )
            self.escrituras_usadas_ids.add(obj_id)
            self.escrituras_usadas_uch_norm.add(norm_uch)
            self.objetivos_escritura.append({
                "tipo": tipo,
                "objetivo": obj_id,
                "respuesta": resp_uch,
                "fuente_estimulo": paso.get("fuente_estimulo")
            })

        # Monitorear opciones reducidas (< 4 alternativas)
        if "opciones_ids" in paso and len(paso["opciones_ids"]) < 4:
            self.opciones_reducidas.append({
                "paso_idx": len(self.pasos), "tipo": tipo, "opciones": len(paso["opciones_ids"])
            })

        self.pasos.append(paso)
        if es_evaluacion and obj_id:
            self.ultimo_paso_objetivo[obj_id] = len(self.pasos) - 1


def compilar_lecciones_curriculares(palabras_lista: list, lecciones_lista: list, oraciones_dict: dict):
    """
    Compilador curricular 11 Tipos (versión 4 adaptada para Unity):
      - 11 tipos estrictamente permitidos.
      - 1 presentación por familia nueva + 1 microactividad inmediata obligatoria.
      - 4 a 6 actividades de escritura libre por lección.
      - Sin duplicación de objetivos escritos ni de oraciones por modalidad (dictado vs traducción).
      - Menos de 804 pasos globales.
      - Salida 100% determinista.
    """
    # 1. Índices de resolución
    indice_raices = {}
    indice_formas = {}
    multi_palabras = []
    palabras_map = {p["id"]: p for p in palabras_lista}
    formas_map = {}

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

    # Identificación curricular
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
    formas_por_familia = {
        familia: {f["id"] for f in palabras_map[familia].get("formas", [])}
        for familia in palabras_map
    }

    metricas = {tipo: {f"P{i}": 0 for i in range(1, 5)} for tipo in ("palabras", "formas", "oraciones")}

    familias_presentadas_global = set()
    palabras_escritas_global = set()
    leccion_origen_familia = {}
    lecciones_compiladas = []
    informe_compilacion = []

    def familias_recientes(n_lecciones=5):
        recientes = set()
        for lec_prev in lecciones_compiladas[-n_lecciones:]:
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

    idx_micro_global = 0

    # -----------------------------------------------------------------------
    # Recorrido de Lecciones Curriculares (L01 a L27)
    # -----------------------------------------------------------------------
    for lec_idx, lec in enumerate(lecciones_lista):
        lid = lec["id"]
        semilla = sum(ord(c) * (i + 1) for i, c in enumerate(lid))
        rng = random.Random(semilla)

        # Resolver familias presentes en las oraciones de esta lección
        familias_en_leccion = set()
        for oid in lec["oraciones_ids"]:
            if oid in oraciones_dict:
                familias_en_leccion.update(resolver_familias_en_oracion(
                    oraciones_dict[oid]["uch"], indice_raices, indice_formas, multi_palabras
                ))

        familias_nuevas = sorted(list(familias_en_leccion - familias_presentadas_global))
        familias_repaso = sorted(list(familias_en_leccion & familias_presentadas_global))
        familias_futuras = familias_curriculares - familias_presentadas_global - set(familias_en_leccion)

        estado = EstadoLeccion(
            leccion_id=lid,
            rng=rng,
            familias_nuevas=familias_nuevas,
            familias_repaso=familias_repaso,
            familias_futuras=familias_futuras,
            oraciones_ids=lec["oraciones_ids"]
        )

        familias_repaso_organico = []
        repaso_organico_set = set()

        def registrar_repaso_organico(fid, uso_tipo):
            if (fid in familias_presentadas_global
                    and fid not in familias_en_leccion
                    and fid not in repaso_organico_set):
                origen = leccion_origen_familia.get(fid, "?")
                familias_repaso_organico.append({
                    "familia_id": fid, "leccion_origen": origen, "uso": uso_tipo
                })
                repaso_organico_set.add(fid)

        n_nuevas = len(familias_nuevas)
        punto_asr1 = max(1, round(n_nuevas * 0.40)) if n_nuevas > 0 else 0
        punto_asr2 = max(punto_asr1 + 2, round(n_nuevas * 0.75)) if n_nuevas >= 8 else None

        # ===================================================================
        # ETAPA 1: Presentación de Familias y Microactividades Inmediatas
        # ===================================================================
        familias_evaluadas_en_orden = []

        for fn_idx, fid in enumerate(familias_nuevas):
            if fid not in palabras_map:
                continue
            p_data = palabras_map[fid]
            estado.familias_presentadas.add(fid)
            tiene_formas = "formas" in p_data and len(p_data["formas"]) > 0

            # 1.1 Presentación de la familia (EXACTAMENTE UNA POR FAMILIA NUEVA)
            estado.agregar_paso({
                "tipo": "presentacion_familia",
                "objetivo_id": fid,
                "tiene_formas": tiene_formas,
                "seccion": "palabras_nuevas",
                "fuente_estimulo": "audio"
            }, es_evaluacion=False)

            # 1.2 Microactividad inmediata obligatoria
            # Si tiene formas y no se ha emitido audio_a_forma en la lección, usarlo
            usar_audio_forma = tiene_formas and (estado.audio_forma_realizados < 1) and (fn_idx % 2 == 1)
            emitio_micro = False

            if usar_audio_forma:
                forma_sel = p_data["formas"][0]
                opciones_f = distractores_forma(forma_sel["id"], familias_en_leccion, familias_futuras, rng)
                if len(opciones_f) >= 2:
                    estado.agregar_paso({
                        "tipo": "audio_a_forma",
                        "forma_id": forma_sel["id"],
                        "raiz_id": fid,
                        "opciones_ids": opciones_f,
                        "seccion": "palabras_nuevas",
                        "fuente_estimulo": "audio"
                    }, es_evaluacion=True)
                    estado.audio_forma_realizados += 1
                    familias_evaluadas_en_orden.append(fid)
                    emitio_micro = True

            # Si no usó forma, alternar deterministamente entre uch_a_es y audio_a_uch
            if not emitio_micro:
                mod_micro = "uch_a_es" if (idx_micro_global % 2 == 0) else "audio_a_uch"
                idx_micro_global += 1

                opciones_micro = distractores_raiz(fid, familias_en_leccion, familias_futuras, rng)
                for dist_id in opciones_micro:
                    if dist_id != fid:
                        registrar_repaso_organico(dist_id, "distractor")

                estado.agregar_paso({
                    "tipo": mod_micro,
                    "objetivo_id": fid,
                    "opciones_ids": opciones_micro,
                    "seccion": "palabras_nuevas",
                    "fuente_estimulo": "texto_uch" if mod_micro == "uch_a_es" else "audio"
                }, es_evaluacion=True)

                familias_evaluadas_en_orden.append(fid)

            # 1.3 Intercalado: ASR Léxico 1
            if estado.asr_lexico_realizados == 0 and (fn_idx + 1) == punto_asr1:
                candidatos_asr = [
                    f for f in familias_evaluadas_en_orden
                    if estado.distancia_desde_evaluacion(f) >= 2
                ]
                if not candidatos_asr and familias_evaluadas_en_orden:
                    candidatos_asr = [f for f in familias_evaluadas_en_orden if f != fid]
                if candidatos_asr and estado.ultima_mecanica() != "asr":
                    target_asr = candidatos_asr[0]
                    estado.posiciones_asr.append({
                        "tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr
                    })
                    estado.agregar_paso({
                        "tipo": "escucha_y_repite_asr",
                        "objetivo_id": target_asr,
                        "opcional": True,
                        "seccion": "practica_oral",
                        "fuente_estimulo": "audio"
                    }, es_evaluacion=True)
                    estado.asr_lexico_realizados += 1

            # 1.4 Primer Emparejamiento Curricular: a la mitad de familias nuevas (después de su microactividad)
            mitad = n_nuevas // 2
            if (fn_idx + 1) == mitad and estado.emparejar_realizados == 0:
                rng_emp1 = random.Random(obtener_semilla_estable(lid, "emparejamiento_1"))
                primeras_nuevas = familias_nuevas[:mitad]
                cands_emp1_nuevas = list(primeras_nuevas)
                rng_emp1.shuffle(cands_emp1_nuevas)
                sel_emp1 = items_validos_emparejamiento(cands_emp1_nuevas, palabras_map, max_items=5)

                if len(sel_emp1) < 5 and familias_presentadas_global:
                    # Priorizar familias de repaso aprendidas previamente que NO pertenezcan a las oraciones
                    # de esta lección, para preservar todo el vocabulario de esta lección disponible para Emp 2
                    cands_prev_fuera = sorted(list(familias_presentadas_global - set(familias_en_leccion) - set(sel_emp1)))
                    rng_emp1.shuffle(cands_prev_fuera)

                    cands_prev_dentro = sorted(list((familias_presentadas_global & set(familias_en_leccion)) - set(sel_emp1)))
                    rng_emp1.shuffle(cands_prev_dentro)

                    cands_totales_1 = sel_emp1 + cands_prev_fuera + cands_prev_dentro
                    sel_emp1 = items_validos_emparejamiento(cands_totales_1, palabras_map, max_items=5)
                    for r_fid in sel_emp1:
                        if r_fid in familias_presentadas_global and r_fid not in familias_en_leccion:
                            registrar_repaso_organico(r_fid, "emparejamiento")

                if len(sel_emp1) >= 2:
                    estado.agregar_paso({
                        "tipo": "emparejar_uch_es",
                        "items_ids": sorted(sel_emp1),
                        "seccion": "palabras_nuevas",
                        "fuente_estimulo": "texto_uch"
                    }, es_evaluacion=False)
                    estado.emparejar_realizados += 1

            # 1.5 Intercalado: ASR Léxico 2 (para lecciones grandes)
            if (punto_asr2 is not None
                    and estado.asr_lexico_realizados == 1
                    and (fn_idx + 1) == punto_asr2):
                candidatos_asr = [
                    f for f in familias_evaluadas_en_orden
                    if estado.distancia_desde_evaluacion(f) >= 3
                    and ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
                ]
                if candidatos_asr and estado.ultima_mecanica() != "asr":
                    target_asr = candidatos_asr[-1]
                    estado.posiciones_asr.append({
                        "tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr
                    })
                    estado.agregar_paso({
                        "tipo": "escucha_y_repite_asr",
                        "objetivo_id": target_asr,
                        "opcional": True,
                        "seccion": "practica_oral",
                        "fuente_estimulo": "audio"
                    }, es_evaluacion=True)
                    estado.asr_lexico_realizados += 1

        # ===================================================================
        # ETAPA 1.6: Segundo Emparejamiento Curricular (al terminar vocabulario nuevo)
        # ===================================================================
        if estado.emparejar_realizados == 1:
            rng_emp2 = random.Random(obtener_semilla_estable(lid, "emparejamiento_2"))
            items_emp1_set = set()
            for p_ant in estado.pasos:
                if p_ant["tipo"] == "emparejar_uch_es":
                    items_emp1_set.update(p_ant.get("items_ids", []))

            # Prioridad 1: Familias nuevas que no participaron en el primer emparejamiento
            nuevas_restantes = [f for f in familias_nuevas if f not in items_emp1_set]
            rng_emp2.shuffle(nuevas_restantes)

            # Prioridad 2: Familias de repaso de ESTA lección (de sus oraciones) que no participaron en Emp 1
            repaso_leccion = [f for f in familias_repaso if f not in items_emp1_set]
            rng_emp2.shuffle(repaso_leccion)

            # Candidatos sin repetición: unión de nuevas restantes y repaso de la lección
            pool_emp2_sin_repetir = nuevas_restantes + repaso_leccion
            sel_emp2 = items_validos_emparejamiento(pool_emp2_sin_repetir, palabras_map, max_items=5)

            # Regla 7: Si no existen suficientes familias distintas, reducir la cantidad de parejas
            # en vez de repetir palabras artificialmente. Solo si len(sel_emp2) < 2 recurrir a reutilizar.
            if len(sel_emp2) < 2:
                reutilizables = [f for f in (set(familias_nuevas) | set(familias_repaso)) if f in items_emp1_set]
                rng_emp2.shuffle(reutilizables)
                sel_emp2 = items_validos_emparejamiento(pool_emp2_sin_repetir + reutilizables, palabras_map, max_items=5)

            if len(sel_emp2) >= 2:
                estado.agregar_paso({
                    "tipo": "emparejar_uch_es",
                    "items_ids": sorted(sel_emp2),
                    "seccion": "palabras_nuevas",
                    "fuente_estimulo": "texto_uch"
                }, es_evaluacion=False)
                estado.emparejar_realizados += 1

        # ===================================================================
        # ETAPA 2: Práctica de Escritura Libre Léxica (Palabras y Formas)
        # ===================================================================
        # 2.1 Escritura de Forma documentada (máx 1 por lección si hay formas válidas)
        candidatos_forma_esc = []
        for fid in familias_evaluadas_en_orden:
            p_info = palabras_map.get(fid, {})
            for frm in p_info.get("formas", []):
                frm_id = frm["id"]
                norm_f = normalizar_texto(frm["uch"])
                if (frm_id not in estado.escrituras_usadas_ids
                        and norm_f not in estado.escrituras_usadas_uch_norm
                        and estado.distancia_desde_evaluacion(fid) >= 2):
                    candidatos_forma_esc.append((fid, frm))

        if candidatos_forma_esc and estado.escrituras_formas_realizadas == 0:
            fid_f, frm_sel = candidatos_forma_esc[0]
            consigna_limpia = limpiar_texto_consigna(frm_sel["es"])
            consigna = CONSIGNAS_FORMA[0][0].format(es=consigna_limpia)
            fuente_esc = CONSIGNAS_FORMA[0][1]
            refuerzo_mod = REFUERZO_MAP["escribir_forma"][0]

            estado.agregar_paso({
                "tipo": "escribir_forma",
                "forma_id": frm_sel["id"],
                "raiz_id": fid_f,
                "respuesta_esperada_uch": frm_sel["uch"],
                "consigna": consigna,
                "fuente_estimulo": fuente_esc,
                "refuerzo_al_fallar": {
                    "tipo": refuerzo_mod,
                    "forma_id": frm_sel["id"],
                    "raiz_id": fid_f
                },
                "seccion": "palabras_nuevas"
            }, es_evaluacion=True)
            estado.escrituras_formas_realizadas += 1

        # 2.2 Escritura de Palabras (raíces) con Prioridad Curricular de 4 Niveles
        tier1 = [
            f for f in familias_nuevas
            if f in palabras_map
            and f not in estado.escrituras_usadas_ids
            and normalizar_texto(palabras_map[f]["uch"]) not in estado.escrituras_usadas_uch_norm
        ]
        if lid == "L06":
            tier1.sort(key=lambda x: (0 if x in ["amchuki", "wisnakti"] else 1, -estado.distancia_desde_evaluacion(x)))
        else:
            tier1.sort(key=lambda x: -estado.distancia_desde_evaluacion(x))

        tier2 = [
            f for f in familias_repaso
            if f in palabras_map
            and f not in estado.escrituras_usadas_ids
            and normalizar_texto(palabras_map[f]["uch"]) not in estado.escrituras_usadas_uch_norm
            and f not in palabras_escritas_global
        ]
        tier2.sort(key=lambda x: -estado.distancia_desde_evaluacion(x))

        tier3 = [
            f for f in familias_repaso
            if f in palabras_map
            and f not in estado.escrituras_usadas_ids
            and normalizar_texto(palabras_map[f]["uch"]) not in estado.escrituras_usadas_uch_norm
            and f in palabras_escritas_global
        ]
        tier3.sort(key=lambda x: -estado.distancia_desde_evaluacion(x))

        pool_palabras_esc = tier1 + tier2 + tier3
        for fid_pal in pool_palabras_esc:
            if estado.escrituras_palabras_realizadas >= estado.presupuesto_escritura_palabras:
                break
            p_data = palabras_map[fid_pal]
            norm_p = normalizar_texto(p_data["uch"])

            if (fid_pal in estado.escrituras_usadas_ids
                    or norm_p in estado.escrituras_usadas_uch_norm):
                continue

            consigna_idx = estado.escrituras_palabras_realizadas % len(CONSIGNAS_PALABRA)
            consigna_tmpl, fuente_esc = CONSIGNAS_PALABRA[consigna_idx]
            es_limpio = limpiar_texto_consigna(p_data["es"])
            consigna = consigna_tmpl.format(es=es_limpio)
            refuerzo_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_palabras_realizadas % len(REFUERZO_MAP["escribir_palabra"])]

            estado.agregar_paso({
                "tipo": "escribir_palabra",
                "objetivo_id": fid_pal,
                "respuesta_esperada_uch": p_data["uch"],
                "consigna": consigna,
                "fuente_estimulo": fuente_esc,
                "refuerzo_al_fallar": {
                    "tipo": refuerzo_mod,
                    "objetivo_id": fid_pal
                },
                "seccion": "palabras_nuevas"
            }, es_evaluacion=True)
            estado.escrituras_palabras_realizadas += 1
            palabras_escritas_global.add(fid_pal)

        # Completar ASR léxico si faltaba la meta de 1
        if estado.asr_lexico_realizados < estado.meta_asr_lexico and familias_evaluadas_en_orden:
            cands_asr = [
                f for f in familias_evaluadas_en_orden
                if ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
            ]
            if cands_asr and estado.ultima_mecanica() != "asr":
                target_asr = cands_asr[0]
                estado.posiciones_asr.append({"tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr})
                estado.agregar_paso({
                    "tipo": "escucha_y_repite_asr",
                    "objetivo_id": target_asr,
                    "opcional": True,
                    "seccion": "practica_oral",
                    "fuente_estimulo": "audio"
                }, es_evaluacion=True)
                estado.asr_lexico_realizados += 1

        # ===================================================================
        # ETAPA 3: Práctica de Oraciones (Construcción, Escritura y ASR)
        # ===================================================================
        oraciones_en_leccion = [oid for oid in lec["oraciones_ids"] if oid in oraciones_dict]
        todas_presentadas = familias_presentadas_global | set(familias_nuevas)

        # 3.1 Identificar oraciones elegibles para escritura libre (2 a 6 tokens, vocabulario cubierto)
        oraciones_elegibles_escritura = []
        oraciones_no_elegibles_escritura = []

        for oid in oraciones_en_leccion:
            o_data = oraciones_dict[oid]
            n_tokens = len(o_data["uch"].split())
            if not (2 <= n_tokens <= 6):
                oraciones_no_elegibles_escritura.append({
                    "id": oid, "motivo": f"tokens={n_tokens}, fuera de rango 2-6"
                })
                continue
            try:
                fams = resolver_familias_en_oracion(
                    o_data["uch"], indice_raices, indice_formas, multi_palabras
                )
                if fams.issubset(todas_presentadas):
                    oraciones_elegibles_escritura.append(oid)
                else:
                    faltantes = fams - todas_presentadas
                    oraciones_no_elegibles_escritura.append({
                        "id": oid, "motivo": f"familias no presentadas: {sorted(faltantes)}"
                    })
            except ValueError:
                oraciones_no_elegibles_escritura.append({
                    "id": oid, "motivo": "error de resolución léxica"
                })

        # 3.2 Asignar oraciones para Traducción escrita (texto_es) y Dictado escrito (audio)
        # REGLA OBLIGATORIA: Dictado y traducción no pueden compartir el mismo oracion_id
        oid_traduccion = None
        oid_dictado = None

        if len(oraciones_elegibles_escritura) >= 2:
            oid_traduccion = oraciones_elegibles_escritura[0]
            oid_dictado = oraciones_elegibles_escritura[1]
        elif len(oraciones_elegibles_escritura) == 1:
            if lec_idx % 2 == 0:
                oid_traduccion = oraciones_elegibles_escritura[0]
            else:
                oid_dictado = oraciones_elegibles_escritura[0]

        # 3.3 Asignar oración para ASR oral
        candidatos_asr_oracion = [
            oid for oid in oraciones_en_leccion
            if 2 <= len(oraciones_dict[oid]["uch"].split()) <= 6
        ]
        target_oracion_asr = None
        no_escritas_asr = [oid for oid in candidatos_asr_oracion if oid != oid_traduccion and oid != oid_dictado]
        if no_escritas_asr:
            target_oracion_asr = no_escritas_asr[0]
        elif candidatos_asr_oracion:
            target_oracion_asr = candidatos_asr_oracion[0]
        elif oraciones_en_leccion:
            target_oracion_asr = oraciones_en_leccion[0]

        # 3.4 Asignar ordenar_oracion a las oraciones que no se escriben
        # REGLA OBLIGATORIA: Verificar que la oración tenga al menos dos palabras o unidades independientes.
        # Excluir automáticamente oraciones de un solo token (e.g. O_011 en L04 tiene 1 solo token).
        oraciones_descartadas_ordenar = []
        oraciones_para_ordenar = []
        for oid in oraciones_en_leccion:
            if oid == oid_traduccion or oid == oid_dictado:
                continue
            o_uch = oraciones_dict[oid]["uch"]
            tokens = o_uch.split()
            if len(tokens) < 2:
                oraciones_descartadas_ordenar.append({
                    "oracion_id": oid,
                    "tokens": len(tokens),
                    "motivo": f"tokens={len(tokens)} (< 2), oración de un solo token no apta para ordenamiento con fichas"
                })
                continue
            oraciones_para_ordenar.append(oid)

        # Si no hay oraciones no escritas elegibles, buscar otra oración de la lección con >= 2 tokens
        if not oraciones_para_ordenar:
            cands_fallback = [oid for oid in oraciones_en_leccion if len(oraciones_dict[oid]["uch"].split()) >= 2]
            if cands_fallback:
                oraciones_para_ordenar = [cands_fallback[0]]

        # 3.5 Construir la secuencia de oraciones intercalando mecánicas
        pasos_oracion = []
        rec_cola = list(oraciones_para_ordenar)

        # Primer ordenamiento de oración (construcción guiada)
        if rec_cola:
            oid_ord = rec_cola.pop(0)
            pasos_oracion.append({
                "tipo": "ordenar_oracion",
                "oracion_id": oid_ord,
                "seccion": "practica_oracion",
                "fuente_estimulo": "texto_es"
            })

        # Traducción escrita
        if oid_traduccion:
            o_data = oraciones_dict[oid_traduccion]
            es_limpio = limpiar_texto_consigna(o_data["es"])
            consigna = CONSIGNAS_ORACION_TRADUCCION.format(es=es_limpio)
            pasos_oracion.append({
                "tipo": "escribir_oracion",
                "oracion_id": oid_traduccion,
                "respuesta_esperada_uch": o_data["uch"],
                "consigna": consigna,
                "fuente_estimulo": "texto_es",
                "refuerzo_al_fallar": {
                    "tipo": REFUERZO_MAP["escribir_oracion"][0],
                    "oracion_id": oid_traduccion
                },
                "seccion": "practica_oracion"
            })

        # Práctica oral opcional de oración (ASR)
        if target_oracion_asr:
            pasos_oracion.append({
                "tipo": "escucha_y_repite_oracion_asr",
                "oracion_id": target_oracion_asr,
                "opcional": True,
                "seccion": "practica_oral",
                "fuente_estimulo": "audio"
            })

        # Dictado escrito
        if oid_dictado:
            o_data = oraciones_dict[oid_dictado]
            pasos_oracion.append({
                "tipo": "escribir_oracion",
                "oracion_id": oid_dictado,
                "respuesta_esperada_uch": o_data["uch"],
                "consigna": CONSIGNAS_ORACION_DICTADO,
                "fuente_estimulo": "audio",
                "refuerzo_al_fallar": {
                    "tipo": REFUERZO_MAP["escribir_oracion"][0],
                    "oracion_id": oid_dictado
                },
                "seccion": "practica_oracion"
            })

        # Ordenamientos de oraciones restantes para cubrir toda la lección
        while rec_cola:
            oid_ord = rec_cola.pop(0)
            pasos_oracion.append({
                "tipo": "ordenar_oracion",
                "oracion_id": oid_ord,
                "seccion": "practica_oracion",
                "fuente_estimulo": "texto_es"
            })

        # Agregar los pasos de oraciones asegurando registro y métricas
        for paso_o in pasos_oracion:
            t_o = paso_o["tipo"]
            if t_o == "escucha_y_repite_oracion_asr":
                estado.posiciones_asr.append({
                    "tipo": "escucha_y_repite_oracion_asr",
                    "pos": len(estado.pasos),
                    "target": paso_o["oracion_id"]
                })
                estado.asr_oracion_realizados += 1
            elif t_o == "escribir_oracion":
                estado.escrituras_oraciones_realizadas += 1

            estado.agregar_paso(paso_o, es_evaluacion=True)

        # ===================================================================
        # ETAPA 4: Conteo y Construcción del Informe de la Lección
        # ===================================================================
        pasos_por_tipo = {}
        for paso in estado.pasos:
            t = paso["tipo"]
            pasos_por_tipo[t] = pasos_por_tipo.get(t, 0) + 1

        total_escrituras_leccion = (
            estado.escrituras_palabras_realizadas
            + estado.escrituras_formas_realizadas
            + estado.escrituras_oraciones_realizadas
        )

        inf_lec = {
            "leccion_id": lid,
            "familias_nuevas": len(familias_nuevas),
            "familias_repaso_leccion": len(familias_repaso),
            "total_pasos": len(estado.pasos),
            "pasos_por_tipo": pasos_por_tipo,
            "escrituras_libres_totales": total_escrituras_leccion,
            "desglose_escritura": {
                "palabras": estado.escrituras_palabras_realizadas,
                "formas": estado.escrituras_formas_realizadas,
                "oraciones_traduccion": 1 if oid_traduccion else 0,
                "oraciones_dictado": 1 if oid_dictado else 0
            },
            "posiciones_asr": estado.posiciones_asr,
            "objetivos_escritura": estado.objetivos_escritura,
            "repaso_colectivo": {
                "total": estado.emparejar_realizados,
                "emparejar_uch_es": pasos_por_tipo.get("emparejar_uch_es", 0)
            },
            "oracion_asr_seleccionada": target_oracion_asr,
            "oraciones_no_elegibles_para_escritura": oraciones_no_elegibles_escritura,
            "oraciones_descartadas_ordenar": oraciones_descartadas_ordenar,
            "opciones_reducidas": estado.opciones_reducidas,
            "familias_repaso_organico": [
                {"familia_id": r["familia_id"], "leccion_origen": r["leccion_origen"], "uso": r["uso"]}
                for r in familias_repaso_organico
            ]
        }
        informe_compilacion.append(inf_lec)

        lec_compilada = {
            "id": lid,
            "titulo": lec["titulo"],
            "orden": lec["orden"],
            "familias_nuevas": familias_nuevas,
            "familias_repaso": familias_repaso,
            "familias_repaso_organico": familias_repaso_organico,
            "oraciones_ids": lec["oraciones_ids"],
            "pasos": estado.pasos
        }
        lecciones_compiladas.append(lec_compilada)

        familias_presentadas_global.update(familias_nuevas)
        for fid in familias_nuevas:
            leccion_origen_familia[fid] = lid

    return lecciones_compiladas, metricas, informe_compilacion
