# Módulo PLN — Procesamiento del Lenguaje Natural (Uchumataqu)

Este módulo implementa las herramientas lingüísticas computacionales para el modelado, segmentación morfológica, verificación ortográfica y análisis de la lengua originaria **Uchumataqu (Uru de Irohito)**.

El módulo está estructurado en dos tecnologías complementarias con entornos y herramientas independientes:

1. **[HFST (Helsinki Finite-State Transducer)](hfst/README.md)**: **Modelo Oficial para Producción**.
   Transductor de estados finitos bidireccional (analizador y generador) compilado a partir de formas léxicas atestadas y reglas morfológicas documentadas. Garantiza precisión estricta, determinismo, cero alucinaciones y ejecución instantánea (< 5 ms).
2. **[Seq2Seq (Red Neuronal con Atención)](seq2seq/README.md)**: **Piloto Experimental**.
   Arquitectura neuronal basada en codificador-decodificador de caracteres para investigación lingüística y experimentación comparativa.

---

## 📁 Fuentes Primarias y Reglas Lingüísticas

En la raíz de este directorio se conservan las fuentes léxicas y normativas consolidadas:
- `palabras.json`: Vocabulario base estructurado en familias léxicas (raíces y formas documentadas).
- `oraciones.json`: 137 oraciones canónicas con transcripción normalizada y traducción.
- `diccionario.json`: 1,384 registros léxicos documentados de fuentes históricas (Hannss 2008, Métraux 1935, Uhle 1894).
- `reglas_de_escritura_y_gram_tica_uchumataqu.md`: Compendio de reglas fonológicas, ortográficas y gramaticales.

---

## 🚀 Comandos Rápidos de Uso

Desde la raíz del proyecto:

```bash
# 1. Analizar morfológicamente una palabra con HFST:
bash PLN/hfst/run.sh analyze achasinaka

# 2. Diagnosticar la respuesta de un estudiante frente a un objetivo:
bash PLN/hfst/run.sh compare achasi achasinaka

# 3. Compilar el transductor morfológico HFST:
bash PLN/hfst/run.sh build

# 4. Ejecutar la consola interactiva en tiempo real (con colores y glosario de sufijos):
python3 probar_hfst_tiempo_real.py

# 5. Ejecutar las pruebas unitarias de regresión (27 tests):
bash PLN/hfst/test.sh -q
```

Para una explicación exhaustiva de la arquitectura del transductor, gramática lexc y exportación para Unity, consulte la **[Guía Detallada de HFST](hfst/README.md)**.
