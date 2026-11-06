"""
prepare_pitch_augmentation.py
Genera aumento de datos acústicos por desplazamiento de tono (Pitch Shifting)
para el corpus de entrenamiento de Uchumataqu (Uru de Irohito).

Objetivo:
  Simular variaciones de frecuencia fundamental (F0) y formantes para extender
  la robustez acústica del modelo Zipformer ante voces infantiles y agudas que
  no están representadas entre los hablantes adultos del corpus nativo.

Transformaciones por defecto (en semitonos / cents):
  - +2.0 semitonos (+200 cents): Voces adultas agudas / femeninas
  - +4.0 semitonos (+400 cents): Voces infantiles / niños (F0 ~ 250 - 350 Hz)
  - -2.0 semitonos (-200 cents): Voces masculinas profundas (F0 ~ 90 - 120 Hz)

Salidas:
  - Archivos de audio en: ASR/data/audio_augmented/pitch/
  - Manifest ampliado en: ASR/data/manifests/train_manifest_pitch.json
  - Cortes Lhotse en:     ASR/data/lhotse/uchumataqu_cuts_train_pitch.jsonl.gz

Uso:
  python3 ASR/pipeline_icefall/uchumataqu/prepare_pitch_augmentation.py
  python3 ASR/pipeline_icefall/uchumataqu/prepare_pitch_augmentation.py --semitones 2.0 4.0 -2.0 --num_workers 8
"""

import os
import sys
import json
import gzip
import wave
import shutil
import argparse
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Tuple

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
PIPELINE_DIR = SCRIPT_DIR.parent
ASR_DIR = PIPELINE_DIR.parent
PROJECT_ROOT = ASR_DIR.parent

DEFAULT_MANIFESTS_DIR = ASR_DIR / "data" / "manifests"
DEFAULT_OUTPUT_AUDIO_DIR = ASR_DIR / "data" / "audio_augmented" / "pitch"
DEFAULT_OUTPUT_LHOTSE_DIR = ASR_DIR / "data" / "lhotse"


def get_wav_info(path: str) -> Tuple[float, int, int]:
    """Retorna (duracion_segundos, num_muestras, sample_rate)."""
    with wave.open(path, "rb") as wf:
        nframes = wf.getnframes()
        sr = wf.getframerate()
        duration = nframes / float(sr) if sr > 0 else 0.0
        return duration, nframes, sr


def aplicar_pitch_sox(input_path: str, output_path: str, cents: int) -> bool:
    """Aplica pitch shifting usando sox CLI."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = ["sox", input_path, output_path, "pitch", str(cents)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        return False


def aplicar_pitch_ffmpeg(input_path: str, output_path: str, semitones: float) -> bool:
    """Fallback con ffmpeg si sox no está disponible."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # factor = 2^(semitones / 12)
    ratio = 2.0 ** (semitones / 12.0)
    # asetrate escala pitch y velocidad; atempo compensa la velocidad manteniendo el nuevo pitch
    filter_str = f"asetrate=16000*{ratio:.6f},atempo={1.0 / ratio:.6f},aresample=16000"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-af", filter_str, output_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def procesar_un_audio(args_tuple) -> Tuple[bool, dict]:
    """Tarea de procesamiento para un archivo y un factor de pitch."""
    entry, semitone, output_base_dir, force, backend = args_tuple
    cents = int(round(semitone * 100))
    cents_str = f"p{cents:+d}"
    
    orig_audio_path = entry.get("audio_path", "")
    if not os.path.isabs(orig_audio_path):
        orig_audio_path = str(PROJECT_ROOT / orig_audio_path)
    
    if not os.path.exists(orig_audio_path):
        return False, None

    orig_utt_id = entry.get("utt_id", "utt")
    new_utt_id = f"{orig_utt_id}_{cents_str}"
    
    rel_folder = f"pitch_{cents:+d}"
    out_filename = f"{new_utt_id}.wav"
    dest_path = str(output_base_dir / rel_folder / out_filename)

    # Reusar archivo existente si no se fuerza la regeneración
    exito = True
    if force or not os.path.exists(dest_path) or os.path.getsize(dest_path) < 100:
        if backend == "sox":
            exito = aplicar_pitch_sox(orig_audio_path, dest_path, cents)
            if not exito:
                exito = aplicar_pitch_ffmpeg(orig_audio_path, dest_path, semitone)
        else:
            exito = aplicar_pitch_ffmpeg(orig_audio_path, dest_path, semitone)

    if not exito or not os.path.exists(dest_path):
        return False, None

    try:
        dur, n_samples, sr = get_wav_info(dest_path)
    except Exception:
        return False, None

    # Clonar y adaptar la entrada para el nuevo manifest
    new_entry = dict(entry)
    new_entry["utt_id"] = new_utt_id
    new_entry["audio_path"] = dest_path
    new_entry["audio_rel_path"] = str(Path(dest_path).relative_to(PROJECT_ROOT)) if str(dest_path).startswith(str(PROJECT_ROOT)) else dest_path
    new_entry["duracion"] = round(dur, 4)
    new_entry["locutor"] = f"{entry.get('locutor', 'spk')}_{cents_str}"
    new_entry["pitch_shift_cents"] = cents
    new_entry["pitch_shift_semitones"] = semitone

    return True, new_entry


def convertir_entry_a_lhotse_cut(entry: dict, cut_idx: int) -> dict:
    """Convierte una entrada de manifest a un corte Lhotse MonoCut."""
    utt_id = entry.get("utt_id", f"uch_pitch_{cut_idx:06d}")
    audio_path = entry.get("audio_path", "")
    duracion = float(entry.get("duracion", 0.0))
    locutor = entry.get("locutor", "unknown")
    fonemas = entry.get("fonemas", "")
    texto_uch = entry.get("texto_uch", "")
    texto_es = entry.get("texto_es", "")
    tipo = entry.get("tipo", "palabra")
    toma = entry.get("toma", 1)

    return {
        "type": "MonoCut",
        "id": utt_id,
        "start": 0.0,
        "duration": duracion,
        "channel": 0,
        "supervisions": [
            {
                "id": utt_id,
                "recording_id": utt_id,
                "start": 0.0,
                "duration": duracion,
                "channel": 0,
                "text": fonemas,
                "speaker": locutor,
                "language": "Uchumataqu",
                "custom": {
                    "text_words": texto_uch,
                    "texto_es": texto_es,
                    "tipo": tipo,
                    "toma": toma,
                    "pitch_shift_cents": entry.get("pitch_shift_cents", 0)
                }
            }
        ],
        "recording": {
            "id": utt_id,
            "sources": [
                {
                    "type": "file",
                    "channels": [0],
                    "source": audio_path
                }
            ],
            "sampling_rate": 16000,
            "num_samples": int(round(duracion * 16000)),
            "duration": duracion,
            "channel_ids": [0]
        },
        "custom": {
            "speaker": locutor,
            "tipo": tipo,
            "augmented": True if entry.get("pitch_shift_cents", 0) != 0 else False
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Data Augmentation por Pitch Shifting para Uchumataqu ASR (Lhotse)")
    parser.add_argument("--manifests_dir", type=str, default=str(DEFAULT_MANIFESTS_DIR), help="Directorio con train_manifest.json")
    parser.add_argument("--output_audio_dir", type=str, default=str(DEFAULT_OUTPUT_AUDIO_DIR), help="Directorio para WAVs aumentados")
    parser.add_argument("--output_lhotse_dir", type=str, default=str(DEFAULT_OUTPUT_LHOTSE_DIR), help="Directorio para cuts Lhotse")
    parser.add_argument("--semitones", type=float, nargs="+", default=[2.0, 4.0, -2.0], help="Factores de desplazamiento en semitonos (+2=femenina, +4=infantil, -2=grave)")
    parser.add_argument("--num_workers", type=int, default=max(1, os.cpu_count() - 1), help="Hilos de procesamiento en paralelo")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración de audios existentes")
    args = parser.parse_args()

    manifests_dir = Path(args.manifests_dir)
    output_audio_dir = Path(args.output_audio_dir)
    output_lhotse_dir = Path(args.output_lhotse_dir)
    train_manifest_path = manifests_dir / "train_manifest.json"

    print("=" * 70)
    print("DATA AUGMENTATION: PITCH SHIFTING PARA UCHUMATAQU ASR (LHOTSE)")
    print("=" * 70)
    print(f"Manifest base       : {train_manifest_path}")
    print(f"Directorio de audio : {output_audio_dir}")
    print(f"Directorio Lhotse   : {output_lhotse_dir}")
    print(f"Factores semitonos  : {args.semitones} (cents: {[int(s*100) for s in args.semitones]})")
    print(f"Hilos paralelos     : {args.num_workers}")

    # Verificar sox o ffmpeg
    backend = "sox" if shutil.which("sox") else ("ffmpeg" if shutil.which("ffmpeg") else None)
    if not backend:
        print("[ERROR] Ni 'sox' ni 'ffmpeg' están instalados en el sistema.")
        print("  Instala sox con: sudo apt-get install -y sox libsox-fmt-all")
        sys.exit(1)
    print(f"Motor de pitch      : {backend}")

    if not train_manifest_path.exists():
        print(f"[ERROR] No se encontró {train_manifest_path}")
        print("  Ejecuta primero: python3 scripts/entrenamiento/preparar_dataset.py")
        sys.exit(1)

    with open(train_manifest_path, "r", encoding="utf-8") as f:
        train_entries = json.load(f)

    print(f"Entradas originales en train_manifest: {len(train_entries)}")

    # Preparar tareas
    tasks = []
    for entry in train_entries:
        for semitone in args.semitones:
            tasks.append((entry, semitone, output_audio_dir, args.force, backend))

    total_tasks = len(tasks)
    print(f"Tareas a procesar   : {total_tasks} ({len(args.semitones)} variantes por audio)")
    print("Procesando audios en paralelo...")

    augmented_entries = []
    exitos = 0
    fallos = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.num_workers) as executor:
        futures = {executor.submit(procesar_un_audio, t): t for t in tasks}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            ok, new_entry = future.result()
            if ok and new_entry is not None:
                augmented_entries.append(new_entry)
                exitos += 1
            else:
                fallos += 1
            if i % 1000 == 0 or i == total_tasks:
                print(f"  [{i}/{total_tasks}] generados... ({exitos} exitosos, {fallos} fallos)")

    print(f"\n[OK] Generación de audio completada: {exitos} variantes generadas.")

    # Combinar train original + variantes aumentadas
    # Las originales marcan pitch_shift_cents = 0
    all_train_entries = []
    for entry in train_entries:
        e = dict(entry)
        e["pitch_shift_cents"] = 0
        e["pitch_shift_semitones"] = 0.0
        all_train_entries.append(e)

    all_train_entries.extend(augmented_entries)
    print(f"Total de entradas en train ampliado: {len(all_train_entries)} (originales + pitch)")

    # 1. Guardar train_manifest_pitch.json
    out_manifest_json = manifests_dir / "train_manifest_pitch.json"
    with open(out_manifest_json, "w", encoding="utf-8") as f:
        json.dump(all_train_entries, f, ensure_ascii=False, indent=2)
    print(f"  [OK] Guardado manifest JSON: {out_manifest_json}")

    # 2. Generar cuts Lhotse uchumataqu_cuts_train_pitch.jsonl.gz
    out_cuts_gz = output_lhotse_dir / "uchumataqu_cuts_train_pitch.jsonl.gz"
    output_lhotse_dir.mkdir(parents=True, exist_ok=True)

    with gzip.open(out_cuts_gz, "wt", encoding="utf-8") as gz_out:
        for idx, entry in enumerate(all_train_entries):
            cut = convertir_entry_a_lhotse_cut(entry, idx)
            gz_out.write(json.dumps(cut, ensure_ascii=False) + "\n")
    print(f"  [OK] Guardado cuts Lhotse: {out_cuts_gz}")

    # Resumen
    dur_total_horas = sum(float(e.get("duracion", 0)) for e in all_train_entries) / 3600.0
    print("\n" + "=" * 70)
    print("RESUMEN DE DATA AUGMENTATION:")
    print(f"  - Cuts originales   : {len(train_entries)}")
    print(f"  - Cuts aumentados   : {len(augmented_entries)}")
    print(f"  - Cuts totales train: {len(all_train_entries)} ({len(all_train_entries)/len(train_entries):.1f}x)")
    print(f"  - Horas de voz train: {dur_total_horas:.2f} horas efectivas")
    print("=" * 70)


if __name__ == "__main__":
    main()

