"""
distractores_corpus.py
Módulo de resolución léxica y generación de distractores no ambiguos para Uchumataqu.
Basado en:
  - 01-modulo-pln-texto.md (Sección 5, 6 y 10.5)
  - 05-guia-corpus-datos.md (Sección 2.7, 9 y 12)
  - instrucciones-mejora-compilador-lecciones.md (Sección 7)
"""

import re
import random
import unicodedata

# ---------------------------------------------------------------------------
# Normalización canónica de apóstrofe y texto
# ---------------------------------------------------------------------------
_APOSTROFES_NO_CANONICOS = "'`´\u2018\u2019\u02b9"  # excluye U+02BC (ʼ)

def normalizar_apostrofe(texto: str) -> str:
    """Normaliza todas las variantes de apóstrofe al estándar U+02BC (ʼ)."""
    if not texto:
        return ""
    for a in _APOSTROFES_NO_CANONICOS:
        texto = texto.replace(a, "\u02bc")
    return texto

def normalizar_texto(texto: str) -> str:
    """Normaliza texto para búsquedas deterministas respetando grafías nativas."""
    if not texto:
        return ""
    texto = normalizar_apostrofe(texto)
    texto = texto.strip().lower()
    texto = re.sub(r"[¿?!¡.,;:\"()_]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto

def normalizar_lid(raw: str) -> str:
    """Normaliza cualquier L<n> a L con 2 dígitos: L01…L27."""
    num = re.sub(r"\D", "", raw.strip())
    return f"L{int(num):02d}" if num else raw.strip()

# ---------------------------------------------------------------------------
# Nombres Propios Contextuales Permitidos (01-modulo-pln-texto.md, Sec 5.3)
# ---------------------------------------------------------------------------
NOMBRES_PROPIOS_CONTEXTUALES = {
    "pedro",
    "lorenzo",
    "maria",
    "maría",
    "juana",
    "waki",
    "irohito urus",
    "irohito",
}

# ---------------------------------------------------------------------------
# Manejo de Traducciones con Alternancias ("/")
# ---------------------------------------------------------------------------
def desglosar_traducciones(es_texto: str) -> list:
    """
    Desglosa traducciones con alternativas separadas por barra (ej: 'Es/está grande').
    Retorna una lista de variantes limpias y completas en español.
    """
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
            v1 = f"{partes[0]} {complemento}".strip()
            v2 = partes[1].strip()
            return [v1, v2]
        elif len(p1_tokens) > 1 and len(p2_tokens) == 1:
            base = " ".join(p1_tokens[1:])
            v1 = partes[0].strip()
            v2 = f"{partes[1]} {base}".strip()
            return [v1, v2]

    return [p for p in partes if p]

def seleccionar_traduccion_variante(es_texto: str, rng: random.Random) -> str:
    """Selecciona determinísticamente una sola variante natural para un ejercicio."""
    variantes = desglosar_traducciones(es_texto)
    if len(variantes) == 1:
        return variantes[0]
    idx = rng.randint(0, len(variantes) - 1)
    return variantes[idx]

def son_traducciones_compatibles(es_a: str, es_b: str) -> bool:
    """
    Comprueba si dos textos de traducción comparten significado o variantes alternativas.
    Retorna True si son incompatibles como distractor (es decir, significan lo mismo o se traslapan).
    """
    vars_a = set(v.lower().strip() for v in desglosar_traducciones(es_a))
    vars_b = set(v.lower().strip() for v in desglosar_traducciones(es_b))
    return len(vars_a & vars_b) > 0

# ---------------------------------------------------------------------------
# Resolución Léxica Determinista (01-modulo-pln-texto.md, Sec 5.1)
# ---------------------------------------------------------------------------
def resolver_familias_en_oracion(oracion_uch: str, indice_raices: dict, indice_formas: dict, multi_palabras: list) -> set:
    """
    Aplica longest-match para resolver todas las familias léxicas presentes en una oración.
    Retorna un conjunto con los IDs de las familias (raíces) detectadas.
    Los nombres propios contextuales permitidos se aceptan sin generar familia_id.
    Falla si algún token no puede resolverse y no es un nombre propio permitido.
    """
    uch_norm = normalizar_texto(oracion_uch)
    familias_encontradas = set()

    # 1. Unidades pedagógicas multi-palabra de palabras.json
    for frase, familia_id in multi_palabras:
        if frase in uch_norm:
            familias_encontradas.add(familia_id)
            uch_norm = uch_norm.replace(frase, " ")

    # 2. Nombres propios contextuales multi-palabra (ej: 'irohito urus')
    for np in sorted([n for n in NOMBRES_PROPIOS_CONTEXTUALES if " " in n], key=len, reverse=True):
        if np in uch_norm:
            uch_norm = uch_norm.replace(np, " ")

    # 3. Tokens individuales
    tokens = uch_norm.split()
    for tok in tokens:
        if tok in indice_raices:
            familias_encontradas.add(indice_raices[tok])
        elif tok in indice_formas:
            familias_encontradas.add(indice_formas[tok]["familia_id"])
        elif tok in NOMBRES_PROPIOS_CONTEXTUALES:
            # Token contextual permitido: no devuelve familia_id
            continue
        else:
            raise ValueError(
                f"Error de resolución léxica (01-modulo-pln-texto.md, Sec 5.1): "
                f"El token '{tok}' en la oración '{oracion_uch}' no es raíz, forma, "
                f"ni nombre propio contextual permitido."
            )

    return familias_encontradas

def resolver_tokens_detalle_oracion(oracion_uch: str, indice_raices: dict, indice_formas: dict, multi_palabras: list) -> list:
    """
    Resuelve los elementos léxicos específicos de una oración (palabras/formas)
    con sus IDs correspondientes para actividades de completar oración.
    Excluye nombres propios contextuales para que nunca sean seleccionados como palabra oculta.
    """
    uch_norm = normalizar_texto(oracion_uch)
    tokens_resueltos = []

    # 1. Unidades pedagógicas multi-palabra
    for frase, familia_id in multi_palabras:
        if frase in uch_norm:
            tokens_resueltos.append(familia_id)
            uch_norm = uch_norm.replace(frase, " ")

    # 2. Nombres propios multi-palabra (se omiten de los evaluables)
    for np in sorted([n for n in NOMBRES_PROPIOS_CONTEXTUALES if " " in n], key=len, reverse=True):
        if np in uch_norm:
            uch_norm = uch_norm.replace(np, " ")

    # 3. Tokens individuales
    tokens = uch_norm.split()
    for tok in tokens:
        if tok in indice_raices:
            tokens_resueltos.append(indice_raices[tok])
        elif tok in indice_formas:
            f_val = indice_formas[tok]
            f_id = f_val["forma_id"] if isinstance(f_val, dict) else f_val
            tokens_resueltos.append(f_id)
        elif tok in NOMBRES_PROPIOS_CONTEXTUALES:
            continue
        else:
            raise ValueError(
                f"Error de resolución léxica en detalle de oración: "
                f"El token '{tok}' en la oración '{oracion_uch}' no pertenece a palabras.json "
                f"ni al conjunto cerrado de nombres propios."
            )

    return tokens_resueltos

# ---------------------------------------------------------------------------
# Selección de Distractores por Prioridad (P1 a P4)
# ---------------------------------------------------------------------------
def seleccionar_distractores_por_prioridad(
    objetivo_id: str,
    items_map: dict,
    pools_prioridad: list,
    rng: random.Random,
    metricas: dict,
    tipo: str,
    count: int = 3
) -> list:
    """
    Selecciona distractores sin ambigüedad gramatical ni semántica respetando el orden P1..P4.
    Excluye nombres propios, duplicados y equivalencias de traducción.
    Pase 1: Prioriza la misma categoría gramatical.
    Pase 2: Si no hay suficientes distractores (categoría única/escasa), relaja la categoría
            para asegurar al menos 2-4 opciones totales y evitar preguntas de 1 sola opción.
    """
    objetivo = items_map[objetivo_id]
    seleccionados = []

    # Pase 1: Misma categoría gramatical
    for prioridad, pool in enumerate(pools_prioridad, start=1):
        candidatos = [
            item_id for item_id in sorted(set(pool))
            if item_id != objetivo_id
            and item_id not in seleccionados
            and item_id in items_map
            and item_id.lower() not in NOMBRES_PROPIOS_CONTEXTUALES
            and items_map[item_id].get("categoria_gramatical") == objetivo.get("categoria_gramatical")
            and not son_traducciones_compatibles(objetivo["es"], items_map[item_id]["es"])
        ]
        faltan = count - len(seleccionados)
        if faltan <= 0:
            break
        elegidos = rng.sample(candidatos, min(faltan, len(candidatos)))
        seleccionados.extend(elegidos)
        if metricas and tipo in metricas:
            metricas[tipo][f"P{prioridad}"] += len(elegidos)

    # Pase 2: Categoría relajada si faltan opciones
    if len(seleccionados) < count:
        for prioridad, pool in enumerate(pools_prioridad, start=1):
            candidatos = [
                item_id for item_id in sorted(set(pool))
                if item_id != objetivo_id
                and item_id not in seleccionados
                and item_id in items_map
                and item_id.lower() not in NOMBRES_PROPIOS_CONTEXTUALES
                and not son_traducciones_compatibles(objetivo["es"], items_map[item_id]["es"])
            ]
            faltan = count - len(seleccionados)
            if faltan <= 0:
                break
            elegidos = rng.sample(candidatos, min(faltan, len(candidatos)))
            seleccionados.extend(elegidos)
            if metricas and tipo in metricas:
                metricas[tipo][f"P{prioridad}"] += len(elegidos)

    # Retorna lista ordenada canónicamente con la respuesta correcta incluida
    return sorted([objetivo_id] + seleccionados)

def generar_distractores_oracion(
    objetivo_oid: str,
    oraciones_dict: dict,
    pools_prioridad: list,
    rng: random.Random,
    metricas: dict,
    uso_global: dict = None,
    count: int = 3
) -> list:
    """
    Selecciona distractores de oración en las cuatro prioridades curriculares.
    Para P3 (reserva), ordena por menor uso acumulado para equilibrar la exposición de reserva.
    """
    if uso_global is None:
        uso_global = {}
    seleccionados = []

    for prioridad, pool in enumerate(pools_prioridad, start=1):
        candidatos = [
            oid for oid in sorted(set(pool))
            if oid != objetivo_oid
            and oid not in seleccionados
            and oid in oraciones_dict
            and not son_traducciones_compatibles(oraciones_dict[objetivo_oid]["es"], oraciones_dict[oid]["es"])
        ]
        faltan = count - len(seleccionados)
        if faltan <= 0:
            break

        if prioridad == 3:
            candidatos.sort(key=lambda x: (uso_global.get(x, 0), x))
            elegidos = candidatos[:min(faltan, len(candidatos))]
        else:
            elegidos = rng.sample(candidatos, min(faltan, len(candidatos)))

        for e in elegidos:
            uso_global[e] = uso_global.get(e, 0) + 1

        seleccionados.extend(elegidos)
        if metricas and "oraciones" in metricas:
            metricas["oraciones"][f"P{prioridad}"] += len(elegidos)

    return sorted([objetivo_oid] + seleccionados)


# ---------------------------------------------------------------------------
# Selección Especializada de Distractores para completar_oracion
# ---------------------------------------------------------------------------
STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
    "en", "con", "por", "para", "es", "está", "están", "son", "y", "o", "que", "muy",
    "su", "sus", "mi", "mis", "tu", "tus", "nuestro", "nuestra", "nuestros", "nuestras"
}

def obtener_palabras_significativas_es(texto_es: str) -> set:
    """Extrae palabras de contenido en español ignorando palabras funcionales / stopwords."""
    palabras = re.findall(r"\w+", (texto_es or "").lower())
    return {p for p in palabras if p not in STOPWORDS_ES and len(p) > 1}

def seleccionar_distractores_completar(
    objetivo_id: str,
    oracion_es: str,
    palabras_map: dict,
    formas_map: dict,
    pools_prioridad: list,
    rng: random.Random,
    count: int = 3
) -> list:
    """
    Selecciona distractores inequívocos para completar_oracion:
    - Exclusivamente vocabulario enseñado (misma lección, recientes o repaso).
    - Ninguna opción comparte significado o palabras con la traducción en español mostrada.
    - Excluye nombres propios contextuales y alternativas compatibles.
    - Asegura entre 2 y 4 opciones totales ([objetivo_id] + 1..3 distractores).
    """
    es_sig = obtener_palabras_significativas_es(oracion_es)
    t_obj = palabras_map.get(objetivo_id) or formas_map.get(objetivo_id)
    cat = t_obj.get("categoria_gramatical") if t_obj else None

    items_lookup = {}
    items_lookup.update(palabras_map)
    items_lookup.update(formas_map)

    seleccionados = []

    # Pase 1: Misma categoría gramatical
    for pool in pools_prioridad:
        cands = []
        for v in sorted(set(pool)):
            if v == objetivo_id or v in seleccionados:
                continue
            if v.lower() in NOMBRES_PROPIOS_CONTEXTUALES:
                continue
            v_obj = items_lookup.get(v)
            if not v_obj:
                continue
            v_es_sig = obtener_palabras_significativas_es(v_obj.get("es", ""))
            if v_es_sig & es_sig:
                continue
            if son_traducciones_compatibles(oracion_es, v_obj.get("es", "")):
                continue
            if cat and v_obj.get("categoria_gramatical") == cat:
                cands.append(v)
        faltan = count - len(seleccionados)
        if faltan <= 0:
            break
        if cands:
            elegidos = rng.sample(cands, min(faltan, len(cands)))
            seleccionados.extend(elegidos)

    # Pase 2: Categoría gramatical relajada si faltan opciones
    if len(seleccionados) < count:
        for pool in pools_prioridad:
            cands = []
            for v in sorted(set(pool)):
                if v == objetivo_id or v in seleccionados:
                    continue
                if v.lower() in NOMBRES_PROPIOS_CONTEXTUALES:
                    continue
                v_obj = items_lookup.get(v)
                if not v_obj:
                    continue
                v_es_sig = obtener_palabras_significativas_es(v_obj.get("es", ""))
                if v_es_sig & es_sig:
                    continue
                if son_traducciones_compatibles(oracion_es, v_obj.get("es", "")):
                    continue
                cands.append(v)
            faltan = count - len(seleccionados)
            if faltan <= 0:
                break
            if cands:
                elegidos = rng.sample(cands, min(faltan, len(cands)))
                seleccionados.extend(elegidos)

    return sorted([objetivo_id] + seleccionados)

