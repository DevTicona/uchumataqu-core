# Uchumataqu — Proyecto de Grado

Aplicación móvil educativa offline para la revitalización de la lengua indígena originaria **Uchumataqu (Uru de Irohito)**, integrando Procesamiento del Lenguaje Natural (**PLN / HFST**), Reconocimiento Automático del Habla offline (**ASR / Icefall Zipformer / Sherpa-onnx**) y Realidad Aumentada (**RA**) en **Unity**.

---

## 🏛️ Arquitectura General del Repositorio

```text
proyecto-grado/
├── ASR/                            # Módulo ASR: Reconocimiento Automático del Habla
│   ├── datos_asr/                  # Tokens canónicos (42), léxico fonético y corpus de texto
│   ├── audios_palabras/            # Grabaciones segmentadas de palabras (~2,662 WAVs)
│   ├── audios_oraciones/           # Grabaciones segmentadas de oraciones (~435 WAVs)
│   ├── data/                       # Manifiestos de partición (train, val, test, pitch) y cortes Lhotse
│   ├── models/exported_onnx/       # Modelo Zipformer en producción (FP32 y cuantizado INT8 - 72 MB)
│   ├── pipeline_icefall/           # Recetas oficiales Icefall (Zipformer CTC train/finetune/decode/export)
│   ├── scripts/                    # Scripts de limpieza de audio, G2P, preparación y pruebas
│   ├── evaluar_wer_cer_testset.py  # Evaluador empírico independiente (WER, CER, PER)
│   └── README.md                   # Guía técnica completa del módulo ASR
│
├── PLN/                            # Módulo PLN: Procesamiento del Lenguaje Natural
│   ├── hfst/                       # Transductor Morfológico de Estados Finitos (Oficial Producción)
│   │   ├── src/                    # Compilador y runtime HFST en Python
│   │   ├── grammar/                # Gramática Léxica formal (lexicon.lexc)
│   │   ├── build/                  # Transductores compilados (.hfst y optimizado .hfstol)
│   │   ├── export/pln-hfst-v1/     # Modelos binarios e índices JSON para Unity
│   │   ├── tests/                  # 27 pruebas automatizadas de regresión morfológica
│   │   └── README.md               # Guía técnica completa de compilación y uso HFST
│   ├── seq2seq/                    # Modelo neuronal experimental con atención
│   ├── palabras.json               # Vocabulario de 266 familias léxicas agrupadas
│   ├── oraciones.json              # 137 oraciones canónicas documentadas
│   ├── diccionario.json            # 1,384 registros históricos documentados
│   └── README.md                   # Visión general del módulo lingüístico
│
├── UNITY/                          # Módulo Unity: Aplicación Móvil y Recursos Educativos
│   ├── datos_app/                  # JSONs de runtime (lecciones_compiladas, palabras, oraciones, RA)
│   ├── audios_palabras/            # Audios WAV normalizados a -3.0 dBFS para la app (~326)
│   ├── audios_oraciones/           # Audios WAV normalizados a -3.0 dBFS de oraciones (~136)
│   ├── scripts/corpus/             # Compilador curricular determinista (11 modalidades pedagógicas)
│   ├── scripts/audio/              # Normalizador y auditor de archivos acústicos
│   └── README.md                   # Guía de organización, adición de contenidos y sincronización
│
├── web_asr_tester/                 # Servidor Web de Pruebas y Diagnóstico en Tiempo Real
│   ├── server.py                   # API REST con inferencia Sherpa-onnx, G2P y alineador fonético
│   ├── static/                     # Frontend interactivo (HTML, CSS moderno, JavaScript)
│   ├── iniciar_servidor.sh         # Script para lanzar la consola web en http://localhost:8080
│   └── test_*.py                   # Pruebas automatizadas de la API y lógica de evaluación
│
├── excel/                          # Fuentes primarias léxicas y oraciones en hojas de cálculo
│   ├── palabras_app.xlsx           # Vocabulario curricular para la aplicación móvil
│   ├── palabras_pln.xlsx           # Vocabulario extendido para modelado lingüístico
│   └── oraciones.xlsx              # Oraciones con traducción para lecciones y reserva
│
├── validar_todo.py                 # Suite de validación integral del proyecto (25 reglas obligatorias)
├── sincronizar_unity.py            # Sincronizador controlado WSL -> Unity Windows
├── probar_hfst_tiempo_real.py      # Consola interactiva para análisis morfológico HFST en terminal
└── README.md                       # Esta guía maestra
```

---

## ⚡ Comandos de Uso Frecuente (Quickstart)

### 1. Validación Integral de Todo el Proyecto
Verifica las 25 reglas pedagógicas, estructurales, consistencia fonológica y determinismo reproducible:
```bash
python3 validar_todo.py
```
*Debe retornar: `TODAS LAS 25 VALIDACIONES PASARON EXITOSAMENTE (100% OK)`.*

---

### 2. Reconocimiento de Voz (ASR)

#### Servidor Web Interactivo de Diagnóstico:
Inicie el tester web con interfaz gráfica para probar grabaciones con micrófono, subir audios, comparar modelos y ver el semáforo fonético:
```bash
bash web_asr_tester/iniciar_servidor.sh
# Acceda desde su navegador a: http://localhost:8080
```

#### Evaluación Oficial de Precisión (WER, CER, PER):
Ejecuta la evaluación rigurosa sobre el conjunto de prueba independiente (460 audios):
```bash
python3 ASR/evaluar_wer_cer_testset.py
```
*Resultados empíricos: **WER 14.86%**, **CER 4.88%**, **PER 4.79%**.*

#### Inferencia por línea de comandos:
```bash
python3 ASR/scripts/pruebas/probar_inferencia.py \
    --audio ASR/audios_palabras/pedro/chisi_01.wav \
    --esperado "ch'isi" \
    --model ASR/models/exported_onnx/model.int8.onnx
```

*Para detalles de cómo entrenar el modelo desde cero con Icefall (100 épocas) y exportar a ONNX, consulte **[ASR/README.md](ASR/README.md)**.*

---

### 3. Procesamiento del Lenguaje Natural (PLN / HFST)

#### Analizador Morfológico Interactivo en Consola:
```bash
python3 probar_hfst_tiempo_real.py
```
*Muestra lemas, categorías gramaticales, sufijos desglosados y sugerencias ortográficas en tiempo real.*

#### Compilación y Pruebas Unitarias de HFST:
```bash
# Compilar el transductor morfológico:
bash PLN/hfst/run.sh build

# Ejecutar las 27 pruebas unitarias de regresión:
bash PLN/hfst/test.sh -q
```

*Para detalles de cómo construir y modificar gramáticas lexc y transductores, consulte **[PLN/hfst/README.md](PLN/hfst/README.md)**.*

---

### 4. Organización de Contenidos y Sincronización con Unity

#### Recompilar el currículo (26 lecciones y 6 escenarios RA):
```bash
python3 UNITY/scripts/corpus/preparar_corpus_app.py
```

#### Normalizar audios a -3.0 dBFS y auditar cobertura sonora:
```bash
python3 UNITY/scripts/audio/normalizar_audios.py
python3 UNITY/scripts/audio/verificar_audios_app.py
```

#### Sincronizar desde WSL hacia el proyecto Unity en Windows:
```bash
# Simulación (sin escribir en disco):
python3 sincronizar_unity.py --dry-run

# Sincronización real (copia archivos nuevos o modificados por SHA-256):
python3 sincronizar_unity.py

# Sincronización con limpieza de huérfanos:
python3 sincronizar_unity.py --delete
```

*Para la guía detallada de cómo agregar nuevas palabras, oraciones, audios y lecciones, consulte **[UNITY/README.md](UNITY/README.md)**.*

---

## 📚 Enlaces a la Documentación Específica por Módulo

- 🎙️ **[Guía Completa de ASR (Entrenamiento, Aumento, Icefall, ONNX)](ASR/README.md)**
- 🧊 **[Recetas de Icefall y Entrenamiento de Zipformer](ASR/pipeline_icefall/README.md)**
- 📖 **[Guía Completa de HFST (Morfología, Lexc, Transductores)](PLN/hfst/README.md)**
- 🎮 **[Guía de la Aplicación Móvil Unity (Contenidos, Audios, Sincronización)](UNITY/README.md)**
- 🌐 **[Herramienta de Diagnóstico Web ASR Tester](web_asr_tester/README.md)**
