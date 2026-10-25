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


def evaluar_idoneidad_refuerzo(fid: str, p_info: dict, audio_files: set, lexicon_words: set) -> dict:
    """
    Evalúa la idoneidad lingüística y técnica de una familia nueva para su refuerzo:
    - Escritura (escribir_palabra o escribir_forma): prioriza morfología flexionada, diacríticos,
      caracteres especiales, consonantes aspiradas/uvulares/africadas complejas y palabras incompatibles con ASR.
    - ASR (escucha_y_repite_asr): prioriza palabras con audio verificado y compatibilidad estricta
      con el inventario y tokens del modelo de reconocimiento de voz.
    """
    uch = p_info.get("uch", "")
    uch_lower = uch.lower()

    # Verificación dura ASR: archivo de audio existente y palabra/token en lexicon ASR
    tiene_audio = (fid in audio_files) or (f"{fid}.wav" in audio_files)
    en_lexicon = (uch_lower in lexicon_words) or (fid in lexicon_words)

    if not tiene_audio or not en_lexicon:
        return {
            "fid": fid,
            "uch": uch,
            "apto_asr": False,
            "score_escritura": 999,
            "motivos": ["incompatible_asr"]
        }

    score = 0
    motivos = []

    # 1. Formas morfológicas documentadas (alta prioridad para escribir_forma)
    formas = p_info.get("formas", [])
    if formas:
        score += 5
        motivos.append(f"formas_morfológicas({len(formas)})")

    # 2. Caracteres especiales y diacríticos (ï, ü, ä, ö, ë, ñ, apostrofe, ejectivas)
    diacriticos = [c for c in ["ï", "ü", "ä", "ö", "ë", "ñ", "'", "’", "ʼ"] if c in uch_lower]
    if diacriticos:
        score += 6
        motivos.append(f"diacriticos({','.join(diacriticos)})")

    # 3. Consonantes aspiradas del uchumataqu (chh, kh, ph, th, qh)
    if "chh" in uch_lower:
        score += 4
        motivos.append("aspirada_chh")
    elif any(d in uch_lower for d in ["kh", "ph", "th", "qh"]):
        score += 3
        motivos.append("aspirada")

    # 4. Consonantes africadas y velares/uvulares complejas (ts, sh, ll, q, x)
    if any(d in uch_lower for d in ["ts", "sh"]):
        score += 2
        motivos.append("africada_fricativa")
    if "q" in uch_lower or "x" in uch_lower:
        score += 3
        motivos.append("uvular_x_q")
    if "ll" in uch_lower:
        score += 1
        motivos.append("lateral_ll")

    # 5. Grupos consonánticos (e.g. kch, ks, xt, sk, rch, etc.)
    if re.search(r"[kstxrp][kstxrp]", uch_lower):
        score += 2
        motivos.append("grupo_consonantico")

    # 6. Longitud y complejidad estructural
    if len(uch) >= 8:
        score += 1
        motivos.append("longitud_mayor")

    return {
        "fid": fid,
        "uch": uch,
        "apto_asr": True,
        "score_escritura": score,
        "motivos": motivos
    }


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

    # Cargar recursos para validación estricta de compatibilidad ASR
    proyecto_raiz = os.path.abspath(os.path.join(_pkg_dir, "..", "..", ".."))
    ruta_lexicon = os.path.join(proyecto_raiz, "ASR", "datos_asr", "lexicon.txt")
    ruta_audios_pal = os.path.join(proyecto_raiz, "UNITY", "audios_palabras")

    lexicon_words = set()
    if os.path.exists(ruta_lexicon):
        with open(ruta_lexicon, "r", encoding="utf-8") as f_lex:
            for linea in f_lex:
                linea = linea.strip()
                if "\t" in linea:
                    lexicon_words.add(linea.split("\t")[0].strip())

    audio_files_set = set()
    if os.path.exists(ruta_audios_pal):
        audio_files_set = {
            os.path.splitext(f)[0] for f in os.listdir(ruta_audios_pal)
            if f.endswith(".wav") or f.endswith(".mp3") or f.endswith(".ogg")
        }

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
        mitad = (n_nuevas + 1) // 2
        fams_a = familias_nuevas[:mitad]
        fams_b = familias_nuevas[mitad:]

        # ===================================================================
        # BLOQUE A: Aprendizaje y Refuerzo (Mitad A)
        # ===================================================================
        # 1. Presentaciones y microactividades individuales inmediatas
        audio_forma_en_a = 0
        for fn_idx, fid in enumerate(fams_a):
            if fid not in palabras_map:
                continue
            p_data = palabras_map[fid]
            estado.familias_presentadas.add(fid)
            tiene_formas = "formas" in p_data and len(p_data["formas"]) > 0

            estado.agregar_paso({
                "tipo": "presentacion_familia",
                "objetivo_id": fid,
                "tiene_formas": tiene_formas,
                "seccion": "palabras_nuevas",
                "fuente_estimulo": "audio"
            }, es_evaluacion=False)

            usar_audio_forma = tiene_formas and (audio_forma_en_a == 0) and (fn_idx % 2 == 1)
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
                    audio_forma_en_a += 1
                    estado.audio_forma_realizados += 1
                    emitio_micro = True

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

        # 2. Emparejamiento 1 (Bloque A)
        rng_emp1 = random.Random(obtener_semilla_estable(lid, "emparejamiento_1"))
        cands_emp1 = list(fams_a)
        rng_emp1.shuffle(cands_emp1)
        sel_emp1 = items_validos_emparejamiento(cands_emp1, palabras_map, max_items=5)
        if len(sel_emp1) < 5 and familias_presentadas_global:
            cands_prev_fuera = sorted(list(familias_presentadas_global - set(familias_en_leccion) - set(sel_emp1)))
            rng_emp1.shuffle(cands_prev_fuera)
            cands_totales_1 = sel_emp1 + cands_prev_fuera
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

        # 3. Refuerzos Bloque A (Selección inteligente y distribución equilibrada)
        evals_a = [evaluar_idoneidad_refuerzo(f, palabras_map[f], audio_files_set, lexicon_words) for f in fams_a if f in palabras_map]
        incompatibles_asr_a = [e for e in evals_a if not e["apto_asr"]]
        compatibles_asr_a = [e for e in evals_a if e["apto_asr"]]
        compatibles_asr_a.sort(key=lambda x: x["score_escritura"], reverse=True)

        k_a = len(evals_a)
        target_esc_a = max(len(incompatibles_asr_a), k_a // 2)
        num_comp_esc_a = target_esc_a - len(incompatibles_asr_a)
        sel_esc_a = incompatibles_asr_a + compatibles_asr_a[:num_comp_esc_a]
        sel_asr_a = compatibles_asr_a[num_comp_esc_a:]

        steps_esc_a = []
        for e in sel_esc_a:
            fid_e = e["fid"]
            p_data = palabras_map[fid_e]
            formas = p_data.get("formas", [])
            frm_disponible = None
            for frm in formas:
                if frm["id"] not in estado.escrituras_usadas_ids and normalizar_texto(frm["uch"]) not in estado.escrituras_usadas_uch_norm:
                    frm_disponible = frm
                    break

            if frm_disponible is not None:
                consigna_idx = estado.escrituras_formas_realizadas % len(CONSIGNAS_FORMA)
                consigna_tmpl, fuente_esc = CONSIGNAS_FORMA[consigna_idx]
                consigna = consigna_tmpl.format(es=limpiar_texto_consigna(frm_disponible["es"]))
                refuerzo_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_formas_realizadas % len(REFUERZO_MAP["escribir_forma"])]
                steps_esc_a.append({
                    "tipo": "escribir_forma",
                    "forma_id": frm_disponible["id"],
                    "raiz_id": fid_e,
                    "respuesta_esperada_uch": frm_disponible["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "forma_id": frm_disponible["id"],
                        "raiz_id": fid_e
                    },
                    "seccion": "palabras_nuevas"
                })
                estado.escrituras_formas_realizadas += 1
            else:
                consigna_idx = estado.escrituras_palabras_realizadas % len(CONSIGNAS_PALABRA)
                consigna_tmpl, fuente_esc = CONSIGNAS_PALABRA[consigna_idx]
                consigna = consigna_tmpl.format(es=limpiar_texto_consigna(p_data["es"]))
                refuerzo_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_palabras_realizadas % len(REFUERZO_MAP["escribir_palabra"])]
                steps_esc_a.append({
                    "tipo": "escribir_palabra",
                    "objetivo_id": fid_e,
                    "respuesta_esperada_uch": p_data["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "objetivo_id": fid_e
                    },
                    "seccion": "palabras_nuevas"
                })
                estado.escrituras_palabras_realizadas += 1
                palabras_escritas_global.add(fid_e)

        steps_asr_a = []
        for e in sel_asr_a:
            steps_asr_a.append({
                "tipo": "escucha_y_repite_asr",
                "objetivo_id": e["fid"],
                "opcional": True,
                "seccion": "practica_oral",
                "fuente_estimulo": "audio"
            })
            estado.asr_lexico_realizados += 1

        refuerzos_a = []
        idx_e, idx_a = 0, 0
        empieza_con_esc = len(steps_esc_a) >= len(steps_asr_a)
        while idx_e < len(steps_esc_a) or idx_a < len(steps_asr_a):
            if empieza_con_esc:
                if idx_e < len(steps_esc_a):
                    refuerzos_a.append(steps_esc_a[idx_e])
                    idx_e += 1
                if idx_a < len(steps_asr_a):
                    refuerzos_a.append(steps_asr_a[idx_a])
                    idx_a += 1
            else:
                if idx_a < len(steps_asr_a):
                    refuerzos_a.append(steps_asr_a[idx_a])
                    idx_a += 1
                if idx_e < len(steps_esc_a):
                    refuerzos_a.append(steps_esc_a[idx_e])
                    idx_e += 1

        for paso_ref in refuerzos_a:
            estado.agregar_paso(paso_ref, es_evaluacion=True)

        # ===================================================================
        # BLOQUE B: Aprendizaje y Refuerzo (Mitad B)
        # ===================================================================
        # 1. Presentaciones y microactividades individuales inmediatas
        audio_forma_en_b = 0
        for fn_idx, fid in enumerate(fams_b):
            if fid not in palabras_map:
                continue
            p_data = palabras_map[fid]
            estado.familias_presentadas.add(fid)
            tiene_formas = "formas" in p_data and len(p_data["formas"]) > 0

            estado.agregar_paso({
                "tipo": "presentacion_familia",
                "objetivo_id": fid,
                "tiene_formas": tiene_formas,
                "seccion": "palabras_nuevas",
                "fuente_estimulo": "audio"
            }, es_evaluacion=False)

            usar_audio_forma = tiene_formas and (audio_forma_en_b == 0) and (fn_idx % 2 == 1)
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
                    audio_forma_en_b += 1
                    estado.audio_forma_realizados += 1
                    emitio_micro = True

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

        # 2. Emparejamiento 2 (Bloque B)
        rng_emp2 = random.Random(obtener_semilla_estable(lid, "emparejamiento_2"))
        items_emp1_set = set(sel_emp1)
        nuevas_restantes = [f for f in fams_b if f not in items_emp1_set]
        rng_emp2.shuffle(nuevas_restantes)
        repaso_leccion = [f for f in familias_repaso if f not in items_emp1_set]
        rng_emp2.shuffle(repaso_leccion)

        pool_emp2 = nuevas_restantes + repaso_leccion
        sel_emp2 = items_validos_emparejamiento(pool_emp2, palabras_map, max_items=5)
        if len(sel_emp2) < 2:
            reutilizables = [f for f in fams_b if f in items_emp1_set]
            sel_emp2 = items_validos_emparejamiento(pool_emp2 + reutilizables, palabras_map, max_items=5)

        if len(sel_emp2) >= 2:
            estado.agregar_paso({
                "tipo": "emparejar_uch_es",
                "items_ids": sorted(sel_emp2),
                "seccion": "palabras_nuevas",
                "fuente_estimulo": "texto_uch"
            }, es_evaluacion=False)
            estado.emparejar_realizados += 1

        # 3. Refuerzos Bloque B (Selección inteligente y distribución equilibrada)
        evals_b = [evaluar_idoneidad_refuerzo(f, palabras_map[f], audio_files_set, lexicon_words) for f in fams_b if f in palabras_map]
        incompatibles_asr_b = [e for e in evals_b if not e["apto_asr"]]
        compatibles_asr_b = [e for e in evals_b if e["apto_asr"]]
        compatibles_asr_b.sort(key=lambda x: x["score_escritura"], reverse=True)

        k_b = len(evals_b)
        target_esc_b = max(len(incompatibles_asr_b), k_b // 2)
        num_comp_esc_b = target_esc_b - len(incompatibles_asr_b)
        sel_esc_b = incompatibles_asr_b + compatibles_asr_b[:num_comp_esc_b]
        sel_asr_b = compatibles_asr_b[num_comp_esc_b:]

        steps_esc_b = []
        for e in sel_esc_b:
            fid_e = e["fid"]
            p_data = palabras_map[fid_e]
            formas = p_data.get("formas", [])
            frm_disponible = None
            for frm in formas:
                if frm["id"] not in estado.escrituras_usadas_ids and normalizar_texto(frm["uch"]) not in estado.escrituras_usadas_uch_norm:
                    frm_disponible = frm
                    break

            if frm_disponible is not None:
                consigna_idx = estado.escrituras_formas_realizadas % len(CONSIGNAS_FORMA)
                consigna_tmpl, fuente_esc = CONSIGNAS_FORMA[consigna_idx]
                consigna = consigna_tmpl.format(es=limpiar_texto_consigna(frm_disponible["es"]))
                refuerzo_mod = REFUERZO_MAP["escribir_forma"][estado.escrituras_formas_realizadas % len(REFUERZO_MAP["escribir_forma"])]
                steps_esc_b.append({
                    "tipo": "escribir_forma",
                    "forma_id": frm_disponible["id"],
                    "raiz_id": fid_e,
                    "respuesta_esperada_uch": frm_disponible["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "forma_id": frm_disponible["id"],
                        "raiz_id": fid_e
                    },
                    "seccion": "palabras_nuevas"
                })
                estado.escrituras_formas_realizadas += 1
            else:
                consigna_idx = estado.escrituras_palabras_realizadas % len(CONSIGNAS_PALABRA)
                consigna_tmpl, fuente_esc = CONSIGNAS_PALABRA[consigna_idx]
                consigna = consigna_tmpl.format(es=limpiar_texto_consigna(p_data["es"]))
                refuerzo_mod = REFUERZO_MAP["escribir_palabra"][estado.escrituras_palabras_realizadas % len(REFUERZO_MAP["escribir_palabra"])]
                steps_esc_b.append({
                    "tipo": "escribir_palabra",
                    "objetivo_id": fid_e,
                    "respuesta_esperada_uch": p_data["uch"],
                    "consigna": consigna,
                    "fuente_estimulo": fuente_esc,
                    "refuerzo_al_fallar": {
                        "tipo": refuerzo_mod,
                        "objetivo_id": fid_e
                    },
                    "seccion": "palabras_nuevas"
                })
                estado.escrituras_palabras_realizadas += 1
                palabras_escritas_global.add(fid_e)

        steps_asr_b = []
        for e in sel_asr_b:
            steps_asr_b.append({
                "tipo": "escucha_y_repite_asr",
                "objetivo_id": e["fid"],
                "opcional": True,
                "seccion": "practica_oral",
                "fuente_estimulo": "audio"
            })
            estado.asr_lexico_realizados += 1

        refuerzos_b = []
        idx_e, idx_a = 0, 0
        empieza_con_esc = len(steps_esc_b) >= len(steps_asr_b)
        while idx_e < len(steps_esc_b) or idx_a < len(steps_asr_b):
            if empieza_con_esc:
                if idx_e < len(steps_esc_b):
                    refuerzos_b.append(steps_esc_b[idx_e])
                    idx_e += 1
                if idx_a < len(steps_asr_b):
                    refuerzos_b.append(steps_asr_b[idx_a])
                    idx_a += 1
            else:
                if idx_a < len(steps_asr_b):
                    refuerzos_b.append(steps_asr_b[idx_a])
                    idx_a += 1
                if idx_e < len(steps_esc_b):
                    refuerzos_b.append(steps_esc_b[idx_e])
                    idx_e += 1

        for paso_ref in refuerzos_b:
            estado.agregar_paso(paso_ref, es_evaluacion=True)

        # ===================================================================
        # BLOQUE FINAL: Práctica de Oraciones (Construcción, Escritura y ASR)
        # ===================================================================
        oraciones_en_leccion = [oid for oid in lec["oraciones_ids"] if oid in oraciones_dict]
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
            oraciones_elegibles_escritura.append(oid)

        rng_oraciones = random.Random(obtener_semilla_estable(lid, "oraciones_escritura"))
        cands_esc_oraciones = list(oraciones_elegibles_escritura)
        rng_oraciones.shuffle(cands_esc_oraciones)

        oid_traduccion = cands_esc_oraciones[0] if len(cands_esc_oraciones) >= 1 else None
        oid_dictado = cands_esc_oraciones[1] if len(cands_esc_oraciones) >= 2 else (
            cands_esc_oraciones[0] if len(cands_esc_oraciones) >= 1 else None
        )

        cands_oracion_asr = [oid for oid in oraciones_en_leccion if oid not in [oid_traduccion, oid_dictado]]
        if not cands_oracion_asr and oraciones_en_leccion:
            cands_oracion_asr = list(oraciones_en_leccion)
        target_oracion_asr = cands_oracion_asr[0] if cands_oracion_asr else None

        rec_cola = [oid for oid in oraciones_en_leccion if len(oraciones_dict[oid]["uch"].split()) >= 2]
        oraciones_descartadas_ordenar = [oid for oid in oraciones_en_leccion if len(oraciones_dict[oid]["uch"].split()) < 2]

        # 1. Pasos de reconstrucción de oraciones
        ord_steps = []
        for oid in rec_cola:
            ord_steps.append({
                "tipo": "ordenar_oracion",
                "oracion_id": oid,
                "seccion": "practica_oracion",
                "fuente_estimulo": "texto_es"
            })

        # 2. Pasos de escritura y ASR de oraciones para intercalar
        # Estructura de intercalación: traducción escrita -> ASR oral -> dictado escrito
        # garantizando que nunca haya dos escrituras consecutivas
        inter_steps = []
        if oid_traduccion:
            o_data = oraciones_dict[oid_traduccion]
            inter_steps.append({
                "tipo": "escribir_oracion",
                "oracion_id": oid_traduccion,
                "respuesta_esperada_uch": o_data["uch"],
                "consigna": CONSIGNAS_ORACION_TRADUCCION.format(es=o_data["es"]),
                "fuente_estimulo": "texto_es",
                "refuerzo_al_fallar": {
                    "tipo": REFUERZO_MAP["escribir_oracion"][0],
                    "oracion_id": oid_traduccion
                },
                "seccion": "practica_oracion"
            })
            estado.escrituras_oraciones_realizadas += 1

        if target_oracion_asr:
            inter_steps.append({
                "tipo": "escucha_y_repite_oracion_asr",
                "oracion_id": target_oracion_asr,
                "opcional": True,
                "seccion": "practica_oral",
                "fuente_estimulo": "audio"
            })
            estado.asr_oracion_realizados += 1

        if oid_dictado and oid_dictado != oid_traduccion:
            o_data = oraciones_dict[oid_dictado]
            inter_steps.append({
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
            estado.escrituras_oraciones_realizadas += 1

        # 3. Intercalación balanceada:
        # Alterna ordenar_oracion con los pasos de inter_steps (escritura y ASR)
        # evitando agrupar varios ejercicios ordenar_oracion consecutivos
        steps_oraciones = []
        idx_ord = 0
        idx_inter = 0
        while idx_ord < len(ord_steps) or idx_inter < len(inter_steps):
            if idx_ord < len(ord_steps):
                steps_oraciones.append(ord_steps[idx_ord])
                idx_ord += 1
            if idx_inter < len(inter_steps):
                steps_oraciones.append(inter_steps[idx_inter])
                idx_inter += 1

        for paso_o in steps_oraciones:
            estado.agregar_paso(paso_o, es_evaluacion=True)

        # Actualizar posiciones ASR
        posiciones_asr_organizadas = []
        for idx_p, p in enumerate(estado.pasos):
            t_p = p["tipo"]
            if t_p in ["escucha_y_repite_asr", "escucha_y_repite_oracion_asr"]:
                target_p = p.get("objetivo_id") or p.get("oracion_id")
                posiciones_asr_organizadas.append({
                    "tipo": t_p, "pos": idx_p, "target": target_p
                })
        estado.posiciones_asr = posiciones_asr_organizadas
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

        pares_rec = sum(
            1 for idx_rec in range(len(estado.pasos) - 1)
            if estado.pasos[idx_rec]["tipo"] == "ordenar_oracion" and estado.pasos[idx_rec + 1]["tipo"] == "ordenar_oracion"
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
            "pares_reconstruccion_consecutivos": pares_rec,
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
