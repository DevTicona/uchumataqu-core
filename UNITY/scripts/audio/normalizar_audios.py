#!/usr/bin/env python3
"""
normalizar_audios.py
Normalizador de volumen pico a -3.0 dBFS para archivos de audio WAV en Unity.

Aplica estandarización acústica homogénea en:
  - UNITY/audios_palabras/
  - UNITY/audios_oraciones/

Características:
  - Motor preferido: SoX ('norm -3.0'), con fallback a ffmpeg y motor nativo NumPy/wave.
  - Medición rápida de pico: Evalúa si el archivo ya se encuentra en el rango objetivo
    (por defecto -3.0 dBFS ± 0.05 dB) para evitar re-codificaciones innecesarias.
  - Opción --force para forzar la normalización de todos los archivos.
  - Escritura atómica mediante archivos temporales para prevenir archivos corruptos.

Uso:
  python3 UNITY/scripts/audio/normalizar_audios.py
  python3 UNITY/scripts/audio/normalizar_audios.py --dry-run
  python3 UNITY/scripts/audio/normalizar_audios.py --force
  python3 UNITY/scripts/audio/normalizar_audios.py --target-db -3.0 --verbose
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None


SCRIPT_DIR = Path(__file__).resolve().parent
UNITY_DIR = SCRIPT_DIR.parent.parent
PROJECT_ROOT = UNITY_DIR.parent

DEFAULT_DIRS = [
    UNITY_DIR / "audios_palabras",
    UNITY_DIR / "audios_oraciones",
]


def calcular_pico_dbfs(ruta_archivo: Path) -> Optional[float]:
    """
    Calcula el nivel de pico en dBFS de un archivo WAV de forma rápida.
    Retorna None si el archivo no puede leerse o está vacío.
    """
    try:
        with wave.open(str(ruta_archivo), "rb") as w:
            nframes = w.getnframes()
            sampwidth = w.getsampwidth()
            if nframes == 0:
                return -999.0
            frames = w.readframes(nframes)

        if np is not None:
            if sampwidth == 2:
                data = np.frombuffer(frames, dtype=np.int16)
                peak_linear = np.max(np.abs(data)) / 32768.0
            elif sampwidth == 1:
                data = np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128
                peak_linear = np.max(np.abs(data)) / 128.0
            elif sampwidth == 4:
                data = np.frombuffer(frames, dtype=np.int32)
                peak_linear = np.max(np.abs(data)) / 2147483648.0
            else:
                return None
        else:
            # Fallback sin numpy (lectura por muestras estándar 16-bit)
            if sampwidth == 2:
                import struct
                count = len(frames) // 2
                samples = struct.unpack(f"<{count}h", frames)
                peak_linear = max(abs(s) for s in samples) / 32768.0
            else:
                return None

        if peak_linear <= 0:
            return -999.0

        return 20.0 * math.log10(peak_linear)
    except Exception:
        return None


def normalizar_archivo_sox(ruta_in: Path, ruta_out: Path, target_db: float) -> bool:
    """Normaliza un archivo de audio a target_db usando SoX."""
    if not shutil.which("sox"):
        return False
    try:
        cmd = ["sox", str(ruta_in), str(ruta_out), "norm", f"{target_db:.2f}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and ruta_out.exists() and ruta_out.stat().st_size > 100
    except Exception:
        return False


def normalizar_archivo_ffmpeg(ruta_in: Path, ruta_out: Path, target_db: float, pico_actual: Optional[float]) -> bool:
    """Normaliza un archivo de audio a target_db usando ffmpeg."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        if pico_actual is None:
            cmd_measure = [
                "ffmpeg", "-hide_banner", "-i", str(ruta_in),
                "-af", "volumedetect", "-f", "null", "/dev/null"
            ]
            res_m = subprocess.run(cmd_measure, capture_output=True, text=True)
            import re
            m = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", res_m.stderr)
            if not m:
                return False
            pico_actual = float(m.group(1))

        diff = target_db - pico_actual
        gain_str = f"{diff:+.2f}dB"
        cmd_norm = [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(ruta_in),
            "-af", f"volume={gain_str}",
            "-c:a", "pcm_s16le", str(ruta_out)
        ]
        res_n = subprocess.run(cmd_norm, capture_output=True, text=True)
        return res_n.returncode == 0 and ruta_out.exists() and ruta_out.stat().st_size > 100
    except Exception:
        return False


def normalizar_archivo_numpy(ruta_in: Path, ruta_out: Path, target_db: float) -> bool:
    """Normaliza un archivo de audio WAV PCM de 16-bit de forma nativa con NumPy y wave."""
    if np is None:
        return False
    try:
        with wave.open(str(ruta_in), "rb") as w:
            params = w.getparams()
            if params.sampwidth != 2:
                return False
            frames = w.readframes(params.nframes)

        data = np.frombuffer(frames, dtype=np.int16)
        curr_peak = np.max(np.abs(data))
        if curr_peak == 0:
            return False

        target_peak = 32767.0 * (10.0 ** (target_db / 20.0))
        gain = target_peak / float(curr_peak)
        scaled = np.clip(np.round(data * gain), -32768, 32767).astype(np.int16)

        with wave.open(str(ruta_out), "wb") as w_out:
            w_out.setparams(params)
            w_out.writeframes(scaled.tobytes())

        return ruta_out.exists() and ruta_out.stat().st_size > 100
    except Exception:
        return False


def normalizar_audio(
    ruta_archivo: Path,
    target_db: float = -3.0,
    tolerancia: float = 0.05,
    forzar: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Evalúa y normaliza un archivo de audio a target_db.

    Retorna una tupla: (estado, pico_antes, pico_despues)
      - estado: 'sin_cambios', 'normalizado', 'error'
    """
    pico_antes = calcular_pico_dbfs(ruta_archivo)

    # Si ya está dentro de la tolerancia y no se fuerza, omitir
    if pico_antes is not None and not forzar:
        if abs(pico_antes - target_db) <= tolerancia:
            if verbose:
                print(f"  [OMITIDO] {ruta_archivo.name:<35} | Pico actual: {pico_antes:6.2f} dBFS (ya a {target_db:.1f} dB)")
            return "sin_cambios", pico_antes, pico_antes

    if dry_run:
        if verbose:
            print(f"  [SIMULADO] {ruta_archivo.name:<34} | {pico_antes:6.2f} dBFS -> {target_db:.2f} dBFS")
        return "normalizado", pico_antes, target_db

    ruta_tmp = ruta_archivo.with_suffix(".tmp.wav")

    # Intentar motores en orden de preferencia: SoX -> NumPy -> FFmpeg
    exito = normalizar_archivo_sox(ruta_archivo, ruta_tmp, target_db)
    if not exito:
        exito = normalizar_archivo_numpy(ruta_archivo, ruta_tmp, target_db)
    if not exito:
        exito = normalizar_archivo_ffmpeg(ruta_archivo, ruta_tmp, target_db, pico_antes)

    if exito:
        try:
            ruta_tmp.replace(ruta_archivo)
            pico_despues = calcular_pico_dbfs(ruta_archivo)
            if verbose:
                p_ant_str = f"{pico_antes:6.2f}" if pico_antes is not None else " N/A  "
                p_des_str = f"{pico_despues:6.2f}" if pico_despues is not None else " N/A  "
                print(f"  [AJUSTADO] {ruta_archivo.name:<34} | {p_ant_str} dBFS -> {p_des_str} dBFS")
            return "normalizado", pico_antes, pico_despues
        except Exception as e:
            if verbose:
                print(f"  [ERROR] No se pudo reemplazar {ruta_archivo.name}: {e}")
            if ruta_tmp.exists():
                ruta_tmp.unlink(missing_ok=True)
            return "error", pico_antes, None
    else:
        if ruta_tmp.exists():
            ruta_tmp.unlink(missing_ok=True)
        if verbose:
            print(f"  [ERROR] Falló la normalización técnica de {ruta_archivo.name}")
        return "error", pico_antes, None


def procesar_directorio(
    directorio: Path,
    target_db: float = -3.0,
    tolerancia: float = 0.05,
    forzar: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Procesa todos los archivos .wav de un directorio."""
    if not directorio.exists() or not directorio.is_dir():
        print(f"[WARN] Directorio no encontrado: {directorio}")
        return {"total": 0, "sin_cambios": 0, "normalizados": 0, "errores": 0}

    archivos = sorted([
        f for f in directorio.iterdir()
        if f.suffix.lower() == ".wav" and not f.name.startswith(".") and not f.name.endswith(".tmp.wav")
    ])

    stats = {
        "total": len(archivos),
        "sin_cambios": 0,
        "normalizados": 0,
        "errores": 0,
    }

    print(f"\n📂 Procesando: {directorio} ({len(archivos)} archivos WAV)")
    print("-" * 75)

    for arch in archivos:
        estado, _, _ = normalizar_audio(
            arch,
            target_db=target_db,
            tolerancia=tolerancia,
            forzar=forzar,
            dry_run=dry_run,
            verbose=verbose,
        )
        if estado == "sin_cambios":
            stats["sin_cambios"] += 1
        elif estado == "normalizado":
            stats["normalizados"] += 1
        else:
            stats["errores"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Normaliza cada audio WAV a -3.0 dBFS en las carpetas de Unity."
    )
    parser.add_argument(
        "--target-db",
        type=float,
        default=-3.0,
        help="Nivel de pico objetivo en dBFS (por defecto: -3.0 dBFS)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Margen de tolerancia en dB para considerar el audio ya normalizado (def: 0.05 dB)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la normalización de todos los archivos incluso si ya están a -3 dB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo simulación: no modifica los archivos en disco",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra el detalle individual de cada archivo procesado",
    )
    parser.add_argument(
        "--palabras-only",
        action="store_true",
        help="Solo procesa la carpeta de palabras",
    )
    parser.add_argument(
        "--oraciones-only",
        action="store_true",
        help="Solo procesa la carpeta de oraciones",
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        help="Rutas a directorios personalizados para normalizar",
    )

    args = parser.parse_args()

    directorios = []
    if args.dirs:
        directorios = [Path(d).resolve() for d in args.dirs]
    elif args.palabras_only:
        directorios = [UNITY_DIR / "audios_palabras"]
    elif args.oraciones_only:
        directorios = [UNITY_DIR / "audios_oraciones"]
    else:
        directorios = DEFAULT_DIRS

    print("=" * 75)
    print("🔊 NORMALIZADOR DE AUDIO UCHUMATAQU (UNITY)")
    print(f"  • Objetivo:       {args.target_db:.2f} dBFS")
    print(f"  • Tolerancia:     ±{args.tolerance:.2f} dB")
    print(f"  • Modo forzado:   {'SÍ' if args.force else 'NO (omite si ya está en rango)'}")
    print(f"  • Simulación:     {'SÍ (--dry-run)' if args.dry_run else 'NO (modificación real)'}")
    print("=" * 75)

    t_inicio = time.time()
    tot_general = {"total": 0, "sin_cambios": 0, "normalizados": 0, "errores": 0}

    for d in directorios:
        st = procesar_directorio(
            d,
            target_db=args.target_db,
            tolerancia=args.tolerance,
            forzar=args.force,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        for k in tot_general:
            tot_general[k] += st[k]

    t_total = time.time() - t_inicio

    print("\n" + "=" * 75)
    print("RESUMEN GLOBAL DE NORMALIZACIÓN")
    print("=" * 75)
    print(f"  Total de archivos analizados:  {tot_general['total']}")
    print(f"  Ya en nivel óptimo (-3 dB):     {tot_general['sin_cambios']}")
    print(f"  Archivos normalizados:          {tot_general['normalizados']}")
    print(f"  Errores:                        {tot_general['errores']}")
    print(f"  Tiempo transcurrido:            {t_total:.2f} segundos")
    print("=" * 75)

    if tot_general["errores"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
