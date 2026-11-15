# Módulo ASR — Reconocimiento Automático del Habla (Sherpa-onnx / Icefall)

Este directorio implementa el ciclo completo de diseño fonológico, preparación de datos, entrenamiento acústico, aumento de datos (*data augmentation*), evaluación de métricas de precisión (WER, CER, PER) y exportación a **ONNX** para la lengua indígena originaria **Uchumataqu (Uru de Irohito)**.

El sistema utiliza la arquitectura **Zipformer2 CTC** (Encoder Zipformer de 6 etapas y cabeza lineal CTC; 64,015,648 parámetros), ejecutada mediante las recetas oficiales del framework **[k2-fsa/icefall](https://github.com/k2-fsa/icefall)** y optimizada para inferencia offline en dispositivos móviles mediante **Sherpa-onnx** y **OnnxRuntime**.

---

## 📁 Estructura del Directorio

```text
ASR/
├── datos_asr/                           # Inventario fonológico canónico
│   ├── tokens.txt                       # 42 tokens (4 especiales + 38 fonemas canónicos ASCII)
│   ├── lexicon.txt                      # 325 entradas léxicas con pronunciación fonética
│   └── corpus_asr_texto.txt             # 460 líneas de texto limpio para modelado
│
├── audios_originales/                   # Grabaciones crudas sin segmentar
│   ├── palabras/{eva, pedro, ...}/      # Tomas continuas de palabras por locutor
│   └── oraciones/{pedro, roberto, ...}/ # Grabaciones de oraciones por locutor
├── audios_palabras/                     # Grabaciones segmentadas y normalizadas (~2,662 WAVs)
├── audios_oraciones/                    # Grabaciones segmentadas de oraciones (~435 WAVs)
│
├── data/                                # Manifiestos de partición y cortes acústicos
│   ├── manifests/                       # Manifiestos JSON y Kaldi (train, val, test, pitch)
│   │   ├── train_manifest.json          # Partición de entrenamiento base
│   │   ├── train_manifest_pitch.json    # Partición con aumento de pitch (+200 / -200 cents)
│   │   ├── val_manifest.json            # Partición de validación
│   │   ├── test_manifest.json           # Partición de test independiente (460 audios)
│   │   └── kaldi/                       # wav.scp, text, utt2spk, spk2utt
│   └── lhotse/                          # Cortes Lhotse comprimidos (*.jsonl.gz)
│       ├── uchumataqu_cuts_train.jsonl.gz
│       ├── uchumataqu_cuts_train_pitch.jsonl.gz
│       ├── uchumataqu_cuts_val.jsonl.gz
│       └── uchumataqu_cuts_test.jsonl.gz
│
├── models/                              # Modelos entrenados y exportados
│   ├── exported_onnx/                   # MODELO OFICIAL EN PRODUCCIÓN (exp_scratch_v2)
│   │   ├── model.onnx                   # FP32 Float (262 MB)
│   │   ├── model.int8.onnx              # Cuantizado INT8 optimizado para móviles (72.5 MB)
│   │   ├── tokens.txt                   # Tokens fonéticos (índices 0..41)
│   │   └── lexicon.txt                  # Diccionario de búsqueda léxica
│   ├── exported_onnx_baseline_v1/       # Modelo preliminar baseline
│   └── exported_finetune/               # Modelo derivado de fine-tuning sobre LibriSpeech
│
├── pipeline_icefall/                    # 🧊 Recetas oficiales k2-fsa/icefall
│   ├── icefall_repo/                    # Submódulo / clon oficial de Icefall
│   │   └── egs/librispeech/ASR/zipformer/
│   │       ├── train.py                 # Receta: entrenamiento desde cero
│   │       ├── finetune.py              # Receta: fine-tuning
│   │       ├── decode.py                # Decodificador beam-search / greedy
│   │       └── export-onnx-ctc.py       # Exportador oficial CTC a ONNX
│   ├── exp_scratch_v2/                  # Logs y checkpoints del entrenamiento final (100 épocas)
│   ├── uchumataqu/                      # Scripts de adaptación a Lhotse y aumento
│   │   ├── prepare_uchumataqu.py        # Generador de cortes Lhotse
│   │   └── prepare_pitch_augmentation.py# Variación tonal acústica (+200 / -200 cents)
│   ├── run_train_scratch.sh             # Lanzador: entrenamiento desde cero
│   ├── run_finetune.sh                  # Lanzador: fine-tuning
│   ├── run_decode.sh                    # Lanzador: decodificación oficial
│   └── run_export.sh                    # Lanzador: exportación a ONNX INT8 / FP32
│
├── scripts/                             # Herramientas de preparación, limpieza y pruebas
│   ├── limpieza/                        # Normalización a -3 dBFS y corte de silencios
│   │   ├── limpiar_palabras.py
│   │   ├── limpiar_oraciones.py
│   │   └── verificar_audios_asr.py
│   ├── entrenamiento/                   # Generación de inventario fonológico y manifests
│   │   ├── lector_xlsx.py
│   │   ├── preparar_asr.py
│   │   └── preparar_dataset.py
│   └── pruebas/                         # Pruebas unitarias de inferencia y G2P
│       ├── probar_inferencia.py
│       └── tests/test_g2p.py            # 50 tests fonológicos
│
├── evaluar_wer_cer_testset.py           # Evaluador empírico independiente (WER, CER, PER)
├── evaluar_50_palabras_anexos.py        # Matriz de 50 palabras clave para anexos de tesis
├── reportes/                            # Informes de auditoría acústica
│   ├── reporte_audios_asr.txt
│   └── reporte_audios_faltantes_asr_gaby_sofia_roberto_pedro.txt
└── README.md                            # Esta guía
```

---

## 🔬 Especificaciones Técnicas del Modelo en Producción

El modelo en producción integrado en Unity y evaluado para el Capítulo IV corresponde a la corrida **`exp_scratch_v2`**:

| Parámetro | Valor Técnico | Detalle y Justificación |
| :--- | :--- | :--- |
| **Arquitectura** | **Zipformer2 CTC** | Encoder Zipformer (6 stacks convolucionales-atencionales) + proyección CTC |
| **Parámetros** | **64,015,648** (~64 M) | Dimensiones: `num_encoder_layers="2,2,3,4,3,2"`, `encoder_dim="192,256,384,512,384,256"` |
| **Entrenamiento** | **Desde cero (*from scratch*)** | Sin pesos preentrenados; inicialización aleatoria para no heredar sesgos fonéticos externos |
| **Épocas** | **100 completadas** | Convergencia total verificada en logs (`ASR/pipeline_icefall/exp_scratch_v2/log/`) |
| **Función de pérdida** | **Pérdida CTC pura** | `use_ctc=True`, `use_transducer=False`, `ctc_loss_scale=1.0` |
| **Rasgos acústicos** | **80 Fbank (Mel)** | 16 kHz mono, ventana de 25 ms, paso de 10 ms |
| **Data Augmentation** | **Multi-nivel** | 1. *Speed Perturbation* (0.9, 1.1; p=2/3)<br>2. *SpecAugment* (time warp 80, 2x27 freq masks, 10x100 time masks)<br>3. *Pitch Shifting* acústico (+200 y -200 cents) |
| **Sampler** | **DynamicBucketingSampler** | 6 buckets de longitud, `max_duration=100` s por lote |
| **Tamaño ONNX** | **72.5 MB (INT8)** | Cuantización simétrica INT8 optimizada para ejecución en Android sin GPU |

---

## 🚀 Guía de Entrenamiento Paso a Paso (Cómo Entrenar ASR)

### Paso 1: Preparación del Corpus y Fonología G2P

1. **Limpieza y corte de grabaciones**:
   ```bash
   # Limpiar palabras por locutor (agrega 250 ms de silencio y normaliza a -3 dBFS)
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor eva
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor sofia
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor roberto
   python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor lorenzo
   
   # Limpiar oraciones
   python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro
   python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor gaby
   ```

2. **Auditar la cobertura acústica**:
   ```bash
   python3 ASR/scripts/limpieza/verificar_audios_asr.py
   ```

3. **Generar `tokens.txt`, `lexicon.txt` y corpus de texto**:
   ```bash
   python3 ASR/scripts/entrenamiento/preparar_asr.py
   ```
   *Genera los 42 tokens fonéticos canónicos y el léxico fonetizado mediante reglas G2P deterministas.*

4. **Crear particiones train, val y test**:
   ```bash
   python3 ASR/scripts/entrenamiento/preparar_dataset.py
   ```

5. **Aumento acústico de Pitch Shifting (+200 / -200 cents)**:
   ```bash
   python3 ASR/pipeline_icefall/uchumataqu/prepare_pitch_augmentation.py
   ```

6. **Convertir manifiestos a cortes Lhotse**:
   ```bash
   python3 ASR/pipeline_icefall/uchumataqu/prepare_uchumataqu.py
   ```

---

### Paso 2: Ejecución del Entrenamiento con Icefall

Para entrenar el modelo desde cero con la receta oficial de Zipformer:

```bash
# Lanzar entrenamiento desde cero (100 épocas en GPU):
NUM_EPOCHS=100 MAX_DURATION=100 bash ASR/pipeline_icefall/run_train_scratch.sh
```

El script invoca internamente la receta oficial `egs/librispeech/ASR/zipformer/train.py` con:
- `use-ctc=True`
- `lr-batches=7500`
- `dynamic-batching=True`
- `exp-dir=ASR/pipeline_icefall/exp_scratch_v2`

Los checkpoints por época (`epoch-1.pt` a `epoch-100.pt`) se almacenan en `ASR/pipeline_icefall/exp_scratch_v2/`.

---

### Paso 3: Promedio de Checkpoints y Exportación a ONNX

Para obtener el modelo final robusto, se promedian los últimos 15 checkpoints y se exporta a formato ONNX para Sherpa-onnx:

```bash
# Exportar modelo CTC a ONNX (FP32 e INT8):
EPOCH=100 AVG=15 bash ASR/pipeline_icefall/run_export.sh
```

Este proceso genera en `ASR/models/exported_onnx/`:
- `model.onnx`: Grafo computacional en precisión FP32 (262 MB).
- `model.int8.onnx`: Grafo cuantizado a enteros de 8 bits (72.5 MB).
- `tokens.txt` y `lexicon.txt`: Recursos léxicos requeridos por el motor de inferencia.

---

### Paso 4: Evaluación Rigurosa (WER, CER, PER)

El repositorio incluye dos evaluadores automatizados independientes:

```bash
# 1. Evaluación completa sobre el Test Set oficial (460 audios independientes):
python3 ASR/evaluar_wer_cer_testset.py

# 2. Evaluación de las 50 palabras clave de la matriz de anexos:
python3 ASR/evaluar_50_palabras_anexos.py
```

#### Resultados Empíricos Verificados en Test Set Oficial:
- **WER (Word Error Rate)**: **14.86%**
- **CER (Character Error Rate)**: **4.88%**
- **PER (Phoneme Error Rate)**: **4.79%**
- **Acierto exacto de pronunciación en palabras aisladas**: **100.0%** (0.0% PER)

Los reportes detallados se guardan automáticamente en:
- `evidencias_capitulo_iv/RESULTADOS_DETALLADOS_WER_CER_ASR.csv`
- `evidencias_capitulo_iv/TABLA_50_PALABRAS_ASR_ANEXOS.csv`
- `evidencias_capitulo_iv/resumen_wer_cer_asr.json`

---

### Paso 5: Pruebas en Tiempo Real y Diagnóstico

#### Opción A: Servidor Web con Interfaz Gráfica (`web_asr_tester`)
Proporciona una interfaz gráfica moderna en el navegador para grabar con micrófono, subir archivos WAV, comparar múltiples modelos (Scratch INT8, FP32, Fine-Tuning), inspeccionar el semáforo fonético y exportar diagnósticos en CSV:

```bash
bash web_asr_tester/iniciar_servidor.sh
# Abra en su navegador: http://localhost:8080
```

#### Opción B: Inferencia rápida por consola
```bash
python3 ASR/scripts/pruebas/probar_inferencia.py \
    --audio ASR/audios_palabras/pedro/chisi_01.wav \
    --esperado "ch'isi" \
    --model ASR/models/exported_onnx/model.int8.onnx
```

#### Opción C: Pruebas unitarias de reglas G2P (50 tests fonológicos)
```bash
python3 -m unittest ASR/scripts/pruebas/tests/test_g2p.py
```
