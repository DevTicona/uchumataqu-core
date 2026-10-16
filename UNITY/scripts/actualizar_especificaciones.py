"""
actualizar_especificaciones.py
Sincroniza y actualiza la documentación y especificaciones oficiales conforme a:
- Catálogo generable de 22 tipos activos (memoria_uch_es retirada de la generación).
- Secuenciación: exactamente 1 presentación + 1 microactividad inmediata por familia nueva.
- ASR opcional distribuido (1-2 léxicos + 1 de oración) intercalado.
- Presupuestos de escritura (1 para 1-4, 2 para 5-8, 3 para 9+) y máx 1 escribir_oracion.
- Espaciado mínimo de >=3 pasos intermedios.
"""

import os

PROJECT_ROOT = "/home/primo/proyecto-grado"
UNITY_DOCS = "/mnt/d/unity/Uchumataqu/Docs/Specifications"

def actualizar_archivo(ruta, reemplazos):
    if not os.path.exists(ruta):
        print(f"Omitido (no existe): {ruta}")
        return
    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read()

    modificado = False
    for viejo, nuevo in reemplazos:
        if viejo in contenido:
            contenido = contenido.replace(viejo, nuevo)
            modificado = True

    if modificado:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        print(f"Actualizado: {ruta}")
    else:
        print(f"Sin cambios necesarios: {ruta}")

def main():
    # 1. 08-patron-arquitectonico-mvp.md
    ruta_08 = os.path.join(UNITY_DOCS, "08-patron-arquitectonico-mvp.md")
    r_08 = [
        (
            "Los 23 tipos oficiales son:",
            "El catálogo generable activo consta de 22 tipos de actividad (con memoria_uch_es conservado en Unity únicamente por compatibilidad de lectura con datos históricos, pero retirado de la generación activa):"
        )
    ]
    actualizar_archivo(ruta_08, r_08)

    # 2. 04-flujo-leccion-app.md
    ruta_04 = os.path.join(UNITY_DOCS, "04-flujo-leccion-app.md")
    r_04 = [
        (
            "12. **Memoria de pares UCH ↔ ES**.\n13. **Escucha y repite** mediante Sherpa-onnx; opcional y no bloqueante.",
            "12. **Memoria de pares UCH ↔ ES** (conservada por retrocompatibilidad de lectura en Unity, retirada de la generación activa nueva).\n13. **Escucha y repite** (ASR léxico) mediante Sherpa-onnx; opcional, no bloqueante y distribuido (~30–40% y ~65–75% de las familias).\n14. **Escribir palabra**: producción escrita espaciada con consigna y refuerzo adaptativo al fallar.\n15. **Escribir forma**: producción morfológica escrita espaciada."
        ),
        (
            "5. **Audio → seleccionar traducción**.",
            "5. **Audio → seleccionar traducción**.\n6. **Escribir oración**: producción escrita guiada de 2 a 6 tokens (máximo 1 por lección).\n7. **Escucha y repite oración** (ASR de oración completa): intercalada hacia la mitad de las oraciones; opcional y no bloqueante."
        ),
        (
            "2. Cada familia nueva recibe al menos una microactividad inmediata.",
            "2. Cada familia nueva recibe exactamente una presentación seguida inmediatamente por una microactividad individual compatible."
        )
    ]
    actualizar_archivo(ruta_04, r_04)

    # 3. 05-guia-corpus-datos.md (ambas rutas)
    for dir_spec in [os.path.join(PROJECT_ROOT, "Specifications"), UNITY_DOCS]:
        ruta_05 = os.path.join(dir_spec, "05-guia-corpus-datos.md")
        r_05 = [
            (
                '"version": 1,\n  "lecciones": [',
                '"version": 3,\n  "metricas_distractores": { ... },\n  "informe_compilacion": [ ... ],\n  "lecciones": ['
            )
        ]
        actualizar_archivo(ruta_05, r_05)

    # 4. 01-modulo-pln-texto.md (ambas rutas)
    for dir_spec in [os.path.join(PROJECT_ROOT, "Specifications"), UNITY_DOCS]:
        ruta_01 = os.path.join(dir_spec, "01-modulo-pln-texto.md")
        r_01 = [
            (
                "3. vocabulario enseñado previamente;\n4. opciones con traducciones distintas y sin duplicados;",
                "3. vocabulario enseñado previamente (dejando una separación de al menos 3 pasos intermedios para revaluar una familia);\n4. opciones con traducciones distintas y sin duplicados (admitiendo 2–4 opciones según disponibilidad sin inventar distractores);"
            )
        ]
        actualizar_archivo(ruta_01, r_01)

    # 5. guia-pruebas-validacion.md
    ruta_val = os.path.join(UNITY_DOCS, "guia-pruebas-validacion.md")
    r_val = [
        (
            "- cada familia nueva recibe al menos una microactividad;",
            "- cada familia nueva recibe exactamente una presentación seguida de una microactividad inmediata;\n- retiro de memoria_uch_es de la generación (exactamente 0 pasos generados);\n- catálogo generable de 22 tipos activos;\n- ASR opcional distribuido (1–2 léxicos + 1 de oración) intercalado sin concentración al final;\n- presupuesto de escritura léxica (1 para 1–4, 2 para 5–8, 3 para 9+) y máx 1 escribir_oracion;\n- espaciado de al menos 3 pasos intermedios antes de revaluar una familia;"
        )
    ]
    actualizar_archivo(ruta_val, r_val)

if __name__ == "__main__":
    main()
