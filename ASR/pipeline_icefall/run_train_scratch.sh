#!/usr/bin/env bash
# =============================================================================
# run_train_scratch.sh
# Entrenamiento de Zipformer desde CERO con las recetas oficiales de k2-fsa/icefall
# para el corpus Uchumataqu (Uru de Irohito).
#
# DATA AUGMENTATION:
#   1. Speed Perturbation  -> PerturbSpeed([0.9, 1.1], p=2/3)
#   2. MUSAN Noise Mixing  -> CutMix(musan_cuts, snr=10..20, p=0.5), opcional
#   3. SpecAugment         -> time_warp=80, freq_masks=2x27, time_masks=10x100
#
#   NOTA: Speed perturbation se muestrea por época (p=2/3); no triplica el
#   corpus en disco. La receta prioriza más actualizaciones con lotes menores.
#
# Prerequisitos:
#   1. pip install -r pipeline_icefall/icefall_repo/requirements.txt
#   2. pip install k2 lhotse kaldifeat
#   3. python3 scripts/entrenamiento/preparar_asr.py
#      python3 scripts/entrenamiento/preparar_dataset.py
#      python3 pipeline_icefall/uchumataqu/prepare_uchumataqu.py
#      python3 pipeline_icefall/uchumataqu/prepare_musan.py
#
# Uso:
#   bash pipeline_icefall/run_train_scratch.sh [--world-size 1] [--num-epochs 50]
# =============================================================================

set -euo pipefail

# Solucionar error "dubious ownership" de Git al correr como root en Docker
git config --global --add safe.directory '*'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASR_DIR="$(dirname "$SCRIPT_DIR")"
ICEFALL_DIR="$SCRIPT_DIR/icefall_repo"
ZIPFORMER_DIR="$ICEFALL_DIR/egs/librispeech/ASR/zipformer"

# Parámetros configurables
# NOTA: Para entrenamiento desde 0 con corpus pequeño se usan más épocas
# y max_duration mayor que en fine-tuning, junto con augmentación completa.
WORLD_SIZE="${WORLD_SIZE:-1}"
# A 100-second batch produces roughly twice as many optimizer updates per
# epoch as the previous 200-second batch.  For this 1.4-hour corpus that is
# more valuable than a larger batch and it fit well within the previous run's
# GPU memory budget.
NUM_EPOCHS="${NUM_EPOCHS:-100}"
MAX_DURATION="${MAX_DURATION:-100}"
BASE_LR="${BASE_LR:-0.045}"
EXP_DIR="${EXP_DIR:-$SCRIPT_DIR/exp_scratch_v2}"
LHOTSE_DIR="$ASR_DIR/data/lhotse"
TOKENS_FILE="$ASR_DIR/datos_asr/tokens.txt"
MANIFEST_DIR="$ASR_DIR/data/manifests"
LANG_DIR="$ASR_DIR/data/lang_bpe"
BPE_MODEL="${BPE_MODEL:-$TOKENS_FILE}"
USE_CTC="${USE_CTC:-1}"
USE_TRANSDUCER="${USE_TRANSDUCER:-0}"
OUTPUT_DOWNSAMPLING_FACTOR="${OUTPUT_DOWNSAMPLING_FACTOR:-1}"

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

# ── Configuración de Data Augmentation ───────────────────────────────────────
# Speed y SpecAugment permanecen activos. MUSAN se habilita únicamente si el
# audio de destino incluye ruido comparable (ENABLE_MUSAN=1).
ENABLE_SPEED_PERTURB=1   # Speed x0.9 y x1.1 (efecto: triplica el corpus)
ENABLE_MUSAN="${ENABLE_MUSAN:-1}"  # Activo por defecto: mezcla ruido/música/habla con SNR 10-20 dB (p=0.5)
ENABLE_SPEC_AUG=1        # SpecAugment enmascarado espectrograma
SPEC_AUG_TIME_WARP=80    # Recomendado por paper SpecAugment original
MUSAN_CUTS="$LHOTSE_DIR/musan_cuts.jsonl.gz"

# Pitch Perturbation / Shifting: amplía el corpus con variaciones de tono
#   (+2.0 st femenina/aguda, +4.0 st infantil/niños, -2.0 st masculina profunda)
ENABLE_PITCH_AUG="${ENABLE_PITCH_AUG:-1}"
PITCH_CUTS="$LHOTSE_DIR/uchumataqu_cuts_train_pitch.jsonl.gz"

# Concatenación de Cortes (CutConcatenate): une palabras aisladas con pausas/silencios
CONCATENATE_CUTS="${CONCATENATE_CUTS:-0}"
CONCAT_GAP="${CONCAT_GAP:-0.3}"
CONCAT_DURATION_FACTOR="${CONCAT_DURATION_FACTOR:-1.0}"
# ─────────────────────────────────────────────────────────────────────────────
 
echo "======================================================================"
echo "  ENTRENAMIENTO ZIPFORMER OFICIAL (k2-fsa/icefall) — DESDE CERO"
echo "  Repositorio: $ICEFALL_DIR"
echo "  Experimento: $EXP_DIR"
echo "  Épocas: $NUM_EPOCHS | Batch max_duration: $MAX_DURATION s | LR base: $BASE_LR"
echo "  Data Augmentation:"
echo "    Speed Perturbation : $ENABLE_SPEED_PERTURB (x0.9, x1.1 on-the-fly)"
echo "    Pitch Shifting     : $ENABLE_PITCH_AUG (+2.0, +4.0, -2.0 semitonos / infantil)"
echo "    MUSAN Noise Mixing : $ENABLE_MUSAN (SNR 10-20 dB, p=0.5)"
echo "    SpecAugment        : $ENABLE_SPEC_AUG (time_warp=$SPEC_AUG_TIME_WARP)"
echo "======================================================================"

# 1. Generar Pitch Augmentation si está habilitado y aún no existe
if [ "$ENABLE_PITCH_AUG" = "1" ] && [ ! -f "$PITCH_CUTS" ]; then
    echo "[PASO PREVIO] Generando dataset aumentado por Pitch Shifting para voces infantiles/agudas..."
    "$PYTHON_BIN" "$SCRIPT_DIR/uchumataqu/prepare_pitch_augmentation.py" \
        --manifests_dir "$MANIFEST_DIR" \
        --output_lhotse_dir "$LHOTSE_DIR"
fi

# 1b. Verificar prerrequisitos de Lhotse y Lang
if [ ! -f "$LHOTSE_DIR/uchumataqu_cuts_train.jsonl.gz" ] || [ ! -f "$LANG_DIR/words.txt" ]; then
    echo "[PASO PREVIO] Generando manifests Lhotse y directorio lang_bpe..."
    "$PYTHON_BIN" "$SCRIPT_DIR/uchumataqu/prepare_uchumataqu.py" \
        --manifests_dir "$MANIFEST_DIR" \
        --output_dir "$LHOTSE_DIR" \
        --lang_dir "$LANG_DIR" \
        --use_pitch_aug "$ENABLE_PITCH_AUG"
else
    # Asegurar que los aliases apunten a la versión deseada (pitch o estándar)
    "$PYTHON_BIN" -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR/uchumataqu')
from prepare_uchumataqu import crear_aliases_receta_librispeech
crear_aliases_receta_librispeech('$LHOTSE_DIR', use_pitch_aug=($ENABLE_PITCH_AUG == 1))
"
fi

# 1b. Verificar y generar manifest de MUSAN (para noise augmentation)
if [ "$ENABLE_MUSAN" = "1" ] && [ ! -f "$MUSAN_CUTS" ]; then
    echo "[PASO PREVIO] Generando manifest MUSAN para data augmentation..."
    "$PYTHON_BIN" "$SCRIPT_DIR/uchumataqu/prepare_musan.py" \
        --output-dir "$LHOTSE_DIR"
    if [ ! -f "$MUSAN_CUTS" ]; then
        echo "[AVISO] No se pudo generar musan_cuts.jsonl.gz. Desactivando MUSAN."
        ENABLE_MUSAN=0
    fi
fi

# 2. Verificar tokens.txt
if [ ! -f "$TOKENS_FILE" ]; then
    echo "[ERROR] No se encontró tokens.txt en: $TOKENS_FILE"
    echo "  Ejecuta primero: python3 scripts/entrenamiento/preparar_asr.py"
    exit 1
fi

# 3. Crear directorio de experimento
mkdir -p "$EXP_DIR"

echo ""
echo "[INFO] Iniciando entrenamiento Zipformer desde cero (CTC)..."
echo ""

# 4. Lanzar entrenamiento oficial de icefall
cd "$ZIPFORMER_DIR"
export PYTHONPATH="$ZIPFORMER_DIR:$ICEFALL_DIR:${PYTHONPATH:-}"

"$PYTHON_BIN" "$ZIPFORMER_DIR/train.py" \
    --world-size "$WORLD_SIZE" \
    --num-epochs "$NUM_EPOCHS" \
    --start-epoch 1 \
    --use-ctc "$USE_CTC" \
    --use-transducer "$USE_TRANSDUCER" \
    --output-downsampling-factor "$OUTPUT_DOWNSAMPLING_FACTOR" \
    --exp-dir "$EXP_DIR" \
    --base-lr "$BASE_LR" \
    --use-fp16 1 \
    --max-duration "$MAX_DURATION" \
    --manifest-dir "$LHOTSE_DIR" \
    --bpe-model "$BPE_MODEL" \
    --on-the-fly-feats "$ENABLE_SPEED_PERTURB" \
    --enable-musan "$ENABLE_MUSAN" \
    --enable-spec-aug "$ENABLE_SPEC_AUG" \
    --spec-aug-time-warp-factor "$SPEC_AUG_TIME_WARP" \
    --concatenate-cuts "$CONCATENATE_CUTS" \
    --gap "$CONCAT_GAP" \
    --duration-factor "$CONCAT_DURATION_FACTOR" \
    --drop-last 0 \
    --num-buckets 6 \
    --log-interval 10 \
    --keep-last-k-epochs 5 \
    --master-port 12355 \
    "$@"

echo ""
echo "======================================================================"
echo "  ENTRENAMIENTO COMPLETADO."
echo "  Checkpoints en: $EXP_DIR/"
echo ""
echo "  Próximos pasos:"
echo "    1. Evaluar:  bash pipeline_icefall/run_decode.sh"
echo "    2. Exportar: bash pipeline_icefall/run_export.sh"
echo "======================================================================"
