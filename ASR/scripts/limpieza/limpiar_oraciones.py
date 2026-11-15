"""
limpiar_oraciones.py
Procesa grabaciones originales de oraciones siguiendo el flujo:
  1. Normaliza el audio completo a -3 dBFS (16000 Hz, mono 16-bit).
  2. Detecta las repeticiones en el audio normalizado según los silencios que separan
     cada toma (sin fusionar silencios en medio de las oraciones).
  3. Recorta cada repetición correctamente desde su inicio y fin, refinando los
     límites para capturar fonación completa (incluyendo oclusiones y sílabas finales).
  4. Agrega un margen de silencio exacto de 300 ms al inicio y al final.
  5. Exporta los archivos a:
     - ASR/audios_oraciones/{locutor}/{id}_01.wav, {id}_02.wav, {id}_03.wav
     - (Opcional con --app) UNITY/audios_oraciones/{id}.wav (toma canónica 01)

Uso:
  python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor roberto
  python3 ASR/scripts/limpieza/limpiar_oraciones.py --locutor pedro --app
  python3 ASR/scripts/limpieza/limpiar_oraciones.py --input /ruta/origen --output /ruta/destino
"""

import os
import sys
import shutil
import argparse
import logging
from pydub import AudioSegment, silence
from pydub.utils import which

logging.basicConfig(level=logging.INFO, format='%(message)s')

script_dir = os.path.dirname(os.path.abspath(__file__))
limpieza_dir = script_dir
scripts_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(scripts_dir)
project_root = os.path.dirname(asr_dir)

# ─── Configuración para Oraciones ───────────────────────────
TARGET_FS       = 16000
TARGET_DB       = -3.0
SILENCE_PAD_MS  = 300     # Silencio de 300 ms añadido al inicio y final
MIN_CHUNK_MS    = 500     # Duración mínima para una oración válida
MIN_FILE_BYTES  = 1000
MAX_CHUNKS      = 3       # 3 repeticiones esperadas por defecto
# ─────────────────────────────────────────────────────────────


def setup_ffmpeg():
    ffmpeg_path = which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_path):
        raise EnvironmentError("ffmpeg no encontrado. Asegúrate de tenerlo instalado.")
    AudioSegment.converter = ffmpeg_path


def normalize(audio: AudioSegment, target_db: float = TARGET_DB) -> AudioSegment:
    """Normaliza la señal de audio completa al valor target_db (por defecto -3 dBFS)."""
    if audio.max_dBFS == float('-inf'):
        return audio
    return audio.apply_gain(target_db - audio.max_dBFS)


def detect_repetition_ranges(audio_normalized: AudioSegment, expected_chunks: int = 3) -> list:
    """
    Detecta las repeticiones directamente sobre el audio ya normalizado a -3 dBFS.
    Aprovecha los silencios inter-repetición reales sin fragmentar oraciones
    ni manipular pausas internas que pertenezcan a la fonación.

    Para oraciones, las pausas entre repeticiones son más largas que en palabras,
    y las oraciones pueden tener pausas internas breves.
    """
    # Umbrales más amplios para oraciones (mayor variabilidad)
    thresholds = [-45, -42, -48, -40, -50, -38, -52, -55]
    min_silence_lens = [700, 600, 800, 900, 500, 1000]

    best_ranges = []

    for thresh in thresholds:
        for min_sil in min_silence_lens:
            raw_ranges = silence.detect_nonsilent(
                audio_normalized,
                min_silence_len=min_sil,
                silence_thresh=thresh
            )
            valid = [tuple(r) for r in raw_ranges if (r[1] - r[0]) >= MIN_CHUNK_MS]

            if len(valid) == expected_chunks:
                return valid
            if len(valid) < expected_chunks and len(valid) > len(best_ranges):
                best_ranges = valid

    # Si no encontramos el número exacto, intentar fusionar fragmentos cercanos
    # (pausas internas de la oración < 800ms)
    if len(best_ranges) > expected_chunks:
        merged = merge_close_ranges(best_ranges, 800)
        if len(merged) == expected_chunks:
            return merged
        # Si aún hay más, tomar las más largas
        merged = sorted(merged, key=lambda r: r[1] - r[0], reverse=True)[:expected_chunks]
        merged.sort(key=lambda r: r[0])
        return merged

    # Si se esperaban 3 pero solo hay 2 o 1, devolver lo que se encontró
    return best_ranges


def merge_close_ranges(ranges: list, gap_ms: int) -> list:
    """Fusiona rangos que estén separados por menos de gap_ms milisegundos."""
    if not ranges:
        return []
    merged = [list(ranges[0])]
    for start, end in ranges[1:]:
        if start - merged[-1][1] < gap_ms:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [tuple(r) for r in merged]


def refine_repetition_boundaries(audio: AudioSegment, start: int, end: int,
                                  max_left: int, max_right: int,
                                  silence_floor: float = -58.0,
                                  max_bridge_gap: int = 180) -> tuple:
    """
    Refina los puntos de corte inicial y final de la repetición:
      - Inicio: Expande hacia atrás buscando el mínimo sonido audible sobre el piso
        de silencio (-58 dBFS). Si encuentra una breve oclusión/pausa (< 180 ms,
        típica de consonantes eyectivas k', p', t' o arranques de oración), la cruza
        para capturar el inicio completo. Si el silencio supera los 180 ms, se detiene.
      - Fin: Expande hacia adelante buscando el decaimiento completo de la oración.
        Si encuentra una breve oclusión (< 180 ms), la cruza para capturar la sílaba
        final íntegra. Si el silencio supera los 180 ms, se detiene.
      - Aplica márgenes limpios de 15 ms al inicio y 20 ms al final, acotados por
        max_left y max_right.
    """
    # 1. Inicio: expandir hacia atrás cruzando micro-cierres fonéticos (< 180 ms)
    cur_s = start
    while cur_s - 10 >= max_left:
        level = audio[cur_s - 10 : cur_s].dBFS
        if level > silence_floor:
            cur_s -= 10
        else:
            # Comprobar si hay un sonido inicial a menos de max_bridge_gap
            found = False
            for lookback in range(10, max_bridge_gap + 10, 10):
                if cur_s - lookback - 10 >= max_left:
                    if audio[cur_s - lookback - 10 : cur_s - lookback].dBFS > silence_floor:
                        found = True
                        cur_s = cur_s - lookback
                        break
            if not found:
                break
    actual_start = max(max_left, cur_s - 15)

    # 2. Fin: expandir hacia adelante cruzando micro-cierres fonéticos (< 180 ms)
    cur_e = end
    while cur_e + 10 <= max_right:
        level = audio[cur_e : cur_e + 10].dBFS
        if level > silence_floor:
            cur_e += 10
        else:
            # Comprobar si hay una sílaba final a menos de max_bridge_gap
            found = False
            for lookahead in range(10, max_bridge_gap + 10, 10):
                if cur_e + lookahead + 10 <= max_right:
                    if audio[cur_e + lookahead : cur_e + lookahead + 10].dBFS > silence_floor:
                        found = True
                        cur_e = cur_e + lookahead
                        break
            if not found:
                break
    actual_end = min(max_right, cur_e + 20)

    return actual_start, actual_end


def verify_exported(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < MIN_FILE_BYTES:
        return False
    try:
        return len(AudioSegment.from_wav(path)) > 0
    except:
        return False


def process_audio(path: str, sentence_name: str, output_dir: str,
                  app_dir: str = None, max_chunks: int = MAX_CHUNKS):
    """
    Procesa un archivo de audio crudo de oración:
      1. Normaliza todo el audio a -3 dBFS.
      2. Detecta las repeticiones sin fusionar silencios en medio de oraciones.
      3. Refina y recorta cada repetición correctamente desde su inicio hasta su final.
      4. Añade 300 ms de silencio al inicio y final.
      5. Exporta los archivos normalizados.
    """
    errores = []
    try:
        raw_audio = AudioSegment.from_file(path).set_frame_rate(TARGET_FS).set_channels(1)
    except Exception as e:
        return 0, [f"Error crítico abriendo archivo: {e}"]

    # Paso 1: Normalizar todo el audio a -3 dBFS
    audio = normalize(raw_audio, TARGET_DB)
    total_ms = len(audio)

    # Paso 2: Detectar las repeticiones sobre el audio normalizado
    ranges = detect_repetition_ranges(audio, expected_chunks=max_chunks)

    if not ranges:
        return 0, [f"No se detectó voz en el audio"]

    if len(ranges) < max_chunks:
        errores.append(f"Solo se detectaron {len(ranges)} de {max_chunks} repeticiones")

    # Silencio exacto de 300 ms para el inicio y final
    padding = AudioSegment.silent(duration=SILENCE_PAD_MS, frame_rate=TARGET_FS)
    exported = 0

    chunks_to_export = min(len(ranges), max_chunks)
    for idx in range(chunks_to_export):
        chunk_id = idx + 1
        start, end = ranges[idx]

        # Límites seguros para no invadir la toma anterior ni la siguiente
        prev_end = 0 if idx == 0 else ranges[idx - 1][1]
        next_start = total_ms if idx == len(ranges) - 1 else ranges[idx + 1][0]

        max_left = (start + prev_end) // 2 if idx > 0 else 0
        max_right = (end + next_start) // 2 if idx < len(ranges) - 1 else total_ms

        # Paso 3: Recortar cada repetición detectando bien el inicio y el final completo
        start_corte, end_corte = refine_repetition_boundaries(
            audio, start, end, max_left, max_right
        )
        chunk = audio[start_corte:end_corte]
        chunk_ms = len(chunk)

        if chunk_ms < MIN_CHUNK_MS:
            errores.append(f"Toma {chunk_id}: Descartada por muy corta ({chunk_ms}ms < {MIN_CHUNK_MS}ms)")
            continue

        # Paso 4: Agregar silencio de 300 ms al inicio y final
        final = padding + chunk + padding

        out_name = f"{sentence_name}_{str(chunk_id).zfill(2)}.wav"
        out_path = os.path.join(output_dir, out_name)

        try:
            final.export(out_path, format="wav", parameters=["-ar", str(TARGET_FS)])
            if verify_exported(out_path):
                exported += 1
                logging.info(f"  ✅ {out_name} exportado a ASR")

                if chunk_id == 1 and app_dir:
                    app_out_path = os.path.join(app_dir, f"{sentence_name}.wav")
                    shutil.copy2(out_path, app_out_path)
                    logging.info(f"  📱 {sentence_name}.wav copiado a App")
            else:
                errores.append(f"Toma {chunk_id}: Error de integridad tras exportar")
                if os.path.exists(out_path):
                    os.remove(out_path)
        except Exception as e:
            errores.append(f"Toma {chunk_id}: Error al exportar: {e}")

    for idx in range(len(ranges), max_chunks):
        errores.append(f"Toma {idx+1}: No generada (no hay más tomas en el audio)")

    return exported, errores


def main():
    parser = argparse.ArgumentParser(
        description="Limpia y divide grabaciones originales de oraciones en repeticiones."
    )
    parser.add_argument("--locutor", default="roberto",
                        help="Nombre del locutor (eva, pedro, sofia, lorenzo, roberto)")
    parser.add_argument("--input", default=None,
                        help="Carpeta con grabaciones originales")
    parser.add_argument("--output", default=None,
                        help="Carpeta de destino ASR")
    parser.add_argument("--max_chunks", type=int, default=None,
                        help="Número de repeticiones esperadas por archivo (por defecto 3)")
    parser.add_argument("--app", action="store_true",
                        help="Si se activa, copia la primera toma a UNITY/audios_oraciones/{id}.wav")
    args = parser.parse_args()

    setup_ffmpeg()

    locutor_nombre = args.locutor.strip().lower()
    max_chunks = args.max_chunks or MAX_CHUNKS

    input_dir = args.input
    if not input_dir:
        candidatos = [
            os.path.join(asr_dir, "audios_originales", "oraciones", args.locutor),
            os.path.join(asr_dir, "audios_originales", "oraciones", args.locutor.capitalize()),
            os.path.join(asr_dir, "audios_originales", "oraciones", args.locutor.lower()),
            os.path.join(project_root, "audios_originales", "oraciones", args.locutor),
            os.path.join(project_root, "audios_originales", "oraciones", args.locutor.capitalize()),
            os.path.join(project_root, "audios_originales", "oraciones", args.locutor.lower()),
        ]
        input_dir = next((c for c in candidatos if os.path.exists(c)), candidatos[0])

    output_dir = args.output or os.path.join(asr_dir, "audios_oraciones", locutor_nombre)
    app_dir = os.path.join(project_root, "UNITY", "audios_oraciones") if args.app else None

    os.makedirs(output_dir, exist_ok=True)
    if app_dir:
        os.makedirs(app_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print(f"[ERROR] Carpeta de grabaciones originales no encontrada: {input_dir}")
        print("  Por favor, coloca las oraciones originales en:")
        print(f"    ASR/audios_originales/oraciones/{args.locutor}/")
        print(f"  o ejecuta con: python3 ASR/scripts/limpieza/limpiar_oraciones.py --input /ruta/origen --locutor {args.locutor}")
        return

    files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".wav", ".mp3", ".m4a", ".ogg"))
        and not f.endswith(":Zone.Identifier")
    )
    if not files:
        logging.warning(f"No se encontraron archivos de audio en {input_dir}")
        return

    # Limpiar previamente audios exportados viejos en la carpeta de destino
    for existing in os.listdir(output_dir):
        if existing.lower().endswith(".wav"):
            os.remove(os.path.join(output_dir, existing))

    print("=" * 70)
    print(f"🚀 INICIANDO LIMPIEZA Y DIVISIÓN DE ORACIONES")
    print(f"   Locutor:      {locutor_nombre.upper()}")
    print(f"   Archivos:     {len(files)} originales")
    print(f"   Repeticiones: {max_chunks} esperadas por archivo")
    print(f"   Entrada:      {input_dir}")
    print(f"   Salida ASR:   {output_dir}")
    if app_dir:
        print(f"   Salida App:   {app_dir}")
    print("=" * 70)

    total_real = 0
    reporte_incidencias = {}

    for idx_file, filename in enumerate(files):
        sentence_name = os.path.splitext(filename)[0]
        # Si el nombre ya es un ID (O_001, etc.), mantenerlo; si no, usar minúsculas
        if not sentence_name.startswith("O_"):
            sentence_name = sentence_name.lower()

        logging.info(
            f"\n📂 [{idx_file+1:03d}/{len(files)}] Archivo: {filename} "
            f"-> ID: {sentence_name} (Esperadas: {max_chunks} tomas)"
        )

        count, errors = process_audio(
            os.path.join(input_dir, filename),
            sentence_name,
            output_dir,
            app_dir,
            max_chunks=max_chunks
        )
        total_real += count
        if errors:
            reporte_incidencias[filename] = errors

    print("\n" + "=" * 70)
    print(f"PROCESAMIENTO COMPLETADO: {total_real} tomas generadas en {output_dir}")
    if reporte_incidencias:
        print(f"⚠️ Advertencias/incidencias en {len(reporte_incidencias)} archivos:")
        for fname, errs in sorted(reporte_incidencias.items()):
            for e in errs:
                print(f"  - {fname}: {e}")
    else:
        print("✨ Todos los archivos fueron procesados y exportados sin incidencias.")
    print("=" * 70)


if __name__ == "__main__":
    main()
