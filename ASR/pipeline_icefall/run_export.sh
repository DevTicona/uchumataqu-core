#!/usr/bin/env bash
# =============================================================================
# run_export.sh
# Exportación oficial a ONNX (CTC) para Sherpa-onnx (Unity / Android)
# utilizando la receta oficial de k2-fsa/icefall (export-onnx-ctc.py).
#
# Uso:
#   bash pipeline_icefall/run_export.sh                        # usa exp_scratch/
#   bash pipeline_icefall/run_export.sh --exp-dir exp_finetune # usa exp_finetune/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASR_DIR="$(dirname "$SCRIPT_DIR")"
ICEFALL_DIR="$SCRIPT_DIR/icefall_repo"
ZIPFORMER_DIR="$ICEFALL_DIR/egs/librispeech/ASR/zipformer"

EXP_DIR="${EXP_DIR:-$SCRIPT_DIR/exp_finetune}"
EPOCH="${EPOCH:-25}"
AVG="${AVG:-5}"
OUTPUT_DOWNSAMPLING_FACTOR="${OUTPUT_DOWNSAMPLING_FACTOR:-1}"
TOKENS_FILE="${TOKENS_FILE:-$ASR_DIR/data/lang_bpe/tokens.txt}"
LEXICON_FILE="$ASR_DIR/datos_asr/lexicon.txt"
OUTPUT_DIR="$ASR_DIR/models/exported_onnx"

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
        --tokens)
            TOKENS_FILE="$2"
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

echo "======================================================================"
echo "  EXPORTACIÓN OFICIAL A ONNX (k2-fsa/icefall) — SHERPA-ONNX RUNTIME"
echo "  Experimento: $EXP_DIR"
echo "  Época: $EPOCH | Avg: $AVG | Tokens: $TOKENS_FILE"
echo "  Salida ONNX: $OUTPUT_DIR"
echo "======================================================================"

# Convertir EXP_DIR a ruta absoluta ANTES del cd al directorio zipformer
if [[ "$EXP_DIR" != /* ]]; then
    EXP_DIR="$SCRIPT_DIR/$EXP_DIR"
fi

if [ ! -f "$TOKENS_FILE" ]; then
    echo "[ERROR] tokens.txt no encontrado en: $TOKENS_FILE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

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
echo "[1/2] Exportando checkpoint a ONNX con la receta oficial..."
"$PYTHON_BIN" "$ZIPFORMER_DIR/export-onnx-ctc.py" \
    --use-transducer 0 \
    --use-ctc 1 \
    --output-downsampling-factor "$OUTPUT_DOWNSAMPLING_FACTOR" \
    --tokens "$TOKENS_FILE" \
    --epoch "$EPOCH" \
    --avg "$AVG" \
    --exp-dir "$EXP_DIR" \
    "$@"

echo ""
echo "[2/2] Sincronizando artefactos para Sherpa-onnx en Unity..."
if [ -f "$EXP_DIR/model.onnx" ]; then
    cp "$EXP_DIR/model.onnx" "$OUTPUT_DIR/model.onnx"
    echo "  [OK] Copiado: $OUTPUT_DIR/model.onnx"
fi

if [ -f "$EXP_DIR/model.int8.onnx" ]; then
    cp "$EXP_DIR/model.int8.onnx" "$OUTPUT_DIR/model.int8.onnx"
    echo "  [OK] Copiado: $OUTPUT_DIR/model.int8.onnx (cuantizado INT8)"
fi

cp "$TOKENS_FILE" "$OUTPUT_DIR/tokens.txt"
echo "  [OK] Copiado: $OUTPUT_DIR/tokens.txt"

if [ -f "$LEXICON_FILE" ]; then
    cp "$LEXICON_FILE" "$OUTPUT_DIR/lexicon.txt"
    echo "  [OK] Copiado: $OUTPUT_DIR/lexicon.txt"
fi

echo ""
echo "======================================================================"
echo "  EXPORTACIÓN COMPLETADA CON ÉXITO."
echo "  Archivos listos para Unity (Sherpa-onnx) en: $OUTPUT_DIR/"
echo "======================================================================"
