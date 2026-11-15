"""
preparar_asr.py
Pipeline de preparación de datos para el módulo ASR (Sherpa-onnx / Moonshine / Zipformer).
Basado en:
  - 01-modulo-pln-texto.md
  - 02-modulo-asr-voz.md
  - 02-1-inventario-fonologico-uchumataqu.md

Entradas:
  - excel/palabras_pln.xlsx
  - excel/oraciones.xlsx

Salidas en ASR/datos_asr/:
  - tokens.txt: Inventario de 42 tokens (índices 0 a 41: especiales + 38 fonemas canónicos ASCII)
  - lexicon.txt: Diccionario de pronunciación fonética (palabra -> fonemas)
  - corpus_asr_texto.txt: Corpus textual limpio para modelo de lenguaje y entrenamiento
"""
 
import os
import re
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
entrenamiento_dir = script_dir
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)

sys.path.insert(0, entrenamiento_dir)
from lector_xlsx import leer_xlsx

# ===========================================================================
# 1. INVENTARIO FONOLÓGICO Y REGLAS G2P (Grafema a Fonema)
# ===========================================================================

FONEMAS_CANONICOS = {
    "A", "AA", "E", "EE", "I", "II", "O", "OO", "U", "UU",
    "P", "T", "K", "Q", "M", "N", "R", "S", "X", "J", "L", "LL", "Y", "W",
    "TS", "CH", "SH", "NY",
    "PH", "TH", "KH", "QH", "CHH",
    "P_EJ", "T_EJ", "K_EJ", "Q_EJ", "CH_EJ"
}

REGLAS_G2P_COMPILADAS = [
    # Nivel 1 — Trígrafos
    (re.compile(r"chʼ"), " CH_EJ "),   # IPA: t͡ʃʼ
    (re.compile(r"chh"), " CHH "),      # IPA: t͡ʃʰ

    # Nivel 2 — Dígrafos aspirados / eyectivos
    (re.compile(r"ph"), " PH "),        # IPA: pʰ
    (re.compile(r"th"), " TH "),        # IPA: tʰ
    (re.compile(r"kh"), " KH "),        # IPA: kʰ
    (re.compile(r"qh"), " QH "),        # IPA: qʰ
    (re.compile(r"pʼ"), " P_EJ "),      # IPA: pʼ
    (re.compile(r"tʼ"), " T_EJ "),      # IPA: tʼ
    (re.compile(r"kʼ"), " K_EJ "),      # IPA: kʼ
    (re.compile(r"qʼ"), " Q_EJ "),      # IPA: qʼ
    (re.compile(r"ch"), " CH "),        # IPA: t͡ʃ

    # Nivel 3 — Secuencias fonotácticas combinadas
    (re.compile(r"tk"), " T K "),
    (re.compile(r"tsh"), " T SH "),

    # Nivel 4 — Dígrafos restantes
    (re.compile(r"ts"), " TS "),        # IPA: t͡s
    (re.compile(r"ll|ly|lʼ"), " LL "),  # IPA: ʎ
    (re.compile(r"ñ"), " NY "),         # IPA: ɲ
    (re.compile(r"sh"), " SH "),        # IPA: ʃ

    # Nivel 5 — Vocales largas nativas con diéresis y variantes ortográficas
    (re.compile(r"ä|aa|ā|â|a:"), " AA "),
    (re.compile(r"ë|ee|ē|ê|e:"), " EE "),
    (re.compile(r"ï|ii|ī|î|i:"), " II "),
    (re.compile(r"ö|oo|ō|ô|o:"), " OO "),
    (re.compile(r"ü|uu|ū|û|u:"), " UU "),

    # Nivel 6A — Adaptaciones técnicas de préstamos del castellano
    (re.compile(r"c"), " K "),          # /k/ velar (ej. Carlos -> K A R L O S)
    (re.compile(r"d"), " T "),          # /t/ sorda aproxima /d/ sonora (ej. Pedro -> P E T R O)
    (re.compile(r"h"), ""),            # 'h' muda en préstamos (ej. Irohito -> I R O I T O)

    # Nivel 6B — Vocales castellanas acentuadas en préstamos (vocales cortas)
    (re.compile(r"á"), " A "),
    (re.compile(r"é"), " E "),
    (re.compile(r"í"), " I "),          # ej. María -> M A R I A (no colisiona con ï -> II)
    (re.compile(r"ó"), " O "),
    (re.compile(r"ú"), " U "),

    # Nivel 7 — Grafemas simples restantes
    (re.compile(r"p"), " P "),
    (re.compile(r"t"), " T "),
    (re.compile(r"k"), " K "),
    (re.compile(r"q"), " Q "),
    (re.compile(r"s|z"), " S "),        # z es variante gráfica de s
    (re.compile(r"x"), " X "),          # x nativa = /χ/ uvular
    (re.compile(r"j"), " J "),          # j nativa = /x/ velar
    (re.compile(r"m"), " M "),
    (re.compile(r"n"), " N "),
    (re.compile(r"r"), " R "),
    (re.compile(r"l"), " L "),
    (re.compile(r"y"), " Y "),          # semivocal /j/
    (re.compile(r"w"), " W "),
    (re.compile(r"a"), " A "),
    (re.compile(r"e"), " E "),
    (re.compile(r"i"), " I "),
    (re.compile(r"o"), " O "),
    (re.compile(r"u"), " U "),
]


def normalizar_apostrofes(texto: str) -> str:
    """Normaliza todas las variantes tipográficas de apóstrofe al glifo canónico U+02BC (ʼ)."""
    return re.sub(r"['’\u2018\u2019\u0060\u00b4\u02b9]", "ʼ", texto)


def grafema_a_fonema(palabra_uch: str) -> str:
    """Convierte una palabra en Uchumataqu a su secuencia de fonemas canónicos ASCII."""
    texto = normalizar_apostrofes(palabra_uch.lower().strip().replace("-", "").replace(".", "").replace(",", ""))
    for patron, reemplazo in REGLAS_G2P_COMPILADAS:
        texto = patron.sub(reemplazo, texto)
    fonemas = [t for t in texto.split() if t]

    for f in fonemas:
        if f not in FONEMAS_CANONICOS:
            raise ValueError(f"Fonema '{f}' generado para '{palabra_uch}' no pertenece al inventario canónico.")

    return " ".join(fonemas)


# ===========================================================================
# 2. GENERADORES DE ARCHIVOS ASR
# ===========================================================================

def generar_tokens_txt(ruta_salida: str):
    tokens_especiales = ["<blk>", "<sos/eos>", "<unk>", "<sil>"]
    fonemas_ordenados = sorted(list(FONEMAS_CANONICOS))
    todos_los_tokens = tokens_especiales + fonemas_ordenados

    with open(ruta_salida, "w", encoding="utf-8") as f:
        for idx, tok in enumerate(todos_los_tokens):
            f.write(f"{tok} {idx}\n")
    print(f"[OK] Generado: {ruta_salida} ({len(todos_los_tokens)} tokens)")


def generar_lexicon_txt(palabras_lista: list, ruta_salida: str):
    lexicon_entradas = {}
    for p in palabras_lista:
        pid = p.strip()
        if not pid:
            continue
        fonemas = grafema_a_fonema(pid)
        lexicon_entradas[pid.lower()] = fonemas

    entradas_ordenadas = sorted(lexicon_entradas.items())
    with open(ruta_salida, "w", encoding="utf-8") as f:
        for pal, fon in entradas_ordenadas:
            f.write(f"{pal}\t{fon}\n")
    print(f"[OK] Generado: {ruta_salida} ({len(entradas_ordenadas)} entradas léxicas)")


def generar_corpus_texto_txt(palabras_uch: list, oraciones_uch: list, ruta_salida: str):
    lineas_unicas = set()

    for p in palabras_uch:
        p_clean = p.strip().replace(".", "").replace(",", "").capitalize()
        if p_clean:
            lineas_unicas.add(p_clean)

    for o in oraciones_uch:
        o_clean = o.strip().replace(".", "").replace(",", "").capitalize()
        if o_clean:
            lineas_unicas.add(o_clean)

    lineas_ordenadas = sorted(list(lineas_unicas))
    with open(ruta_salida, "w", encoding="utf-8") as f:
        for l in lineas_ordenadas:
            f.write(f"{l}\n")
    print(f"[OK] Generado: {ruta_salida} ({len(lineas_ordenadas)} líneas)")


# ===========================================================================
# 3. EJECUCIÓN PRINCIPAL
# ===========================================================================

def main():
    ruta_palabras_pln = os.path.join(project_root, "excel", "palabras_pln.xlsx")
    ruta_oraciones_pln = os.path.join(project_root, "excel", "oraciones.xlsx")
    dir_salida_asr = os.path.join(asr_dir, "datos_asr")
    os.makedirs(dir_salida_asr, exist_ok=True)

    print("=== PROCESANDO DATOS PARA EL MÓDULO ASR ===")

    # 1. Cargar palabras de PLN
    rows_palabras = leer_xlsx(ruta_palabras_pln)[1:]
    palabras_uch = [r[1].strip() for r in rows_palabras if len(r) > 1 and r[1]]
    print(f"Total palabras PLN cargadas: {len(palabras_uch)}")

    # 2. Cargar oraciones de PLN (las 136 oraciones curriculares que tienen audio)
    rows_oraciones = leer_xlsx(ruta_oraciones_pln)[1:]
    oraciones_uch = []
    for r in rows_oraciones:
        if len(r) > 1 and r[1]:
            oid = r[0].strip() if r[0] else ""
            try:
                num = int(re.sub(r"\D", "", oid))
                if num > 136:
                    continue
            except ValueError:
                pass
            oraciones_uch.append(r[1].strip())
    print(f"Total oraciones PLN cargadas (136 con audio): {len(oraciones_uch)}")

    # 3. Generar tokens.txt
    ruta_tokens = os.path.join(dir_salida_asr, "tokens.txt")
    generar_tokens_txt(ruta_tokens)

    # 4. Generar lexicon.txt
    ruta_lexicon = os.path.join(dir_salida_asr, "lexicon.txt")
    generar_lexicon_txt(palabras_uch, ruta_lexicon)

    # 5. Generar corpus_asr_texto.txt
    ruta_corpus = os.path.join(dir_salida_asr, "corpus_asr_texto.txt")
    generar_corpus_texto_txt(palabras_uch, oraciones_uch, ruta_corpus)

    print("=== PROCESAMIENTO ASR COMPLETADO CON ÉXITO ===")


if __name__ == "__main__":
    main()
