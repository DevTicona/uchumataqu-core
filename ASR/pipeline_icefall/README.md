# 🧊 Pipeline Icefall — Recetas Oficiales k2-fsa/icefall (Zipformer)

Pipeline de entrenamiento ASR basado en las **recetas oficiales del repositorio
[k2-fsa/icefall](https://github.com/k2-fsa/icefall)** adaptadas al corpus
**Uchumataqu (Uru de Irohito)**.

Utiliza la arquitectura **Zipformer** (estado del arte 2023–2025), entrenada con
pérdida conjunta **CTC + RNN-T** (Transducer), y exportación a **ONNX** para
integración con Sherpa-onnx en Unity.

---

## 📁 Estructura de esta carpeta

```text
pipeline_icefall/
├── icefall_repo/                       # Clon sparse oficial k2-fsa/icefall
│   ├── egs/librispeech/ASR/zipformer/  # Recetas oficiales
│   │   ├── train.py                    # Entrenamiento desde cero
│   │   ├── finetune.py                 # Fine-tuning con checkpoint preentrenado
│   │   ├── decode.py                   # Evaluación (greedy, beam-search)
│   │   ├── export-onnx-ctc.py          # Exportación CTC a ONNX
│   │   ├── export-onnx.py              # Exportación Transducer a ONNX
│   │   └── model.py                    # Arquitectura Zipformer
│   └── icefall/                        # Módulos core del framework
│       ├── checkpoint.py               # Guardado/carga de checkpoints
│       ├── utils.py                    # Utilidades de entrenamiento
│       └── ...
├── uchumataqu/
│   └── prepare_uchumataqu.py           # Convierte manifests JSON → Lhotse
├── run_train_scratch.sh                # Script: entrenamiento desde cero
├── run_finetune.sh                     # Script: fine-tuning oficial
├── run_decode.sh                       # Script: evaluación con beam-search
├── run_export.sh                       # Script: exportación a ONNX (Sherpa-onnx)
└── README.md                           # Este archivo
```

---

## ⚙️ Prerequisitos de Instalación

```bash
# 1. Instalar dependencias de icefall
pip install -r pipeline_icefall/icefall_repo/requirements.txt

# 2. Instalar k2 (versión compatible con CUDA/PyTorch — ver https://k2-fsa.github.io/k2/)
# Ejemplo para PyTorch 2.1 + CUDA 11.8:
pip install k2==1.24.4.dev20231220+cuda11.8.torch2.1.0 -f https://k2-fsa.github.io/k2/cuda.html

# 3. Instalar lhotse
pip install lhotse>=1.21

# 4. Instalar kaldifeat (opcional, para extracción de features eficiente)
pip install kaldifeat
```

> **Nota Docker:** El entorno `ASR/docker/` ya incluye estas dependencias. Ver `docker/Dockerfile`.

---

# 📘 Guía 1: Entrenamiento desde Cero (Zipformer CTC/RNN-T)

Esta guía explica cómo entrenar un modelo Zipformer **completamente desde cero**
usando el corpus Uchumataqu, sin ningún checkpoint preentrenado.

### Paso 1: Preparar datos base

Asegúrate de haber ejecutado primero el pipeline de preparación:

```bash
# 1a. Limpiar audios crudos (una vez por locutor)
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor sofia
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor eva
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor lorenzo
python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor roberto
python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro

# 1b. Generar tokens.txt, lexicon.txt, corpus
python3 ASR/scripts/entrenamiento/preparar_asr.py

# 1c. Generar manifests JSON y particiones
python3 ASR/scripts/entrenamiento/preparar_dataset.py
```

Verifica que tienes:
- `ASR/datos_asr/tokens.txt` (42 tokens)
- `ASR/data/manifests/train_manifest.json` (~2155 audios)
- `ASR/data/manifests/val_manifest.json` (~471 audios)
- `ASR/data/manifests/test_manifest.json` (~471 audios)

### Paso 2: Convertir manifests a formato Lhotse

```bash
python3 ASR/pipeline_icefall/uchumataqu/prepare_uchumataqu.py
```

Esto genera en `ASR/data/lhotse/`:
- `uchumataqu_cuts_train.jsonl.gz`
- `uchumataqu_cuts_val.jsonl.gz`
- `uchumataqu_cuts_test.jsonl.gz`

### Paso 3: Lanzar entrenamiento desde cero

```bash
# Entrenamiento en GPU única (recomendado: GPU ≥ 16 GB VRAM)
bash ASR/pipeline_icefall/run_train_scratch.sh

# Con parámetros personalizados:
NUM_EPOCHS=50 MAX_DURATION=300 bash ASR/pipeline_icefall/run_train_scratch.sh

# Multi-GPU (2 GPUs):
WORLD_SIZE=2 bash ASR/pipeline_icefall/run_train_scratch.sh
```

El script llama internamente a:
```bash
python3 icefall_repo/egs/librispeech/ASR/zipformer/train.py \
    --world-size 1 \
    --num-epochs 30 \
    --exp-dir pipeline_icefall/exp_scratch \
    --manifest-dir ASR/data/lhotse \
    --tokens ASR/datos_asr/tokens.txt \
    ...
```

**Checkpoints guardados en:** `pipeline_icefall/exp_scratch/`

### Paso 4: Evaluar el modelo

```bash
# Con epoch y promedio de checkpoints
EPOCH=30 AVG=15 bash ASR/pipeline_icefall/run_decode.sh

# Solo conjunto de validación
python3 icefall_repo/egs/librispeech/ASR/zipformer/decode.py \
    --epoch 30 --avg 15 \
    --exp-dir pipeline_icefall/exp_scratch \
    --decoding-method greedy_search \
    --manifest-dir ASR/data/lhotse \
    --tokens ASR/datos_asr/tokens.txt
```

### Paso 5: Exportar a ONNX para Sherpa-onnx

```bash
# Exportar cabeza CTC (recomendado para Sherpa-onnx)
cd pipeline_icefall/icefall_repo
python3 egs/librispeech/ASR/zipformer/export-onnx-ctc.py \
    --exp-dir ../exp_scratch \
    --tokens ASR/datos_asr/tokens.txt \
    --epoch 30 --avg 15

# Copiar modelo a la carpeta de Unity
cp pipeline_icefall/exp_scratch/ctc-epoch-30-avg-15.onnx \
   ASR/models/exported_onnx/icefall_model.onnx
```

---

# 📘 Guía 2: Fine-Tuning desde Checkpoint Preentrenado

Esta guía explica cómo hacer **fine-tuning** de un modelo Zipformer preentrenado
(LibriSpeech, WenetSpeech, etc.) para adaptarlo al corpus Uchumataqu.

> **¿Por qué fine-tuning?** Con solo ~50 minutos de audio Uchumataqu, el fine-tuning
> desde un modelo multilingüe preentrenado convergirá más rápido y con mejor PER final
> que entrenar desde cero.

### Paso 1: Preparar datos (igual que Guía 1, pasos 1 y 2)

```bash
python3 ASR/scripts/entrenamiento/preparar_asr.py
python3 ASR/scripts/entrenamiento/preparar_dataset.py
python3 ASR/pipeline_icefall/uchumataqu/prepare_uchumataqu.py
```

### Paso 2: Descargar un checkpoint preentrenado

Crea la carpeta de modelos preentrenados y descarga uno de estos:

```bash
mkdir -p ASR/pipeline_icefall/pretrained
cd ASR/pipeline_icefall/pretrained
```

**Opción A — Zipformer LibriSpeech (Inglés, transferencia general):**
```bash
wget -O librispeech_pretrained.pt \
  https://huggingface.co/Zengwei/icefall-asr-librispeech-zipformer-2023-05-15/resolve/main/exp/pretrained.pt
```

**Opción B — Zipformer WenetSpeech (Mandarín, excelente para lenguas no-europeas):**
```bash
wget -O wenetspeech_pretrained.pt \
  https://huggingface.co/csukuangfj/icefall-asr-zipformer-wenetspeech-20230615/resolve/main/exp/pretrained.pt
```

**Opción C — Zipformer Multilingüe (RECOMENDADO para Uchumataqu):**
```bash
# Disponible en el repositorio oficial de icefall en HuggingFace
# Ver: https://huggingface.co/k2-fsa
wget -O multilingual_pretrained.pt \
  https://huggingface.co/pkufool/icefall-asr-zipformer-multi-zh-hans-2023-9-2/resolve/main/exp/pretrained.pt
```

### Paso 3: Lanzar fine-tuning oficial

```bash
# Fine-tuning con checkpoint LibriSpeech
INIT_FILE=ASR/pipeline_icefall/pretrained/librispeech_pretrained.pt \
    bash ASR/pipeline_icefall/run_finetune.sh

# Con parámetros ajustados (LR más bajo para fine-tuning suave):
INIT_FILE=ASR/pipeline_icefall/pretrained/librispeech_pretrained.pt \
    INIT_LR=0.0001 NUM_EPOCHS=20 \
    bash ASR/pipeline_icefall/run_finetune.sh
```

El script llama internamente a:
```bash
python3 icefall_repo/egs/librispeech/ASR/zipformer/finetune.py \
    --init-file pretrained/librispeech_pretrained.pt \
    --exp-dir pipeline_icefall/exp_finetune \
    --num-epochs 20 \
    --base-lr 0.0003 \
    --manifest-dir ASR/data/lhotse \
    --tokens ASR/datos_asr/tokens.txt \
    ...
```

> **Sobre el vocabulario:** `finetune.py` reinicializa automáticamente la capa de
> clasificación CTC cuando el vocabulario es diferente (`--init-file` + `--tokens`),
> manteniendo el encoder preentrenado intacto.

### Paso 4: Evaluar el modelo fine-tuned

```bash
EPOCH=20 AVG=10 EXP_DIR=ASR/pipeline_icefall/exp_finetune \
    bash ASR/pipeline_icefall/run_decode.sh
```

### Paso 5: Exportar a ONNX

```bash
cd pipeline_icefall/icefall_repo
python3 egs/librispeech/ASR/zipformer/export-onnx-ctc.py \
    --exp-dir ../exp_finetune \
    --tokens ASR/datos_asr/tokens.txt \
    --epoch 20 --avg 10

cp pipeline_icefall/exp_finetune/ctc-epoch-20-avg-10.onnx \
   ASR/models/exported_onnx/icefall_model.onnx
```

---

## 📊 Comparación de Estrategias

| Estrategia | Tiempo estimado | PER esperado | GPU requerida |
|---|---|---|---|
| Desde cero (30 épocas) | ~8–12 h (V100) | 15–30% | ≥ 16 GB VRAM |
| Fine-tuning LibriSpeech (20 épocas) | ~3–5 h | 10–20% | ≥ 8 GB VRAM |
| Fine-tuning Multilingüe (15 épocas) | ~2–4 h | **5–15%** | ≥ 8 GB VRAM |

> Para corpus pequeños como Uchumataqu (~50 min), el **fine-tuning multilingüe es la mejor opción**.

---

## 🔗 Referencias

- [k2-fsa/icefall en GitHub](https://github.com/k2-fsa/icefall)
- [Documentación oficial de icefall](https://k2-fsa.github.io/icefall/)
- [Modelos preentrenados en HuggingFace (k2-fsa)](https://huggingface.co/k2-fsa)
- [Zipformer paper (Han et al., 2023)](https://arxiv.org/abs/2310.11230)
