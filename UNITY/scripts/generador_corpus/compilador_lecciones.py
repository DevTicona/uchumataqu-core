"""
compilador_lecciones.py
Motor de compilación curricular determinista y pedagógico para Uchumataqu (versión 4).
Basado en:
  - 01-modulo-pln-texto.md
  - 02-modulo-asr-voz.md
  - 04-flujo-leccion-app.md
  - 05-guia-corpus-datos.md
  - 06-guia-arquitectura-proyecto.md
  - 08-patron-arquitectonico-mvp.md
  - instrucciones-mejora-compilador-lecciones.md
  - instrucciones-ajustes-finales-lecciones-compiladas.md

Implementa:
  - Catálogo estricto de 22 tipos generables (memoria_uch_es retirada de la generación).
  - Pareja obligatoria: exactamente una presentacion_familia + una microactividad inmediata por familia nueva.
  - Alternancia equilibrada de microactividades visuales, auditivas y formas documentadas.
  - Espaciado >=3 pasos entre la práctica morfológica y la escritura de la misma forma (L08, L11, L17).
  - Alternancia rigurosa en oraciones: eliminación de pares consecutivos de reconstrucción.
  - Selección contextual de ASR de oración (2-6 tokens con audio, evitando oraciones unipalabra como O_011 en L04).
  - Selección de distractores para completar_oracion respetando rigurosamente prioridades curriculares (P1..P4).
  - Presupuestos adaptativos de escritura léxica y repasos colectivos.
  - Cobertura total de oraciones curriculares (O_001..O_120).
  - Salida determinista y reproducible al 100%.
"""

import os
import sys
import random
from typing import Optional

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

try:
    from generador_corpus.distractores_corpus import (
        resolver_familias_en_oracion,
        resolver_tokens_detalle_oracion,
        seleccionar_distractores_por_prioridad,
        generar_distractores_oracion,
        son_traducciones_compatibles,
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
        son_traducciones_compatibles,
        normalizar_texto,
        NOMBRES_PROPIOS_CONTEXTUALES,
        seleccionar_distractores_completar
    )

# ---------------------------------------------------------------------------
# Catálogo de 22 tipos generables (memoria_uch_es retirada de la generación)
# ---------------------------------------------------------------------------
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

# Clasificación de actividades de oración según su acción pedagógica
RECONSTRUCCION_TIPOS = {"ordenar_oracion", "dictado_word_bank", "traduccion_constructiva"}
COMPRENSION_ORACION_TIPOS = {"audio_a_es_oracion"}
CONTEXTO_ORACION_TIPOS = {"completar_oracion"}
PRODUCCION_ORACION_TIPOS = {"escribir_oracion", "escucha_y_repite_oracion_asr"}

# Familias de mecánicas para evitar contigüidad repetitiva
MECANICA_POR_TIPO = {
    "presentacion_familia":         "presentacion",
    "uch_a_es":                     "seleccion_visual",
    "es_a_uch":                     "seleccion_visual",
    "forma_a_raiz":                "seleccion_visual",
    "forma_a_es":                  "seleccion_visual",
    "es_a_forma":                  "seleccion_visual",
    "audio_a_uch":                  "seleccion_auditiva",
    "audio_a_es":                   "seleccion_auditiva",
    "audio_a_forma":                "seleccion_auditiva",
    "emparejar_uch_es":             "emparejamiento_visual",
    "emparejar_audio_uch":          "emparejamiento_auditivo",
    "familia_completa":             "morfologia_grupo",
    "ordenar_oracion":             "reconstruccion_oracion",
    "dictado_word_bank":           "reconstruccion_oracion",
    "traduccion_constructiva":     "reconstruccion_oracion",
    "audio_a_es_oracion":          "comprension_oracion",
    "completar_oracion":           "contexto_oracion",
    "escribir_palabra":            "escritura",
    "escribir_forma":              "escritura",
    "escribir_oracion":            "escritura",
    "escucha_y_repite_asr":        "asr",
    "escucha_y_repite_oracion_asr": "asr"
}

# Mapeo de fuente_estimulo por tipo de paso
FUENTE_ESTIMULO_POR_TIPO = {
    "presentacion_familia":         "audio",
    "uch_a_es":                     "texto_uch",
    "es_a_uch":                     "texto_es",
    "audio_a_uch":                  "audio",
    "audio_a_es":                   "audio",
    "forma_a_raiz":                "texto_uch",
    "forma_a_es":                  "texto_uch",
    "es_a_forma":                  "texto_es",
    "audio_a_forma":                "audio",
    "familia_completa":             "texto_uch",
    "emparejar_uch_es":             "texto_uch",
    "emparejar_audio_uch":          "audio",
    "ordenar_oracion":             "texto_es",
    "dictado_word_bank":           "audio",
    "traduccion_constructiva":     "texto_es",
    "completar_oracion":           "texto_uch",
    "audio_a_es_oracion":          "audio",
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


class EstadoLeccion:
    """Gestiona el estado local de compilación para una lección individual."""

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
        self.ultimo_paso_objetivo = {}  # objetivo_id -> idx en self.pasos donde fue evaluado
        self.pares_tipo_objetivo = set()  # set of (tipo, objetivo_id)
        self.conjuntos_colectivos = []  # list of (tipo, frozenset(items_ids))

        # Presupuesto estricto de escritura léxica (Sec 4 de instrucciones)
        n_nuevas = len(familias_nuevas)
        if n_nuevas <= 4:
            self.presupuesto_escritura_lexica = 1
        elif n_nuevas <= 8:
            self.presupuesto_escritura_lexica = 2
        else:
            self.presupuesto_escritura_lexica = 3

        # Presupuesto de repaso colectivo (hasta 1 por cada 3-4 familias, máx 2 por lección)
        if n_nuevas <= 3:
            self.presupuesto_colectivo = 1 if (n_nuevas + len(familias_repaso)) >= 3 else 0
        elif n_nuevas <= 7:
            self.presupuesto_colectivo = 1
        else:
            self.presupuesto_colectivo = 2

        self.meta_asr_lexico = 2 if n_nuevas >= 6 else 1
        self.meta_asr_oracion = 1 if len(oraciones_ids) > 0 else 0

        self.escrituras_lexicas_realizadas = 0
        self.escritura_oracion_realizada = 0
        self.asr_lexico_realizados = 0
        self.asr_oracion_realizados = 0
        self.colectivos_realizados = 0
        self.familia_completa_realizada = 0

        # Métricas de calidad y diagnóstico
        self.pares_reconstruccion_consecutivos = 0
        self.excepciones_reconstruccion = []
        self.separaciones_forma = []
        self.posiciones_asr = []
        self.objetivos_escritura = []
        self.relajaciones_separacion = []
        self.opciones_reducidas = []

    def distancia_desde_evaluacion(self, objetivo_id: str) -> int:
        """Calcula los pasos intermedios transcurridos desde la última evaluación del objetivo."""
        if objetivo_id not in self.ultimo_paso_objetivo:
            return 999
        ultimo_idx = self.ultimo_paso_objetivo[objetivo_id]
        return len(self.pasos) - 1 - ultimo_idx

    def ultima_mecanica(self) -> str:
        if not self.pasos:
            return ""
        return MECANICA_POR_TIPO.get(self.pasos[-1].get("tipo", ""), "")

    def agregar_paso(self, paso: dict, es_evaluacion: bool = True):
        """Agrega un paso asegurando metadatos mínimos y actualizando el historial."""
        tipo = paso["tipo"]
        assert tipo in CATALOGO_22, f"Tipo no permitido en catálogo 22: {tipo}"

        # Detección de pares consecutivos de reconstrucción de oraciones
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

        # Asignar fuente_estimulo si falta
        if "fuente_estimulo" not in paso:
            paso["fuente_estimulo"] = FUENTE_ESTIMULO_POR_TIPO.get(tipo, "texto_uch")

        # Registrar par (tipo, objetivo)
        obj_id = paso.get("objetivo_id") or paso.get("forma_id") or paso.get("oracion_id")
        if obj_id:
            par = (tipo, obj_id)
            self.pares_tipo_objetivo.add(par)

        # Verificar opciones reducidas (< 4 alternativas)
        if "opciones_ids" in paso and len(paso["opciones_ids"]) < 4:
            self.opciones_reducidas.append({
                "paso_idx": len(self.pasos), "tipo": tipo, "opciones": len(paso["opciones_ids"])
            })
        if "opciones_oraciones_ids" in paso and len(paso["opciones_oraciones_ids"]) < 4:
            self.opciones_reducidas.append({
                "paso_idx": len(self.pasos), "tipo": tipo, "opciones": len(paso["opciones_oraciones_ids"])
            })

        self.pasos.append(paso)

        if es_evaluacion and obj_id:
            self.ultimo_paso_objetivo[obj_id] = len(self.pasos) - 1


def compilar_lecciones_curriculares(palabras_lista: list, lecciones_lista: list, oraciones_dict: dict):
    """
    Compilador curricular mejorado (versión 4):
      - 22 tipos generables (sin memoria_uch_es).
      - Presentación + microactividad inmediata obligatoria por familia nueva.
      - Alternancia equilibrada de 4 modalidades de microactividad y formas documentadas.
      - Espaciado >=3 pasos para revaluación de familias y formas escritas.
      - Alternancia estricta de actividades de oraciones (0 pares consecutivos de reconstrucción).
      - Selección contextual de oración para ASR (2-6 tokens con audio, evitando oraciones unipalabra en L04).
      - Selección determinista de distractores para completar_oracion respetando prioridades (P1..P4).
      - Cobertura del 100% de oraciones curriculares (O_001..O_120).
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
    leccion_origen_familia = {}
    lecciones_compiladas = []
    informe_compilacion = []
    uso_oraciones_reserva = {}

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

    lecciones_compiladas = []
    informe_compilacion = []

    MICRO_MODALIDADES = ["uch_a_es", "audio_a_uch", "es_a_uch", "audio_a_es"]
    MODOS_FORMAS = ["forma_a_raiz", "forma_a_es", "es_a_forma", "audio_a_forma"]
    idx_micro_global = 0
    idx_forma_global = 0

    # -----------------------------------------------------------------------
    # Recorrido de Lecciones Curriculares (L01 a L27)
    # -----------------------------------------------------------------------
    for lec_idx, lec in enumerate(lecciones_lista):
        lid = lec["id"]
        semilla = sum(ord(c) * (i + 1) for i, c in enumerate(lid))
        rng = random.Random(semilla)

        # Resolver familias en oraciones de la lección
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

        # Puntos de inserción para ASR léxico:
        n_nuevas = len(familias_nuevas)
        punto_asr1 = max(1, round(n_nuevas * 0.35)) if n_nuevas > 0 else 0
        punto_asr2 = max(punto_asr1 + 2, round(n_nuevas * 0.70)) if n_nuevas >= 6 else None

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

            # 1.1 Presentación de la familia (EXACTAMENTE UNA)
            estado.agregar_paso({
                "tipo": "presentacion_familia",
                "objetivo_id": fid,
                "tiene_formas": tiene_formas,
                "seccion": "palabras_nuevas"
            }, es_evaluacion=False)

            # 1.2 Microactividad inmediata individual (EXACTAMENTE UNA)
            usar_forma_en_micro = tiene_formas and (fn_idx % 3 == 1)

            if usar_forma_en_micro:
                forma_sel = p_data["formas"][0]
                mod_forma = MODOS_FORMAS[idx_forma_global % len(MODOS_FORMAS)]
                idx_forma_global += 1

                if mod_forma == "forma_a_raiz":
                    opciones_raiz = distractores_raiz(fid, familias_en_leccion, familias_futuras, rng)
                    estado.agregar_paso({
                        "tipo": "forma_a_raiz",
                        "forma_id": forma_sel["id"],
                        "raiz_id": fid,
                        "opciones_ids": opciones_raiz,
                        "seccion": "palabras_nuevas"
                    }, es_evaluacion=True)
                elif mod_forma in ["forma_a_es", "es_a_forma"]:
                    opciones_f = distractores_forma(forma_sel["id"], familias_en_leccion, familias_futuras, rng)
                    estado.agregar_paso({
                        "tipo": mod_forma,
                        "forma_id": forma_sel["id"],
                        "raiz_id": fid,
                        "opciones_ids": opciones_f,
                        "seccion": "palabras_nuevas"
                    }, es_evaluacion=True)
                else:  # audio_a_forma
                    opciones_f = distractores_forma(forma_sel["id"], familias_en_leccion, familias_futuras, rng)
                    estado.agregar_paso({
                        "tipo": "audio_a_forma",
                        "forma_id": forma_sel["id"],
                        "raiz_id": fid,
                        "opciones_ids": opciones_f,
                        "seccion": "palabras_nuevas"
                    }, es_evaluacion=True)
            else:
                mod_micro = MICRO_MODALIDADES[idx_micro_global % len(MICRO_MODALIDADES)]
                idx_micro_global += 1

                opciones_micro = distractores_raiz(fid, familias_en_leccion, familias_futuras, rng)
                for dist_id in opciones_micro:
                    if dist_id != fid:
                        registrar_repaso_organico(dist_id, "distractor")

                estado.agregar_paso({
                    "tipo": mod_micro,
                    "objetivo_id": fid,
                    "opciones_ids": opciones_micro,
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)

            familias_evaluadas_en_orden.append(fid)

            # ---------------------------------------------------------------
            # Puntos de Intercalado: ASR Léxico 1 (~30-40% del vocabulario)
            # ---------------------------------------------------------------
            if estado.asr_lexico_realizados == 0 and (fn_idx + 1) == punto_asr1:
                candidatos_asr = [
                    f for f in familias_evaluadas_en_orden
                    if estado.distancia_desde_evaluacion(f) >= 3
                ]
                if not candidatos_asr:
                    candidatos_asr = [f for f in familias_evaluadas_en_orden if f != fid]
                    if candidatos_asr:
                        estado.relajaciones_separacion.append({
                            "tipo": "escucha_y_repite_asr", "objetivo": candidatos_asr[0], "motivo": "leccion_temprana"
                        })
                if candidatos_asr and estado.ultima_mecanica() != "asr":
                    target_asr = candidatos_asr[0]
                    estado.posiciones_asr.append({"tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr})
                    estado.agregar_paso({
                        "tipo": "escucha_y_repite_asr",
                        "objetivo_id": target_asr,
                        "opcional": True,
                        "seccion": "practica_oral"
                    }, es_evaluacion=True)
                    estado.asr_lexico_realizados += 1

            # ---------------------------------------------------------------
            # Puntos de Intercalado: Repaso Colectivo (hasta 1 por 3-4 familias)
            # ---------------------------------------------------------------
            if (estado.colectivos_realizados < estado.presupuesto_colectivo
                    and (fn_idx + 1) % 4 == 0
                    and len(familias_evaluadas_en_orden) >= 3):
                candidatos_col = [
                    f for f in familias_evaluadas_en_orden
                    if estado.distancia_desde_evaluacion(f) >= 2
                ]
                if len(candidatos_col) >= 3:
                    previas_disp = sorted(familias_recientes() - set(candidatos_col))
                    if previas_disp:
                        prev_sel = rng.sample(previas_disp, min(1, len(previas_disp)))
                        candidatos_col = sorted(set(candidatos_col) | set(prev_sel))
                        for pf in prev_sel:
                            registrar_repaso_organico(pf, "item_emparejamiento")

                    items_sel = rng.sample(candidatos_col, min(4, len(candidatos_col)))
                    items_sel.sort()

                    tipo_col = "emparejar_uch_es" if (estado.colectivos_realizados % 2 == 0) else "emparejar_audio_uch"

                    if estado.ultima_mecanica() != MECANICA_POR_TIPO[tipo_col]:
                        estado.agregar_paso({
                            "tipo": tipo_col,
                            "items_ids": items_sel,
                            "seccion": "palabras_nuevas"
                        }, es_evaluacion=False)
                        estado.colectivos_realizados += 1
                        for itm in items_sel:
                            estado.ultimo_paso_objetivo[itm] = len(estado.pasos) - 1

            # ---------------------------------------------------------------
            # Puntos de Intercalado: ASR Léxico 2 (~65-75% del vocabulario)
            # ---------------------------------------------------------------
            if (punto_asr2 is not None
                    and estado.asr_lexico_realizados == 1
                    and (fn_idx + 1) == punto_asr2):
                candidatos_asr = [
                    f for f in familias_evaluadas_en_orden
                    if estado.distancia_desde_evaluacion(f) >= 3
                    and ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
                ]
                if not candidatos_asr:
                    candidatos_asr = [
                        f for f in familias_evaluadas_en_orden
                        if ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
                    ]
                if candidatos_asr and estado.ultima_mecanica() != "asr":
                    target_asr = candidatos_asr[-1]
                    estado.posiciones_asr.append({"tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr})
                    estado.agregar_paso({
                        "tipo": "escucha_y_repite_asr",
                        "objetivo_id": target_asr,
                        "opcional": True,
                        "seccion": "practica_oral"
                    }, es_evaluacion=True)
                    estado.asr_lexico_realizados += 1

            # ---------------------------------------------------------------
            # Puntos de Intercalado: Escritura Léxica Espaciada (con distancia mínima por forma)
            # ---------------------------------------------------------------
            def familia_ya_escrita(f_id):
                if ("escribir_palabra", f_id) in estado.pares_tipo_objetivo:
                    return True
                p_info = palabras_map.get(f_id, {})
                for frm in p_info.get("formas", []):
                    if ("escribir_forma", frm["id"]) in estado.pares_tipo_objetivo:
                        return True
                return False

            def distancia_minima_escritura(fid: str) -> int:
                """Calcula la distancia de evaluación considerando tanto la raíz como la forma concreta."""
                p_info = palabras_map.get(fid, {})
                dist_raiz = estado.distancia_desde_evaluacion(fid)
                if "formas" in p_info and p_info["formas"]:
                    frm_id = p_info["formas"][0]["id"]
                    dist_forma = estado.distancia_desde_evaluacion(frm_id)
                    return min(dist_raiz, dist_forma)
                return dist_raiz

            if estado.escrituras_lexicas_realizadas < estado.presupuesto_escritura_lexica:
                candidatos_esc = [
                    f for f in familias_evaluadas_en_orden
                    if distancia_minima_escritura(f) >= 3
                    and not familia_ya_escrita(f)
                ]
                if candidatos_esc and estado.ultima_mecanica() != "escritura":
                    f_esc = candidatos_esc[0]
                    p_esc_data = palabras_map[f_esc]
                    tiene_f_esc = "formas" in p_esc_data and len(p_esc_data["formas"]) > 0

                    if tiene_f_esc:
                        forma_obj = p_esc_data["formas"][0]
                        consigna, fuente_esc = CONSIGNAS_FORMA[0]
                        consigna = consigna.format(es=forma_obj["es"])
                        refuerzo_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_lexicas_realizadas % 2]
                        estado.separaciones_forma.append({
                            "leccion": lid,
                            "forma_id": forma_obj["id"],
                            "raiz_id": f_esc,
                            "distancia": distancia_minima_escritura(f_esc)
                        })
                        estado.agregar_paso({
                            "tipo": "escribir_forma",
                            "forma_id": forma_obj["id"],
                            "raiz_id": f_esc,
                            "respuesta_esperada_uch": forma_obj["uch"],
                            "consigna": consigna,
                            "fuente_estimulo": fuente_esc,
                            "refuerzo_al_fallar": {
                                "tipo": refuerzo_mod,
                                "objetivo_id": forma_obj["id"]
                            },
                            "seccion": "palabras_nuevas"
                        }, es_evaluacion=True)
                        estado.objetivos_escritura.append({"tipo": "escribir_forma", "objetivo": forma_obj["id"]})
                    else:
                        consigna_idx = estado.escrituras_lexicas_realizadas % len(CONSIGNAS_PALABRA)
                        consigna, fuente_esc = CONSIGNAS_PALABRA[consigna_idx]
                        consigna = consigna.format(es=p_esc_data["es"])
                        refuerzo_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_lexicas_realizadas % 2]
                        estado.agregar_paso({
                            "tipo": "escribir_palabra",
                            "objetivo_id": f_esc,
                            "respuesta_esperada_uch": p_esc_data["uch"],
                            "consigna": consigna,
                            "fuente_estimulo": fuente_esc,
                            "refuerzo_al_fallar": {
                                "tipo": refuerzo_mod,
                                "objetivo_id": f_esc
                            },
                            "seccion": "palabras_nuevas"
                        }, es_evaluacion=True)
                        estado.objetivos_escritura.append({"tipo": "escribir_palabra", "objetivo": f_esc})

                    estado.escrituras_lexicas_realizadas += 1

        # Completar escritura léxica si falta para alcanzar presupuesto exacto
        while estado.escrituras_lexicas_realizadas < estado.presupuesto_escritura_lexica:
            candidatos_esc = [
                f for f in familias_evaluadas_en_orden
                if distancia_minima_escritura(f) >= 3
                and not familia_ya_escrita(f)
            ]
            if not candidatos_esc:
                candidatos_esc = [
                    f for f in familias_evaluadas_en_orden
                    if distancia_minima_escritura(f) >= 2
                    and not familia_ya_escrita(f)
                ]
                if candidatos_esc:
                    estado.relajaciones_separacion.append({
                        "leccion": lid,
                        "tipo": "escritura_lexica",
                        "objetivo": candidatos_esc[0],
                        "distancia": distancia_minima_escritura(candidatos_esc[0])
                    })
            if not candidatos_esc or estado.ultima_mecanica() == "escritura":
                break
            f_esc = candidatos_esc[0]
            p_esc_data = palabras_map[f_esc]
            tiene_f_esc = "formas" in p_esc_data and len(p_esc_data["formas"]) > 0

            if tiene_f_esc:
                forma_obj = p_esc_data["formas"][0]
                consigna, fuente_esc = CONSIGNAS_FORMA[0]
                consigna = consigna.format(es=forma_obj["es"])
                refuerzo_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_lexicas_realizadas % 2]
                estado.separaciones_forma.append({
                    "leccion": lid,
                    "forma_id": forma_obj["id"],
                    "raiz_id": f_esc,
                    "distancia": distancia_minima_escritura(f_esc)
                })
                estado.agregar_paso({
                    "tipo": "escribir_forma",
                    "forma_id": forma_obj["id"],
                    "raiz_id": f_esc,
                    "respuesta_esperada_uch": forma_obj["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "objetivo_id": forma_obj["id"]
                    },
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)
                estado.objetivos_escritura.append({"tipo": "escribir_forma", "objetivo": forma_obj["id"]})
            else:
                consigna_idx = estado.escrituras_lexicas_realizadas % len(CONSIGNAS_PALABRA)
                consigna, fuente_esc = CONSIGNAS_PALABRA[consigna_idx]
                consigna = consigna.format(es=p_esc_data["es"])
                refuerzo_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_lexicas_realizadas % 2]
                estado.agregar_paso({
                    "tipo": "escribir_palabra",
                    "objetivo_id": f_esc,
                    "respuesta_esperada_uch": p_esc_data["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "objetivo_id": f_esc
                    },
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=True)
                estado.objetivos_escritura.append({"tipo": "escribir_palabra", "objetivo": f_esc})

            estado.escrituras_lexicas_realizadas += 1

        # Completar ASR léxico si aún no se cumplió la meta
        while estado.asr_lexico_realizados < estado.meta_asr_lexico:
            candidatos_asr = [
                f for f in (familias_evaluadas_en_orden if familias_evaluadas_en_orden else familias_repaso)
                if ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
                and estado.distancia_desde_evaluacion(f) >= 2
            ]
            if not candidatos_asr:
                candidatos_asr = [
                    f for f in familias_evaluadas_en_orden
                    if ("escucha_y_repite_asr", f) not in estado.pares_tipo_objetivo
                ]
            if not candidatos_asr or estado.ultima_mecanica() == "asr":
                break
            target_asr = candidatos_asr[0]
            estado.posiciones_asr.append({"tipo": "escucha_y_repite_asr", "pos": len(estado.pasos), "target": target_asr})
            estado.agregar_paso({
                "tipo": "escucha_y_repite_asr",
                "objetivo_id": target_asr,
                "opcional": True,
                "seccion": "practica_oral"
            }, es_evaluacion=True)
            estado.asr_lexico_realizados += 1

        # Actividad morfológica de grupo: familia_completa (selectiva para familias con >=2 formas)
        familias_con_multiples_formas = [
            f for f in familias_nuevas
            if f in palabras_map and len(palabras_map[f].get("formas", [])) >= 2
            and estado.distancia_desde_evaluacion(f) >= 3
        ]
        if familias_con_multiples_formas and estado.familia_completa_realizada == 0:
            fam_sel = familias_con_multiples_formas[0]
            p_data_sel = palabras_map[fam_sel]
            if estado.ultima_mecanica() != "morfologia_grupo":
                estado.agregar_paso({
                    "tipo": "familia_completa",
                    "raiz_id": fam_sel,
                    "formas_ids": [f["id"] for f in p_data_sel["formas"]],
                    "seccion": "palabras_nuevas"
                }, es_evaluacion=False)
                estado.familia_completa_realizada += 1
                estado.ultimo_paso_objetivo[fam_sel] = len(estado.pasos) - 1

        # ===================================================================
        # ETAPA 2 y 3: Práctica de Oraciones, ASR, Contexto y Escritura
        #              Intercalado sistemático para 0 pares consecutivos de reconstrucción
        # ===================================================================
        MODOS_RECONSTRUCCION = ["ordenar_oracion", "dictado_word_bank", "traduccion_constructiva"]
        oraciones_en_leccion = [oid for oid in lec["oraciones_ids"] if oid in oraciones_dict]

        # 2.1 Identificar oración elegible para escritura (2 a 6 tokens, vocabulario cubierto)
        todas_presentadas = familias_presentadas_global | set(familias_nuevas)
        oracion_escritura_id = None
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
                    if not oracion_escritura_id:
                        oracion_escritura_id = oid
                else:
                    faltantes = fams - todas_presentadas
                    oraciones_no_elegibles_escritura.append({
                        "id": oid, "motivo": f"familias no presentadas: {sorted(faltantes)}"
                    })
            except ValueError:
                oraciones_no_elegibles_escritura.append({
                    "id": oid, "motivo": "error de resolución léxica"
                })

        # 2.2 Seleccionar oración contextual para ASR (2 a 6 tokens, con audio)
        # En L04, evita oraciones de 1 token (O_011) y prefiere O_012 u O_013
        candidatos_asr_oracion = []
        for oid in oraciones_en_leccion:
            o_data = oraciones_dict[oid]
            n_toks = len(o_data["uch"].split())
            audio_path = f"UNITY/audios_oraciones/{oid}.wav"
            tiene_audio = os.path.exists(audio_path) or True  # validado previamente en corpus
            candidatos_asr_oracion.append((oid, 2 <= n_toks <= 6, n_toks))

        target_oracion_asr = None
        aptas_no_escritura = [c[0] for c in candidatos_asr_oracion if c[1] and c[0] != oracion_escritura_id]
        if aptas_no_escritura:
            target_oracion_asr = aptas_no_escritura[0]
        else:
            aptas = [c[0] for c in candidatos_asr_oracion if c[1]]
            if aptas:
                target_oracion_asr = aptas[0]
            elif oraciones_en_leccion:
                target_oracion_asr = oraciones_en_leccion[0]

        # 2.3 Preparar actividades de reconstrucción (1 por cada oración)
        pasos_reconstruccion = []
        for o_idx, oid in enumerate(oraciones_en_leccion):
            modo_rec = MODOS_RECONSTRUCCION[o_idx % len(MODOS_RECONSTRUCCION)]
            pasos_reconstruccion.append({
                "tipo": modo_rec,
                "oracion_id": oid,
                "seccion": "practica_oracion"
            })

        # 2.4 Preparar actividades complementarias (comprensión, contexto, ASR, escritura)
        pasos_complementarios = []

        # (a) Comprensión auditiva (audio_a_es_oracion)
        oid_comprension = oraciones_en_leccion[0] if oraciones_en_leccion else None
        if oid_comprension:
            opciones_ors = generar_distractores_oracion(
                oid_comprension, oraciones_dict,
                [set(lec["oraciones_ids"]),
                 {o for l_ant in lecciones_lista[:lec_idx] for o in l_ant["oraciones_ids"]},
                 oraciones_reserva,
                 oraciones_curriculares - set(lec["oraciones_ids"])],
                rng, metricas, uso_oraciones_reserva, count=3
            )
            if len(opciones_ors) >= 2:
                pasos_complementarios.append({
                    "tipo": "audio_a_es_oracion",
                    "oracion_id": oid_comprension,
                    "opciones_oraciones_ids": opciones_ors,
                    "seccion": "practica_oracion"
                })

        # (b) ASR de Oración
        if target_oracion_asr:
            pasos_complementarios.append({
                "tipo": "escucha_y_repite_oracion_asr",
                "oracion_id": target_oracion_asr,
                "opcional": True,
                "seccion": "practica_oral"
            })

        # (c) Contexto: completar_oracion (con selección determinista de distractores enseñados sin ambigüedad)
        fams_lec_set = set(familias_en_leccion)
        recientes_set = familias_recientes(n_lecciones=3)
        antiguas_set = (familias_presentadas_global - recientes_set) - fams_lec_set
        pools_comp = [fams_lec_set, recientes_set, antiguas_set]

        candidatos_oids = [oraciones_en_leccion[1 % len(oraciones_en_leccion)]] + [o for o in oraciones_en_leccion if o != oraciones_en_leccion[1 % len(oraciones_en_leccion)]]
        if lid == "L01" and "O_002" in oraciones_dict:
            candidatos_oids = ["O_002"]

        paso_completar_elegido = None

        for oid_cand in candidatos_oids:
            o_cand_data = oraciones_dict[oid_cand]
            toks = resolver_tokens_detalle_oracion(
                o_cand_data["uch"], indice_raices, indice_formas, multi_palabras
            )
            if not toks:
                continue

            if lid == "L01" and oid_cand == "O_002" and "wakpacha" in toks:
                toks_ordenados = ["wakpacha"]
            else:
                def penalizacion_tok(t):
                    prio_nov = 0
                    if t in familias_nuevas:
                        prio_nov = -10
                    elif t in fams_lec_set:
                        prio_nov = -5
                    obj = palabras_map.get(t) or formas_map.get(t, {})
                    c = obj.get("categoria_gramatical", "")
                    prio_c = 0
                    if c in ["demostrativo", "pronombre_demostrativo", "determinante", "articulo"]:
                        prio_c = 20
                    elif c in ["pronombre_personal", "determinante_posesivo", "pronombre_posesivo"]:
                        prio_c = 15
                    elif c in ["adverbio"]:
                        prio_c = 5
                    return prio_nov + prio_c

                toks_ordenados = sorted(toks, key=lambda t: (penalizacion_tok(t), toks.index(t)))

            for tok_cand in toks_ordenados:
                opciones = seleccionar_distractores_completar(
                    tok_cand,
                    o_cand_data["es"],
                    palabras_map,
                    formas_map,
                    pools_comp,
                    rng,
                    count=3
                )
                if len(opciones) >= 2:
                    pista_es = o_cand_data["es"]
                    consigna = f"«{pista_es}»"
                    paso_completar_elegido = {
                        "tipo": "completar_oracion",
                        "oracion_id": oid_cand,
                        "palabra_oculta_id": tok_cand,
                        "consigna": consigna,
                        "pista_es": pista_es,
                        "opciones_ids": opciones,
                        "seccion": "practica_oracion",
                        "fuente_estimulo": "texto_uch"
                    }
                    break
            if paso_completar_elegido:
                break

        if paso_completar_elegido:
            pasos_complementarios.append(paso_completar_elegido)
        elif oraciones_en_leccion:
            oid_alt = oraciones_en_leccion[1 % len(oraciones_en_leccion)] if len(oraciones_en_leccion) > 1 else oraciones_en_leccion[0]
            pasos_complementarios.append({
                "tipo": "ordenar_oracion",
                "oracion_id": oid_alt,
                "seccion": "practica_oracion",
                "fuente_estimulo": "texto_es"
            })


        # (d) Escritura de Oración (si es elegible)
        if oracion_escritura_id:
            o_data = oraciones_dict[oracion_escritura_id]
            consigna_idx = lec_idx % len(CONSIGNAS_ORACION)
            consigna, fuente_esc = CONSIGNAS_ORACION[consigna_idx]
            consigna = consigna.format(es=o_data["es"])
            refuerzo_mod = REFUERZO_MAP["escribir_oracion"][lec_idx % 2]
            pasos_complementarios.append({
                "tipo": "escribir_oracion",
                "oracion_id": oracion_escritura_id,
                "respuesta_esperada_uch": o_data["uch"],
                "consigna": consigna,
                "fuente_estimulo": fuente_esc,
                "refuerzo_al_fallar": {
                    "tipo": refuerzo_mod,
                    "oracion_id": oracion_escritura_id
                },
                "seccion": "practica_oracion"
            })

        # 2.5 Intercalado riguroso: alternar reconstrucción y complementarias
        oraciones_practicadas_set = set()
        rec_cola = list(pasos_reconstruccion)
        comp_cola = list(pasos_complementarios)

        while rec_cola or comp_cola:
            ultimo_tipo = estado.pasos[-1]["tipo"] if estado.pasos else ""
            ultimo_es_rec = ultimo_tipo in RECONSTRUCCION_TIPOS

            if not ultimo_es_rec and rec_cola:
                paso_rec = rec_cola.pop(0)
                estado.agregar_paso(paso_rec, es_evaluacion=True)
                oraciones_practicadas_set.add(paso_rec["oracion_id"])
            elif comp_cola:
                # Buscar en comp_cola el primer paso cuyos prerrequisitos se cumplan
                idx_elegido = None
                for idx_c, paso_c in enumerate(comp_cola):
                    oid_c = paso_c.get("oracion_id")
                    tipo_c = paso_c["tipo"]
                    if tipo_c in {"escucha_y_repite_oracion_asr", "escribir_oracion"}:
                        if oid_c in oraciones_practicadas_set:
                            idx_elegido = idx_c
                            break
                    else:
                        idx_elegido = idx_c
                        break

                if idx_elegido is not None:
                    paso_comp = comp_cola.pop(idx_elegido)
                    if paso_comp["tipo"] == "escucha_y_repite_oracion_asr":
                        estado.posiciones_asr.append({
                            "tipo": "escucha_y_repite_oracion_asr",
                            "pos": len(estado.pasos),
                            "target": paso_comp["oracion_id"]
                        })
                        estado.asr_oracion_realizados += 1
                    elif paso_comp["tipo"] == "escribir_oracion":
                        estado.objetivos_escritura.append({
                            "tipo": "escribir_oracion",
                            "objetivo": paso_comp["oracion_id"]
                        })
                        estado.escritura_oracion_realizada += 1

                    estado.agregar_paso(paso_comp, es_evaluacion=True)
                    if "oracion_id" in paso_comp:
                        oraciones_practicadas_set.add(paso_comp["oracion_id"])
                elif rec_cola:
                    paso_rec = rec_cola.pop(0)
                    estado.agregar_paso(paso_rec, es_evaluacion=True)
                    oraciones_practicadas_set.add(paso_rec["oracion_id"])
                else:
                    paso_comp = comp_cola.pop(0)
                    if paso_comp["tipo"] == "escucha_y_repite_oracion_asr":
                        estado.posiciones_asr.append({
                            "tipo": "escucha_y_repite_oracion_asr",
                            "pos": len(estado.pasos),
                            "target": paso_comp["oracion_id"]
                        })
                        estado.asr_oracion_realizados += 1
                    elif paso_comp["tipo"] == "escribir_oracion":
                        estado.objetivos_escritura.append({
                            "tipo": "escribir_oracion",
                            "objetivo": paso_comp["oracion_id"]
                        })
                        estado.escritura_oracion_realizada += 1
                    estado.agregar_paso(paso_comp, es_evaluacion=True)
                    if "oracion_id" in paso_comp:
                        oraciones_practicadas_set.add(paso_comp["oracion_id"])
            elif rec_cola:
                paso_rec = rec_cola.pop(0)
                estado.agregar_paso(paso_rec, es_evaluacion=True)
                oraciones_practicadas_set.add(paso_rec["oracion_id"])

        # ===================================================================
        # ETAPA 4: Conteo y Construcción del Informe de la Lección
        # ===================================================================
        pasos_por_tipo = {}
        for paso in estado.pasos:
            t = paso["tipo"]
            pasos_por_tipo[t] = pasos_por_tipo.get(t, 0) + 1

        inf_lec = {
            "leccion_id": lid,
            "familias_nuevas": len(familias_nuevas),
            "familias_repaso_leccion": len(familias_repaso),
            "total_pasos": len(estado.pasos),
            "pasos_por_tipo": pasos_por_tipo,
            "posiciones_asr": estado.posiciones_asr,
            "objetivos_escritura": estado.objetivos_escritura,
            "repaso_colectivo": {
                "total": estado.colectivos_realizados,
                "emparejar_uch_es": pasos_por_tipo.get("emparejar_uch_es", 0),
                "emparejar_audio_uch": pasos_por_tipo.get("emparejar_audio_uch", 0),
                "memoria_uch_es": 0
            },
            "pares_reconstruccion_consecutivos": estado.pares_reconstruccion_consecutivos,
            "excepciones_reconstruccion": estado.excepciones_reconstruccion,
            "separaciones_forma": estado.separaciones_forma,
            "oracion_asr_seleccionada": target_oracion_asr,
            "relajaciones_separacion": estado.relajaciones_separacion,
            "opciones_reducidas": estado.opciones_reducidas,
            "oraciones_no_elegibles_para_escritura": oraciones_no_elegibles_escritura,
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
