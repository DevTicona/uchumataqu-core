#!/usr/bin/env python3
"""
convertir_oraciones_sofia.py
Convierte los audios de oraciones grabados en formato MP3 desde 'UNITY/oraciones_sofia/'
a formato WAV PCM 16-bit (16 kHz, mono) y los guarda en 'UNITY/audios_oraciones/'.

Uso:
  python3 UNITY/scripts/convertir_oraciones_sofia.py
  python3 UNITY/scripts/convertir_oraciones_sofia.py --dry-run
  python3 UNITY/scripts/convertir_oraciones_sofia.py --input-dir UNITY/oraciones_sofia --output-dir UNITY/audios_oraciones
"""

import os
import sys
import shutil
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(SCRIPT_DIR)
UNITY_DIR = os.path.dirname(SCRIPTS_DIR)
PROJECT_ROOT = os.path.dirname(UNITY_DIR)

DEFAULT_INPUT_DIR = os.path.join(UNITY_DIR, "oraciones_sofia")
DEFAULT_OUTPUT_DIR = os.path.join(UNITY_DIR, "audios_oraciones")
VERIFICAR_SCRIPT = os.path.join(SCRIPT_DIR, "verificar_audios_app.py")


def verificar_ffmpeg():
    """Verifica que ffmpeg esté instalado en el sistema."""
    if not shutil.which("ffmpeg"):
        print("[ERROR] No se encontró 'ffmpeg' en el sistema.")
        print("        Por favor instala ffmpeg con: sudo apt install ffmpeg")
        sys.exit(1)


def convertir_audio(
    ruta_origen: str,
    ruta_destino: str,
    sample_rate: int = 16000,
    channels: int = 1,
    dry_run: bool = False
) -> bool:
    """
    Convierte un archivo de audio a WAV PCM 16-bit con ffmpeg.
    Parámetros estándar: 16 kHz (-ar 16000), mono (-ac 1), PCM 16-bit (-c:a pcm_s16le).
    """
    if dry_run:
        return True

    cmd = [
        "ffmpeg",
        "-y",               # Sobrescribir sin preguntar
        "-loglevel", "error", # Solo errores en salida estándar
        "-i", ruta_origen,
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s16le",
        ruta_destino
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True
        else:
            print(f"  ❌ Error convirtiendo {os.path.basename(ruta_origen)}: {res.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ❌ Excepción al ejecutar ffmpeg: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convierte audios de oraciones MP3 a WAV 16-bit (16 kHz mono) hacia audios_oraciones"
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Carpeta de origen con los audios (default: UNITY/oraciones_sofia)"
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta destino para los audios convertidos (default: UNITY/audios_oraciones)"
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Frecuencia de muestreo en Hz (default: 16000 Hz / 16 kHz)"
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=1,
        help="Número de canales de audio (default: 1 / Mono)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la conversión sin generar archivos en disco"
    )
    parser.add_argument(
        "--sin-verificar",
        action="store_true",
        help="No ejecuta verificar_audios_app.py tras la conversión"
    )

    args = parser.parse_args()

    print("=" * 90)
    print("🎙️  CONVERSOR DE AUDIOS DE ORACIONES (MP3 -> WAV 16-BIT 16kHz MONO)")
    print("=" * 90)
    print(f"  Origen           : {args.input_dir}")
    print(f"  Destino          : {args.output_dir}")
    print(f"  Formato salida   : WAV PCM 16-bit ({args.sample_rate} Hz, {args.channels} canal/es)")
    if args.dry_run:
        print("  MODO             : SIMULACIÓN (--dry-run)")
    print("=" * 90)

    verificar_ffmpeg()

    if not os.path.isdir(args.input_dir):
        print(f"[ERROR] No existe la carpeta origen: {args.input_dir}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # Buscar archivos de audio en origen
    extensiones_validas = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
    archivos = sorted([
        f for f in os.listdir(args.input_dir)
        if os.path.splitext(f)[1].lower() in extensiones_validas and not f.startswith(".")
    ])

    if not archivos:
        print(f"[AVISO] No se encontraron archivos de audio en {args.input_dir}")
        return

    print(f"\n[INFO] Se encontraron {len(archivos)} audios para procesar.\n")
    print(f"{'#':<4} {'ARCHIVO ORIGEN':<25} {'->':<3} {'ARCHIVO DESTINO':<25} {'ESTADO'}")
    print("-" * 90)

    exitosos = 0
    fallidos = 0

    for idx, f_name in enumerate(archivos, 1):
        base_name = os.path.splitext(f_name)[0]
        dest_name = f"{base_name}.wav"

        ruta_orig = os.path.join(args.input_dir, f_name)
        ruta_dest = os.path.join(args.output_dir, dest_name)

        ok = convertir_audio(
            ruta_origen=ruta_orig,
            ruta_destino=ruta_dest,
            sample_rate=args.sample_rate,
            channels=args.channels,
            dry_run=args.dry_run
        )

        if ok:
            exitosos += 1
            estado = "SIMULADO" if args.dry_run else "CONVERTIDO"
            print(f"{idx:<4} {f_name:<25} ->  {dest_name:<25} {estado}")
        else:
            fallidos += 1

    print("\n" + "=" * 90)
    print("RESUMEN DE CONVERSIÓN:")
    print(f"  • Total archivos analizados : {len(archivos)}")
    print(f"  • Convertidos con éxito    : {exitosos}")
    print(f"  • Errores en conversión    : {fallidos}")
    print("=" * 90)

    # Actualizar reporte de la app automáticamente
    if not args.dry_run and not args.sin_verificar and os.path.exists(VERIFICAR_SCRIPT):
        print("\n[INFO] Actualizando reporte de verificación (verificar_audios_app.py)...")
        try:
            res = subprocess.run([sys.executable, VERIFICAR_SCRIPT], capture_output=True, text=True)
            if res.returncode == 0:
                print("  ✅ Reporte de audios de la app actualizado exitosamente.")
            else:
                print(f"  ⚠️ Advertencia al ejecutar verificar_audios_app.py:\n{res.stderr}")
        except Exception as e:
            print(f"  ⚠️ No se pudo ejecutar verificar_audios_app.py: {e}")

    print("\n[OK] Proceso finalizado.")


if __name__ == "__main__":
    main()
