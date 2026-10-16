#!/usr/bin/env bash
# =============================================================================
# run_finetune.sh
# Fine-tuning de un modelo Zipformer preentrenado con las recetas OFICIALES de
# k2-fsa/icefall para adaptar al corpus Uchumataqu (Uru de Irohito).
#
# DATA AUGMENTATION (equivalente a Kaldi pero en Lhotse):
#   1. Speed Perturbation  -> on-the-fly via PerturbSpeed([0.9, 1.1])
#      Kaldi equiv: perturb_speed.sh
#   2. MUSAN Noise Mixing  -> CutMix(musan_cuts, snr=10..20, p=0.5), opcional
#      Kaldi equiv: steps/data/augment_data_dir.py
#   3. SpecAugment         -> time warp + freq masking + time masking
#      (no existe en Kaldi clásico, mejora ~5-10% WER)
#
# Modelos preentrenados recomendados:
#   Modelo A: Zipformer WenetSpeech (Mandarin/Multilingual)
#     wget https://huggingface.co/csukuangfj/icefall-asr-zipformer-wenetspeech-20230615/resolve/main/exp/pretrained.pt
#   Modelo B: Zipformer LibriSpeech 2023-05-15 (Inglés, buena transferencia)
#     wget https://huggingface.co/Zengwei/icefall-asr-librispeech-zipformer-2023-05-15/resolve/main/exp/pretrained.pt
#   Modelo C: ZIPA small (Defecto — ya en pretrained/zipa-cr-s/)
#
# Prerequisitos:
#   1. pip install -r pipeline_icefall/icefall_repo/requirements.txt
#   2. pip install k2 lhotse kaldifeat
#   3. python3 scripts/entrenamiento/preparar_asr.py
#      python3 scripts/entrenamiento/preparar_dataset.py
#      python3 pipeline_icefall/uchumataqu/prepare_uchumataqu.py
#      python3 pipeline_icefall/uchumataqu/prepare_musan.py
#   4. Descargar un checkpoint preentrenado (ver modelos arriba)
#
# Uso:
#   INIT_FILE=/ruta/al/pretrained.pt bash pipeline_icefall/run_finetune.sh
# =============================================================================

set -euo pipefail

# Solucionar error "dubious ownership" de Git al correr como root en Docker
git config --global --add safe.directory '*'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASR_DIR="$(dirname "$SCRIPT_DIR")"
ICEFALL_DIR="$SCRIPT_DIR/icefall_repo"
ZIPFORMER_DIR="$ICEFALL_DIR/egs/librispeech/ASR/zipformer"

# Python ejecutable (preferir entorno conda proyecto_grado si existe)
if [ -x "/home/primo/miniconda3/envs/proyecto_grado/bin/python" ]; then
    PYTHON_BIN="${PYTHON_BIN:-/home/primo/miniconda3/envs/proyecto_grado/bin/python}"
    NVIDIA_LIBS=$(find /home/primo/miniconda3/envs/proyecto_grado/lib/python3.12/site-packages/nvidia -type d -name "lib" 2>/dev/null | paste -sd ":" -)
    if [ -n "$NVIDIA_LIBS" ]; then
        export LD_LIBRARY_PATH="$NVIDIA_LIBS:${LD_LIBRARY_PATH:-}"
    fi
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

# Parámetros configurables
WORLD_SIZE="${WORLD_SIZE:-1}"
# The target CTC head is deliberately not loaded: ZIPA has 127 output symbols
# while Uchumataqu has 42.  It therefore needs enough updates to learn from
# scratch, even though the acoustic encoder is pretrained.
NUM_EPOCHS="${NUM_EPOCHS:-50}"
MAX_DURATION="${MAX_DURATION:-100}"
# Keep the recipe's official fine-tuning learning rate.  The former 3e-4
# produced an effective LR of 1.5e-4 in epoch 1 and left the new CTC head
# essentially untrained, resulting in all-blank hypotheses.
INIT_LR="${INIT_LR:-0.0045}"
EXP_DIR="${EXP_DIR:-$SCRIPT_DIR/exp_finetune_v2}"
LHOTSE_DIR="$ASR_DIR/data/lhotse"
TOKENS_FILE="$ASR_DIR/datos_asr/tokens.txt"
MANIFEST_DIR="$ASR_DIR/data/manifests"
LANG_DIR="$ASR_DIR/data/lang_bpe"
BPE_MODEL="${BPE_MODEL:-$TOKENS_FILE}"
OUTPUT_DOWNSAMPLING_FACTOR="${OUTPUT_DOWNSAMPLING_FACTOR:-1}"

# ── Configuración de Data Augmentation ───────────────────────────────────────
# Speed Perturbation: activo cuando on-the-fly-feats=1
#   Aplica 0.9x y 1.1x al corpus de forma aleatoria (p=2/3 por época)
#   Equivalente a perturb_speed.sh de Kaldi
ENABLE_SPEED_PERTURB=1   # 1=activo (requiere --on-the-fly-feats 1)

# MUSAN Noise Mixing: mezcla ruido/música/habla fondo con SNR 10-20 dB.
#   Por defecto se desactiva para establecer una línea base limpia.
# The training and evaluation recordings are clean and very short.  Start the
# new CTC head with clean speech; MUSAN can be enabled explicitly after a
# stable baseline has been established.
ENABLE_MUSAN="${ENABLE_MUSAN:-0}"
MUSAN_CUTS="$LHOTSE_DIR/musan_cuts.jsonl.gz"

# SpecAugment: enmascarado de frecuencias y tiempo en el espectrograma
#   time_warp_factor=80 es el valor recomendado por el paper original
#   No tiene equivalente directo en Kaldi
ENABLE_SPEC_AUG=1
SPEC_AUG_TIME_WARP=80
# ─────────────────────────────────────────────────────────────────────────────

# Checkpoint preentrenado ZIPA — ubicado directamente en pipeline_icefall/pretrained/
ZIPA_DEFAULT_CKPT="$SCRIPT_DIR/pretrained/zipa-cr-s/zipa_small_crctc_500000_avg10.pth"
INIT_FILE="${INIT_FILE:-$ZIPA_DEFAULT_CKPT}"

echo "======================================================================"
echo "  FINE-TUNING ZIPFORMER OFICIAL (k2-fsa/icefall)"
echo "  Corpus: Uchumataqu (Uru de Irohito)"
echo "  Checkpoint base: $INIT_FILE"
echo "  Experimento: $EXP_DIR"
echo "  Épocas: $NUM_EPOCHS | LR inicial: $INIT_LR | Max Duration: $MAX_DURATION s"
echo "  Python: $PYTHON_BIN"
echo "  Data Augmentation:"
echo "    Speed Perturbation : $ENABLE_SPEED_PERTURB (x0.9, x1.1 on-the-fly)"
echo "    MUSAN Noise Mixing : $ENABLE_MUSAN (SNR 10-20 dB, p=0.5)"
echo "    SpecAugment        : $ENABLE_SPEC_AUG (time_warp=$SPEC_AUG_TIME_WARP)"
echo "======================================================================"

# 1. Verificar checkpoint preentrenado
if [ ! -f "$INIT_FILE" ]; then
    echo "[ERROR] No se encontró el checkpoint preentrenado en: $INIT_FILE"
    echo "  Asegúrate de que existe el archivo o pasa INIT_FILE=/ruta/al/modelo.pth"
    exit 1
fi

# 2. Verificar manifests Lhotse y directorio lang_bpe
if [ ! -f "$LHOTSE_DIR/uchumataqu_cuts_train.jsonl.gz" ] || [ ! -f "$LANG_DIR/words.txt" ] || [ ! -f "$BPE_MODEL" ]; then
    echo "[PASO PREVIO] Generando manifests Lhotse y directorio lang_bpe..."
    "$PYTHON_BIN" "$SCRIPT_DIR/uchumataqu/prepare_uchumataqu.py" \
        --manifests_dir "$MANIFEST_DIR" \
        --output_dir "$LHOTSE_DIR" \
        --lang_dir "$LANG_DIR"
fi

# 2b. Verificar y generar manifest de MUSAN (para noise augmentation)
if [ "$ENABLE_MUSAN" = "1" ] && [ ! -f "$MUSAN_CUTS" ]; then
    echo "[PASO PREVIO] Generando manifest MUSAN para data augmentation..."
    "$PYTHON_BIN" "$SCRIPT_DIR/uchumataqu/prepare_musan.py" \
        --output-dir "$LHOTSE_DIR"
    if [ ! -f "$MUSAN_CUTS" ]; then
        echo "[AVISO] No se pudo generar musan_cuts.jsonl.gz. Desactivando MUSAN."
        ENABLE_MUSAN=0
    fi
fi

# 3. Crear directorio de experimento
mkdir -p "$EXP_DIR"

echo ""
echo "[INFO] Iniciando fine-tuning Zipformer con checkpoint: $INIT_FILE"
echo ""

# 4. Lanzar fine-tuning oficial de icefall
cd "$ZIPFORMER_DIR"
export PYTHONPATH="$ZIPFORMER_DIR:$ICEFALL_DIR:${PYTHONPATH:-}"

"$PYTHON_BIN" "$ZIPFORMER_DIR/finetune.py" \
    --world-size "$WORLD_SIZE" \
    --num-epochs "$NUM_EPOCHS" \
    --start-epoch 1 \
    --do-finetune 1 \
    --finetune-ckpt "$INIT_FILE" \
    --init-modules encoder \
    --use-ctc 1 \
    --use-transducer 0 \
    --output-downsampling-factor "$OUTPUT_DOWNSAMPLING_FACTOR" \
    --exp-dir "$EXP_DIR" \
    --base-lr "$INIT_LR" \
    --use-fp16 1 \
    --max-duration "$MAX_DURATION" \
    --manifest-dir "$LHOTSE_DIR" \
    --bpe-model "$BPE_MODEL" \
    --on-the-fly-feats "$ENABLE_SPEED_PERTURB" \
    --enable-musan "$ENABLE_MUSAN" \
    --enable-spec-aug "$ENABLE_SPEC_AUG" \
    --spec-aug-time-warp-factor "$SPEC_AUG_TIME_WARP" \
    --drop-last 0 \
    --num-buckets 6 \
    --log-interval 10 \
    --keep-last-k-epochs 5 \
    --master-port 12356 \
    "$@"

echo ""
echo "======================================================================"
echo "  FINE-TUNING COMPLETADO."
echo "  Checkpoints en: $EXP_DIR/"
echo ""
echo "  Próximos pasos:"
echo "    1. Evaluar:  bash pipeline_icefall/run_decode.sh --exp-dir $EXP_DIR"
echo "    2. Exportar: bash pipeline_icefall/run_export.sh --exp-dir $EXP_DIR"
echo "======================================================================"
