#!/usr/bin/env python3
"""
probar_hfst_tiempo_real.py
Consola interactiva en tiempo real para probar el analizador morfológico HFST en Uchumataqu.
Permite ingresar palabras, formas flexionadas o frases y obtener su análisis lingüístico al instante.
"""

import os
import sys
import json
import difflib

# Agregar el paquete HFST al path
WS_ROOT = os.path.dirname(os.path.abspath(__file__))
HFST_SRC = os.path.join(WS_ROOT, "PLN", "hfst", "src")
if HFST_SRC not in sys.path:
    sys.path.insert(0, HFST_SRC)

try:
    from uchumataqu_hfst.runtime import Analyzer
    from uchumataqu_hfst.data import normalize
except ImportError as e:
    print(f"Error al importar el analizador HFST: {e}")
    sys.exit(1)

# Colores ANSI para terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    DIM = "\033[2m"

POS_NOMBRES = {
    "N": "Sustantivo (Nombre)",
    "V": "Verbo",
    "ADJ": "Adjetivo",
    "ADV": "Adverbio",
    "PRON": "Pronombre",
    "NUM": "Numeral",
    "EXPR": "Expresión / Frase fija",
    "INTERJ": "Interjección",
    "UNK": "Léxico no clasificado"
}

SUFIJOS_DESCRIPCION = {
    "naka": "Pluralizador nominal (-naka: plural)",
    "k": "Enclítico / Sufijo topicalizador o delimitativo (-k / -ki)",
    "cha": "Sufijo diminutivo o afectivo (-cha: pequeño/afectivo)",
    "pini": "Sufijo intensificador / enfático (-pini: 'muy', 'totalmente', 'ciertamente', 'siempre')",
    "m": "Sufijo de segunda persona posesivo o verbal (-m: tu / tú)",
    "skama": "Sufijo limitativo temporal (-skama: hasta)",
    "taki": "Sufijo benefactivo o destino (-taki: para)"
}


def calcular_similitud(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100.0


def main():
    print(f"{Color.CYAN}Cargando transductor morfológico HFST y modelos lingüísticos...{Color.RESET}")
    try:
        analyzer = Analyzer()
    except Exception as e:
        print(f"{Color.RED}Error al inicializar Analyzer HFST: {e}{Color.RESET}")
        return

    # Cargar todas las formas conocidas para sugerencias ortográficas
    formas_conocidas = list(analyzer.records.keys())
    superficies_conocidas = {r["surface"]: r for r in analyzer.records.values()}

    print(f"{Color.GREEN}✓ Transductor HFST cargado correctamente ({len(analyzer.records)} formas documentadas registradas).{Color.RESET}\n")

    print(f"{Color.BOLD}{Color.CYAN}╔════════════════════════════════════════════════════════════════════════════════╗{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║            ANALIZADOR MORFOLÓGICO EN TIEMPO REAL - HFST UCHUMATAQU            ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}╠════════════════════════════════════════════════════════════════════════════════╣{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║  Escribe una palabra o frase en Uchumataqu y presiona ENTER.                   ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║  Comandos útiles:                                                              ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║    - 'ejemplos' : Muestra una lista de formas para copiar y probar.            ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║    - 'evaluar <esperado> <respuesta>' : Simula una evaluación pedagógica.     ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}║    - 'salir'    : Terminar la prueba.                                          ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}╚════════════════════════════════════════════════════════════════════════════════╝{Color.RESET}\n")

    while True:
        try:
            linea = input(f"{Color.BOLD}{Color.YELLOW}Uchumataqu > {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.CYAN}Finalizando prueba interactiva. ¡Hasta pronto!{Color.RESET}")
            break

        if not linea:
            continue

        cmd = linea.lower()
        if cmd in {"salir", "exit", "quit", "q"}:
            print(f"{Color.CYAN}Finalizando prueba interactiva. ¡Hasta pronto!{Color.RESET}")
            break

        if cmd == "ejemplos":
            print(f"\n{Color.BOLD}Ejemplos documentados para probar en HFST:{Color.RESET}")
            ejemplos = [
                ("achasinaka", "Almohadas (forma plural de achasi con sufijo -naka)"),
                ("achasi", "Almohada (raíz nominal simple)"),
                ("anapini", "Nunca (adverbio ana con sufijo enfático -pini)"),
                ("chusi", "Cama (raíz nominal)"),
                ("masota", "Gato (sustantivo animal)"),
                ("palitak", "Amigo (sustantivo de relación social)"),
                ("wiyantam", "Buenos días (fórmula de saludo)"),
                ("sitsni", "Profesor (sustantivo de ocupación)"),
                ("xala", "Llama (sustantivo animal)"),
                ("urkhu", "Vestido tradicional uru (vestimenta)"),
                ("watha", "Pueblo (topónimo / comunidad)"),
                ("amaruskchay", "Conversar (verbo en forma infinitiva)"),
            ]
            for palabra, desc in ejemplos:
                print(f"  • {Color.GREEN}{palabra:<14}{Color.RESET} : {desc}")
            print(f"\n{Color.DIM}También puedes probar comparar respuestas con: evaluar achasi achasinaka{Color.RESET}\n")
            continue

        if cmd.startswith("evaluar "):
            partes = linea.split()[1:]
            if len(partes) != 2:
                print(f"{Color.RED}Uso: evaluar <texto_esperado> <respuesta_usuario>{Color.RESET}\n")
                continue
            esperado, respuesta = partes[0], partes[1]
            cmp_res = analyzer.compare(esperado, respuesta)
            diag = cmp_res.get("diagnosis")
            msg = cmp_res.get("message", "")
            nota = cmp_res.get("note", "")

            color_diag = Color.GREEN if diag == "match" else (Color.YELLOW if diag == "documented_form_difference" else Color.RED)
            print(f"\n{Color.BOLD}Evaluación pedagógica HFST:{Color.RESET}")
            print(f"  • Esperado  : {Color.CYAN}{esperado}{Color.RESET}")
            print(f"  • Respuesta : {Color.CYAN}{respuesta}{Color.RESET}")
            print(f"  • Diagnóstico: {color_diag}{diag}{Color.RESET}")
            print(f"  • Mensaje   : {color_diag}{msg}{Color.RESET}")
            if nota:
                print(f"  • Nota      : {Color.DIM}{nota}{Color.RESET}")
            print()
            continue

        # Análisis de palabra o tokens en la frase
        tokens = [t for t in linea.replace(",", " ").replace(".", " ").replace("¿", "").replace("?", "").replace("!", "").split() if t]

        print(f"\n{Color.BOLD}--- RESULTADOS DEL ANÁLISIS MORFOLÓGICO HFST ---{Color.RESET}")
        for idx, token in enumerate(tokens, 1):
            resultado = analyzer.analyze(token)
            status = resultado.get("status")
            analisis_lista = resultado.get("analyses", [])

            prefix = f"[{idx}/{len(tokens)}] " if len(tokens) > 1 else ""
            print(f"\n{Color.BOLD}{prefix}Entrada: «{token}»{Color.RESET} (Normalizado: {resultado.get('normalized')})")

            if status == "analyzed" and analisis_lista:
                info = analisis_lista[0]
                pos_codigo = info.get("pos", "UNK")
                pos_nombre = POS_NOMBRES.get(pos_codigo, pos_codigo)
                sufijos = info.get("suffixes", [])
                segmentos = info.get("segments", [token])

                print(f"  {Color.GREEN}✓ ESTADO: RECONOCIDA POR HFST (Documentada en Corpus){Color.RESET}")
                print(f"  • Lema / Raíz canónica : {Color.BOLD}{info.get('lemma')}{Color.RESET}")
                print(f"  • Traducción al español: {Color.BOLD}{info.get('translation') or 'Sin traducción directa'}{Color.RESET}")
                print(f"  • Categoría gramatical : {pos_nombre}")
                
                # Segmentación
                if len(segmentos) > 1:
                    seg_str = " + ".join(segmentos)
                    print(f"  • Morfemas / Segmentos : {Color.CYAN}{seg_str}{Color.RESET}")
                else:
                    print(f"  • Morfemas / Segmentos : {Color.DIM}Raíz morfológica simple (sin sufijos){Color.RESET}")

                # Sufijos
                if sufijos:
                    suf_desc = [SUFIJOS_DESCRIPCION.get(s, f"-{s}") for s in sufijos]
                    print(f"  • Sufijos gramaticales : {Color.MAGENTA}{', '.join(suf_desc)}{Color.RESET}")
                    if "pini" in sufijos and pos_codigo in ("ADJ", "ADV"):
                        print(f"  • Matiz semántico      : {Color.YELLOW}Intensificador de grado: equivale a «muy» / «sumamente» (ej. {info.get('translation')}){Color.RESET}")

                # Etiqueta FST
                fst_tag = f"{info.get('lemma')}+{pos_codigo}+ID={info.get('id')}"
                if sufijos:
                    fst_tag += "".join(f"+SUF={s}" for s in sufijos)
                print(f"  • Etiqueta FST oficial : {Color.DIM}{fst_tag}{Color.RESET}")

                # Contextos
                ctxs = info.get("context_ids", [])
                if ctxs:
                    print(f"  • Oraciones de contexto: {Color.DIM}{', '.join(ctxs[:4])}{Color.RESET}")

            elif status == "ambiguous":
                print(f"  {Color.YELLOW}⚠ ESTADO: AMBIGUA ({len(analisis_lista)} interpretaciones encontradas){Color.RESET}")
                for a_idx, info in enumerate(analisis_lista, 1):
                    print(f"     Opción {a_idx}: {info.get('lemma')} ({info.get('pos')}) -> «{info.get('translation')}»")
            else:
                print(f"  {Color.RED}✗ ESTADO: NO RECONOCIDA / FUERA DE CORPUS HFST{Color.RESET}")
                print(f"    {Color.DIM}La forma «{token}» no está registrada en el transductor determinista.{Color.RESET}")

                # Sugerencias por similitud ortográfica
                candidatos = []
                for sup, r in superficies_conocidas.items():
                    sim = calcular_similitud(token, sup)
                    if sim >= 65.0:
                        candidatos.append((sim, sup, r))
                candidatos.sort(key=lambda x: -x[0])

                if candidatos:
                    print(f"    {Color.YELLOW}Sugerencias morfológicas cercanas:{Color.RESET}")
                    for sim, sup, r in candidatos[:3]:
                        print(f"      → ¿Quisiste decir {Color.BOLD}«{sup}»{Color.RESET} ({r.get('translation')})? (Similitud: {sim:.1f}%)")

        print(f"\n{Color.DIM}────────────────────────────────────────────────────────────────────────────{Color.RESET}\n")


if __name__ == "__main__":
    main()
