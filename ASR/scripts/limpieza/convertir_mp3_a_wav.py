#!/usr/bin/env python3
"""
convertir_mp3_a_wav.py
Convierte audios de oraciones en formato MP3 desde ASR/audios_originales/oraciones/
a formato WAV estándar (16000 Hz, Mono, PCM 16-bit) hacia ASR/audios_oraciones/.

Locutores soportados por defecto:
  - gaby:  ASR/audios_originales/oraciones/gaby  -> ASR/audios_oraciones/gaby
  - sofia: ASR/audios_originales/oraciones/sofia -> ASR/audios_oraciones/sofia

IMPORTANTE:
  - NO aplica ninguna normalización de volumen (preserva la ganancia original).
  - Parámetros acústicos: 16000 Hz (-ar 16000), 1 canal mono (-ac 1), pcm_s16le.

Uso:
  python3 ASR/scripts/limpieza/convertir_mp3_a_wav.py
  python3 ASR/scripts/limpieza/convertir_mp3_a_wav.py --locutores gaby
  python3 ASR/scripts/limpieza/convertir_mp3_a_wav.py --dry-run
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LIMPIEZA_DIR = SCRIPT_DIR
SCRIPTS_DIR = SCRIPT_DIR.parent
ASR_DIR = SCRIPTS_DIR.parent
PROJECT_ROOT = ASR_DIR.parent

DEFAULT_LOCUTORES = ["gaby", "sofia"]


def verificar_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("[ERROR] No se encontró 'ffmpeg' en el sistema.")
        sys.exit(1)


def convertir_archivo_mp3_a_wav(
    ruta_origen: Path,
    ruta_destino: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    dry_run: bool = False,
) -> bool:
    """
    Convierte un MP3 a WAV 16 kHz Mono PCM 16-bit SIN normalización.
    """
    if dry_run:
        return True

    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    ruta_tmp = ruta_destino.with_suffix(".tmp.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-i", str(ruta_origen),
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s16le",
        str(ruta_tmp),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and ruta_tmp.exists() and ruta_tmp.stat().st_size > 100:
            ruta_tmp.replace(ruta_destino)
            return True
        else:
            print(f"  [ERROR] Falló conversión de {ruta_origen.name}: {res.stderr.strip()}")
            if ruta_tmp.exists():
                ruta_tmp.unlink(missing_ok=True)
            return False
    except Exception as e:
        print(f"  [ERROR] Excepción convirtiendo {ruta_origen.name}: {e}")
        if ruta_tmp.exists():
            ruta_tmp.unlink(missing_ok=True)
        return False


def procesar_locutor(
    locutor: str,
    sample_rate: int = 16000,
    channels: int = 1,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    dir_origen = ASR_DIR / "audios_originales" / "oraciones" / locutor
    dir_destino = ASR_DIR / "audios_oraciones" / locutor

    if not dir_origen.exists():
        print(f"[WARN] No existe carpeta de origen: {dir_origen}")
        return {"total": 0, "convertidos": 0, "omitidos": 0, "errores": 0}

    dir_destino.mkdir(parents=True, exist_ok=True)

    archivos_mp3 = sorted([
        f for f in dir_origen.iterdir()
        if f.suffix.lower() == ".mp3" and not f.name.startswith(".")
    ])

    print(f"\n📂 Procesando locutor '{locutor}': {len(archivos_mp3)} archivos MP3")
    print(f"   Origen:  {dir_origen}")
    print(f"   Destino: {dir_destino}")
    print("-" * 75)

    stats = {"total": len(archivos_mp3), "convertidos": 0, "omitidos": 0, "errores": 0}

    for f_mp3 in archivos_mp3:
        # Mapeo de nombres para destino WAV
        base_name = f_mp3.stem

        # Caso especial Sofia O_009: el audio O_009.mp3 de Sofia corresponde a O_136
        # ("Wilk chhuñiqasi, uwapinichay, amthü") según la reestructuración curricular.
        if locutor.lower() == "sofia" and base_name == "O_009":
            dest_name = "O_136.wav"
        else:
            dest_name = f"{base_name}.wav"

        ruta_wav = dir_destino / dest_name

        # Convertir
        exito = convertir_archivo_mp3_a_wav(
            f_mp3,
            ruta_wav,
            sample_rate=sample_rate,
            channels=channels,
            dry_run=dry_run,
        )

        if exito:
            stats["convertidos"] += 1
            if verbose:
                print(f"  [OK] {f_mp3.name} -> {dest_name}")
        else:
            stats["errores"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Convierte audios de oraciones MP3 a WAV (16000 Hz, mono, sin normalizar) para ASR."
    )
    parser.add_argument(
        "--locutores",
        nargs="+",
        default=DEFAULT_LOCUTORES,
        help="Locutores a procesar (default: gaby sofia)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Frecuencia de muestreo en Hz (default: 16000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la conversión sin crear ni modificar archivos",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra detalle archivo por archivo",
    )

    args = parser.parse_args()
    verificar_ffmpeg()

    print("=" * 75)
    print("🎙️ CONVERTIDOR MP3 -> WAV (16 kHz, MONO, SIN NORMALIZAR) PARA ASR")
    print(f"  • Locutores:    {', '.join(args.locutores)}")
    print(f"  • Formato:      WAV PCM 16-bit ({args.sample_rate} Hz, Mono)")
    print(f"  • Normalizar:   NO (conserva volumen original)")
    print(f"  • Simulación:   {'SÍ (--dry-run)' if args.dry_run else 'NO (conversión real)'}")
    print("=" * 75)

    totales = {"total": 0, "convertidos": 0, "omitidos": 0, "errores": 0}

    for loc in args.locutores:
        st = procesar_locutor(
            loc,
            sample_rate=args.sample_rate,
            channels=1,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        for k in totales:
            totales[k] += st[k]

    print("\n" + "=" * 75)
    print("RESUMEN DE CONVERSIÓN")
    print("=" * 75)
    print(f"  Total archivos MP3: {totales['total']}")
    print(f"  Convertidos a WAV:  {totales['convertidos']}")
    print(f"  Errores:            {totales['errores']}")
    print("=" * 75)

    if totales["errores"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
