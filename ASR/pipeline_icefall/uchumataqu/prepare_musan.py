"""
prepare_musan.py
Genera el manifest Lhotse de MUSAN (musan_cuts.jsonl.gz) a partir del
directorio local /home/primo/proyecto-grado/musan/, sin necesidad de
re-descargarlo.

MUSAN es el dataset de ruido/música/habla usado por las recetas oficiales
de icefall para data augmentation (CutMix en asr_datamodule.py).

Equivalente Kaldi: steps/data/augment_data_dir.py con noise y music.

Salida: ASR/data/lhotse/musan_cuts.jsonl.gz
  -> Leído por asr_datamodule.py cuando --enable-musan 1

Uso:
  python3 ASR/pipeline_icefall/uchumataqu/prepare_musan.py
  python3 ASR/pipeline_icefall/uchumataqu/prepare_musan.py --musan-dir /ruta/a/musan
"""

import os
import sys
import gzip
import json
import wave
import struct
import argparse
import contextlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas por defecto
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PIPELINE_DIR = _SCRIPT_DIR.parent
_ASR_DIR = _PIPELINE_DIR.parent
_PROJECT_ROOT = _ASR_DIR.parent

DEFAULT_MUSAN_DIR = _PROJECT_ROOT / "musan"
DEFAULT_OUTPUT_DIR = _ASR_DIR / "data" / "lhotse"


# ---------------------------------------------------------------------------
# Utilidades de audio
# ---------------------------------------------------------------------------
def get_wav_duration(path: str) -> float:
    """Devuelve la duración en segundos de un WAV sin librerías externas."""
    try:
        with contextlib.closing(wave.open(path, "r")) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except Exception:
        return 0.0


def get_wav_num_samples(path: str) -> int:
    """Devuelve el número de muestras de un WAV."""
    try:
        with contextlib.closing(wave.open(path, "r")) as f:
            return f.getnframes()
    except Exception:
        return 0


def get_wav_sample_rate(path: str) -> int:
    """Devuelve la tasa de muestreo de un WAV."""
    try:
        with contextlib.closing(wave.open(path, "r")) as f:
            return f.getframerate()
    except Exception:
        return 16000


# ---------------------------------------------------------------------------
# Construcción de cuts Lhotse
# ---------------------------------------------------------------------------
def build_musan_cut(wav_path: str, cut_id: str, category: str) -> dict:
    """
    Construye un objeto Cut de Lhotse para un archivo WAV de MUSAN.

    Estructura compatible con lhotse.CutSet.from_jsonl_lazy()
    y con CutMix() usado en asr_datamodule.py.
    """
    duration = get_wav_duration(wav_path)
    num_samples = get_wav_num_samples(wav_path)
    sample_rate = get_wav_sample_rate(wav_path)

    if duration <= 0.0:
        return None

    cut = {
        "type": "MonoCut",
        "id": cut_id,
        "start": 0.0,
        "duration": duration,
        "channel": 0,
        "supervisions": [],
        "recording": {
            "id": cut_id,
            "sources": [
                {
                    "type": "file",
                    "channels": [0],
                    "source": wav_path
                }
            ],
            "sampling_rate": sample_rate,
            "num_samples": num_samples,
            "duration": duration,
            "channel_ids": [0]
        },
        "custom": {"musan_category": category}
    }
    return cut


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------
def preparar_musan(musan_dir: Path, output_dir: Path) -> int:
    """
    Recorre las subcarpetas noise/, music/ y speech/ de MUSAN y escribe
    musan_cuts.jsonl.gz en output_dir.

    Returns el número total de cuts generados.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "musan_cuts.jsonl.gz"

    # Categorías MUSAN: noise, music, speech
    categories = ["noise", "music", "speech"]

    total = 0
    skipped = 0
    idx = 0

    print(f"\n[INFO] Escaneando MUSAN en: {musan_dir}")

    with gzip.open(str(out_path), "wt", encoding="utf-8") as gz_out:
        for category in categories:
            cat_dir = musan_dir / category
            if not cat_dir.exists():
                print(f"  [AVISO] Categoría no encontrada: {cat_dir}  (omitida)")
                continue

            # Buscar todos los .wav en la categoría (incluyendo subcarpetas)
            wav_files = sorted(cat_dir.rglob("*.wav"))
            n_cat = 0

            for wav_path in wav_files:
                cut_id = f"musan-{category}-{idx:06d}"
                cut = build_musan_cut(str(wav_path), cut_id, category)

                if cut is None:
                    skipped += 1
                    continue

                gz_out.write(json.dumps(cut, ensure_ascii=False) + "\n")
                n_cat += 1
                total += 1
                idx += 1

            print(f"  [{category:6s}] {n_cat:5d} archivos WAV procesados")

    print(f"\n[OK] {total} cuts MUSAN generados -> {out_path}")
    if skipped > 0:
        print(f"     {skipped} archivos omitidos (duración 0 o WAV inválido)")

    return total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=(
            "Genera musan_cuts.jsonl.gz para data augmentation en icefall.\n"
            "Equivalente a lhotse.recipes.prepare_musan() pero offline."
        )
    )
    parser.add_argument(
        "--musan-dir",
        type=Path,
        default=DEFAULT_MUSAN_DIR,
        help=f"Directorio raíz de MUSAN (default: {DEFAULT_MUSAN_DIR})"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida para musan_cuts.jsonl.gz (default: {DEFAULT_OUTPUT_DIR})"
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  PREPARACIÓN DE MUSAN PARA DATA AUGMENTATION (icefall/lhotse)")
    print("=" * 65)

    if not args.musan_dir.exists():
        print(f"\n[ERROR] No se encontró el directorio MUSAN: {args.musan_dir}")
        print("  Descarga MUSAN desde: http://www.openslr.org/17/")
        sys.exit(1)

    n = preparar_musan(args.musan_dir, args.output_dir)

    print("\n" + "=" * 65)
    print(f"  MUSAN listo: {n} cuts en {args.output_dir / 'musan_cuts.jsonl.gz'}")
    print("=" * 65)
    print("\n  Para activar MUSAN en entrenamiento:")
    print("    --enable-musan 1   en run_finetune.sh / run_train_scratch.sh")


if __name__ == "__main__":
    main()
