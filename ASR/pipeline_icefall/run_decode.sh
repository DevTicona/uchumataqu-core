#!/usr/bin/env bash
# =============================================================================
# run_decode.sh
# Evaluación/decodificación oficial con decode.py de k2-fsa/icefall.
# Soporta múltiples métodos: greedy, modified-beam-search, fast-beam-search.
#
# Uso:
#   bash pipeline_icefall/run_decode.sh                        # usa exp_scratch/
#   bash pipeline_icefall/run_decode.sh --exp-dir exp_finetune # usa exp_finetune/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASR_DIR="$(dirname "$SCRIPT_DIR")"
ICEFALL_DIR="$SCRIPT_DIR/icefall_repo"
ZIPFORMER_DIR="$ICEFALL_DIR/egs/librispeech/ASR/zipformer"

if [ -d "$SCRIPT_DIR/exp_scratch_v2" ]; then
    EXP_DIR="${EXP_DIR:-$SCRIPT_DIR/exp_scratch_v2}"
else
    EXP_DIR="${EXP_DIR:-$SCRIPT_DIR/exp_scratch}"
fi
EPOCH="${EPOCH:-}"
AVG="${AVG:-5}"
MAX_DURATION="${MAX_DURATION:-100}"
EVAL_SET="${EVAL_SET:-test}"
CTC_BLANK_PENALTY="${CTC_BLANK_PENALTY:-0}"
USE_CTC="${USE_CTC:-1}"
USE_TRANSDUCER="${USE_TRANSDUCER:-0}"
OUTPUT_DOWNSAMPLING_FACTOR="${OUTPUT_DOWNSAMPLING_FACTOR:-1}"
LHOTSE_DIR="$ASR_DIR/data/lhotse"
TOKENS_FILE="$ASR_DIR/datos_asr/tokens.txt"
LANG_DIR="$ASR_DIR/data/lang_bpe"
BPE_MODEL="${BPE_MODEL:-$TOKENS_FILE}"

# Procesar argumentos de línea de comandos si se pasaron
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exp-dir)
            EXP_DIR="$2"
            shift 2
            ;;
        --epoch)
            EPOCH="$2"
            shift 2
            ;;
        --avg)
            AVG="$2"
            shift 2
            ;;
        --max-duration)
            MAX_DURATION="$2"
            shift 2
            ;;
        --eval-set)
            EVAL_SET="$2"
            shift 2
            ;;
        --ctc-blank-penalty)
            CTC_BLANK_PENALTY="$2"
            shift 2
            ;;
        --output-downsampling-factor)
            OUTPUT_DOWNSAMPLING_FACTOR="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# Convertir EXP_DIR a ruta absoluta ANTES del cd al directorio zipformer
# Si el usuario pasa una ruta relativa (ej: exp_finetune) se resuelve desde SCRIPT_DIR
if [[ "$EXP_DIR" != /* ]]; then
    EXP_DIR="$SCRIPT_DIR/$EXP_DIR"
fi

if [ -z "$EPOCH" ]; then
    EPOCH="$(find "$EXP_DIR" -maxdepth 1 -type f -name 'epoch-*.pt' -printf '%f\n' 2>/dev/null \
        | sed -E 's/^epoch-([0-9]+)\.pt$/\1/' \
        | sort -n \
        | tail -n 1)"
fi

if [ -z "$EPOCH" ]; then
    echo "[ERROR] No se encontró ningún checkpoint epoch-N.pt en: $EXP_DIR"
    exit 1
fi

if [ "$EVAL_SET" != "test" ] && [ "$EVAL_SET" != "val" ]; then
    echo "[ERROR] --eval-set debe ser 'test' o 'val', no '$EVAL_SET'."
    exit 1
fi

if [ "$AVG" -gt "$EPOCH" ]; then
    AVG="$EPOCH"
fi

echo "======================================================================"
echo "  DECODIFICACION OFICIAL (k2-fsa/icefall)"
echo "  Experimento: $EXP_DIR"
echo "  Época: $EPOCH | Avg: $AVG checkpoints | Split: $EVAL_SET"
echo "  Penalización CTC de blanco: $CTC_BLANK_PENALTY"
echo "======================================================================"

# Verificar manifests Lhotse
if [ ! -f "$LHOTSE_DIR/uchumataqu_cuts_test.jsonl.gz" ]; then
    echo "[ERROR] No se encontraron manifests Lhotse en: $LHOTSE_DIR"
    echo "  Ejecuta primero: python3 pipeline_icefall/uchumataqu/prepare_uchumataqu.py"
    exit 1
fi

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

cd "$ZIPFORMER_DIR"
export PYTHONPATH="$ZIPFORMER_DIR:$ICEFALL_DIR:${PYTHONPATH:-}"

echo ""
echo "[1/1] Decodificacion: greedy_search (CTC)"
"$PYTHON_BIN" "$ZIPFORMER_DIR/decode.py" \
    --epoch "$EPOCH" \
    --avg "$AVG" \
    --exp-dir "$EXP_DIR" \
    --max-duration "$MAX_DURATION" \
    --manifest-dir "$LHOTSE_DIR" \
    --bpe-model "$BPE_MODEL" \
    --lang-dir "$LANG_DIR" \
    --on-the-fly-feats 1 \
    --use-ctc "$USE_CTC" \
    --use-transducer "$USE_TRANSDUCER" \
    --output-downsampling-factor "$OUTPUT_DOWNSAMPLING_FACTOR" \
    --eval-set "$EVAL_SET" \
    --ctc-blank-penalty "$CTC_BLANK_PENALTY" \
    --decoding-method greedy_search \
    --use-averaged-model 0 \
    "$@"

echo ""
echo "======================================================================"
echo "  DECODIFICACION COMPLETADA."
echo "  Resultados en: $EXP_DIR/decoding-*/"
echo "======================================================================"
