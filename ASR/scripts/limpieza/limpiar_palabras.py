"""
limpiar_palabras.py
Procesa grabaciones originales de palabras siguiendo el flujo:
  1. Normaliza el audio completo a -3 dBFS (16000 Hz, mono 16-bit).
  2. Detecta las repeticiones en el audio normalizado según los silencios que separan
     cada toma (sin fusionar silencios en medio de las palabras).
  3. Recorta cada repetición correctamente desde su inicio y fin.
  4. Agrega un margen de silencio exacto de 250 ms al inicio y al final.
  5. Exporta los archivos a:
     - ASR/audios_palabras/{locutor}/{id}_01.wav, {id}_02.wav, ...
     - (Opcional con --app) UNITY/audios_palabras/{id}.wav (toma canónica 01)

Reglas de locutores:
  - Las primeras 19 palabras de Eva tienen 3 repeticiones (_01, _02, _03).
    No se fuerzan a 4 tomas (se completarán manualmente con faltantes.wav recortando manualmente).
  - A partir de la palabra 20 en adelante (índice 19 en adelante), se detectan 4 repeticiones (_01, _02, _03, _04).
  - Archivos especiales regrabados con 4 tomas (amchay, amthu) se procesan con 4 tomas.
  - El archivo auxiliar 'faltantes.wav' se excluye del procesamiento automático.
  - Para otros locutores (pedro, sofia, etc.) se respeta su número configurado (por defecto 3).

Uso:
  python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor eva
  python3 ASR/scripts/limpieza/limpiar_palabras.py --locutor pedro --max_chunks 3
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

# ─── Configuración de Procesamiento ──────────────────────────
TARGET_FS       = 16000
TARGET_DB       = -3.0
SILENCE_PAD_MS  = 250     # Silencio de 250 ms añadido al inicio y final
MIN_CHUNK_MS    = 70      # Duración mínima para fonación válida (permite palabras monosilábicas cortas)
MIN_FILE_BYTES  = 1000
# ─────────────────────────────────────────────────────────────


def setup_ffmpeg():
    ffmpeg_path = which("ffmpeg") or "/usr/bin/ffmpeg"
    if not os.path.exists(ffmpeg_path):
        raise EnvironmentError("ffmpeg no encontrado. Asegúrate de instalar ffmpeg.")
    AudioSegment.converter = ffmpeg_path


def normalize(audio: AudioSegment, target_db: float = TARGET_DB) -> AudioSegment:
    """Normaliza la señal de audio completa al valor target_db (por defecto -3 dBFS)."""
    if audio.max_dBFS == float('-inf'):
        return audio
    return audio.apply_gain(target_db - audio.max_dBFS)


def detect_repetition_ranges(audio_normalized: AudioSegment, expected_chunks: int = 4) -> list:
    """
    Detecta las repeticiones directamente sobre el audio ya normalizado a -3 dBFS.
    Aprovecha los silencios inter-repetición reales sin fragmentar palabras
    ni manipular pausas internas que pertenezcan a la fonación.
    """
    thresholds = [-45, -42, -48, -40, -50, -38, -52]
    min_silence_lens = [450, 400, 500, 550, 350]

    best_ranges = []

    # 1. Búsqueda directa del número esperado de repeticiones
    for thresh in thresholds:
        for min_sil in min_silence_lens:
            raw_ranges = silence.detect_nonsilent(audio_normalized, min_silence_len=min_sil, silence_thresh=thresh)
            valid = [tuple(r) for r in raw_ranges if (r[1] - r[0]) >= MIN_CHUNK_MS]
            
            if len(valid) == expected_chunks:
                return valid
            if expected_chunks == 3 and len(valid) == 4:
                return valid
            if len(valid) <= expected_chunks and len(valid) > len(best_ranges):
                best_ranges = valid

    # 2. Si se esperaban 4 pero el archivo solo tiene 3 tomas limpias
    if not best_ranges and expected_chunks == 4:
        for thresh in thresholds:
            for min_sil in min_silence_lens:
                raw_ranges = silence.detect_nonsilent(audio_normalized, min_silence_len=min_sil, silence_thresh=thresh)
                valid = [tuple(r) for r in raw_ranges if (r[1] - r[0]) >= MIN_CHUNK_MS]
                if len(valid) == 3:
                    return valid

    return best_ranges


def refine_repetition_boundaries(audio: AudioSegment, start: int, end: int, max_left: int, max_right: int, silence_floor: float = -58.0, max_bridge_gap: int = 130) -> tuple:
    """
    Refina los puntos de corte inicial y final de la repetición:
      - Inicio: Expande hacia atrás buscando el mínimo sonido audible sobre el piso de silencio (-58 dBFS).
        Si encuentra una breve oclusión/pausa (< 130 ms, típica de consonantes eyectivas k', p', t' o clics
        glotalizados), la cruza para capturar el clic inicial completo. Si el silencio supera los 130 ms,
        se detiene de inmediato para ignorar ruidos aislados en medio de la pausa entre repeticiones.
      - Fin: Expande hacia adelante buscando el decaimiento completo de la palabra. Si encuentra una breve
        oclusión (< 130 ms, típica antes de sílabas finales como -ki, -ta, -tu, -pa), la cruza para capturar
        la sílaba final íntegra. Si el silencio supera los 130 ms, se detiene para no capturar ruidos externos.
      - Aplica márgenes limpios de 15 ms al inicio y 20 ms al final, acotados por max_left y max_right.
    """
    # 1. Inicio: expandir hacia atrás cruzando micro-cierres fonéticos (< 130 ms)
    cur_s = start
    while cur_s - 10 >= max_left:
        level = audio[cur_s - 10 : cur_s].dBFS
        if level > silence_floor:
            cur_s -= 10
        else:
            # Comprobar si hay un sonido inicial (clic eyectivo k', p', t' o aire) a menos de max_bridge_gap
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

    # 2. Fin: expandir hacia adelante cruzando micro-cierres fonéticos (< 130 ms)
    cur_e = end
    while cur_e + 10 <= max_right:
        level = audio[cur_e : cur_e + 10].dBFS
        if level > silence_floor:
            cur_e += 10
        else:
            # Comprobar si hay una sílaba final o liberación fonética a menos de max_bridge_gap
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


def process_audio(path: str, word_name: str, output_dir: str, app_dir: str = None, max_chunks: int = 4):
    """
    Procesa un archivo de audio crudo:
      1. Normaliza todo el audio a -3 dBFS.
      2. Detecta las repeticiones sin fusionar silencios en medio de palabras.
      3. Refina y recorta cada repetición correctamente desde su inicio hasta su final completo.
      4. Añade 250 ms de silencio al inicio y final.
      5. Exporta los archivos normalizados.
    """
    errores = []
    try:
        raw_audio = AudioSegment.from_file(path).set_frame_rate(TARGET_FS).set_channels(1)
    except Exception as e:
        return 0, [f"Error crítico abriendo archivo: {e}"]

    # Paso 1: Primero normalizar todo el audio a -3 dBFS
    audio = normalize(raw_audio, TARGET_DB)
    total_ms = len(audio)

    # Paso 2: Detectar bien las repeticiones sobre el audio normalizado
    ranges = detect_repetition_ranges(audio, expected_chunks=max_chunks)

    if not ranges:
        return 0, [f"No se detectó voz en el audio"]

    if len(ranges) < max_chunks:
        errores.append(f"Solo se detectaron {len(ranges)} de {max_chunks} repeticiones")

    # Silencio exacto de 250 ms para el inicio y final
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
        start_corte, end_corte = refine_repetition_boundaries(audio, start, end, max_left, max_right)
        chunk = audio[start_corte:end_corte]
        chunk_ms = len(chunk)

        if chunk_ms < MIN_CHUNK_MS:
            errores.append(f"Toma {chunk_id}: Descartada por muy corta ({chunk_ms}ms < {MIN_CHUNK_MS}ms)")
            continue

        # Paso 4: Agregar silencio de 250 ms al inicio y final
        final = padding + chunk + padding

        out_name = f"{word_name}_{str(chunk_id).zfill(2)}.wav"
        out_path = os.path.join(output_dir, out_name)

        try:
            final.export(out_path, format="wav", parameters=["-ar", str(TARGET_FS)])
            if verify_exported(out_path):
                exported += 1
                logging.info(f"  ✅ {out_name} exportado a ASR")
                
                if chunk_id == 1 and app_dir:
                    app_out_path = os.path.join(app_dir, f"{word_name}.wav")
                    shutil.copy2(out_path, app_out_path)
                    logging.info(f"  📱 {word_name}.wav copiado a App")
            else:
                errores.append(f"Toma {chunk_id}: Error de integridad tras exportar")
                if os.path.exists(out_path): os.remove(out_path)
        except Exception as e:
            errores.append(f"Toma {chunk_id}: Error al exportar: {e}")

    for idx in range(len(ranges), max_chunks):
        errores.append(f"Toma {idx+1}: No generada (no hay más tomas en el audio)")

    return exported, errores


def main():
    parser = argparse.ArgumentParser(description="Limpia y divide grabaciones originales de palabras en repeticiones.")
    parser.add_argument("--locutor", default="eva", help="Nombre del locutor (eva, pedro, sofia, lorenzo, roberto)")
    parser.add_argument("--input", default=None, help="Carpeta con grabaciones originales")
    parser.add_argument("--output", default=None, help="Carpeta de destino ASR")
    parser.add_argument("--max_chunks", type=int, default=None, help="Número de repeticiones esperadas por archivo (automático por locutor si no se especifica)")
    parser.add_argument("--app", action="store_true", help="Si se activa, copia la primera toma a UNITY/audios_palabras/{id}.wav")
    args = parser.parse_args()

    setup_ffmpeg()

    locutor_nombre = args.locutor.strip().lower()
    
    input_dir = args.input
    if not input_dir:
        candidatos = [
            os.path.join(project_root, "audios_originales", "palabras", args.locutor),
            os.path.join(project_root, "audios_originales", "palabras", args.locutor.capitalize()),
            os.path.join(project_root, "audios_originales", "palabras", args.locutor.lower()),
            os.path.join(asr_dir, "audios_originales", "palabras", args.locutor),
            os.path.join(asr_dir, "audios_originales", "palabras", args.locutor.capitalize()),
            os.path.join(asr_dir, "audios_originales", "palabras", args.locutor.lower()),
        ]
        input_dir = next((c for c in candidatos if os.path.exists(c)), candidatos[0])

    output_dir = args.output or os.path.join(asr_dir, "audios_palabras", locutor_nombre)
    app_dir = os.path.join(project_root, "UNITY", "audios_palabras") if args.app else None

    os.makedirs(output_dir, exist_ok=True)
    if app_dir:
        os.makedirs(app_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print(f"[ERROR] Carpeta de grabaciones originales no encontrada: {input_dir}")
        print("  Por favor, coloca los archivos de audio crudos en:")
        print(f"    audios_originales/palabras/{args.locutor}/")
        print("  o especifica la ruta con: --input /ruta/a/los/audios")
        return

    # Excluir 'faltantes.wav' ya que se recorta manualmente
    files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".wav", ".mp3", ".m4a", ".ogg"))
        and not f.endswith(":Zone.Identifier")
        and not f.lower().startswith("faltantes")
    )
    if not files:
        logging.warning(f"No se encontraron archivos de audio en {input_dir}")
        return

    # Limpiar previamente audios exportados viejos en la carpeta de destino para evitar tomas residuales
    for existing in os.listdir(output_dir):
        if existing.lower().endswith(".wav"):
            os.remove(os.path.join(output_dir, existing))

    print("=" * 70)
    print(f"🚀 INICIANDO LIMPIEZA Y DIVISIÓN DE AUDIOS")
    print(f"   Locutor:    {locutor_nombre.upper()}")
    print(f"   Archivos:   {len(files)} originales")
    print(f"   Entrada:    {input_dir}")
    print(f"   Salida ASR: {output_dir}")
    if app_dir:
        print(f"   Salida App: {app_dir}")
    print("=" * 70)

    total_real = 0
    reporte_incidencias = {}

    for idx_file, filename in enumerate(files):
        word_name = os.path.splitext(filename)[0].lower()
        
        # Regla: Para Eva, las primeras 19 palabras originalmente tienen 3 repeticiones
        # (se completarán con faltantes.wav recortando manualmente).
        # A partir de la palabra 20 (índice 19 en adelante), tienen 4 repeticiones.
        # Casos especiales regrabados con 4 repeticiones (amchay, amthu) esperan 4 tomas.
        if args.max_chunks is not None:
            chunks_para_este_archivo = args.max_chunks
        elif locutor_nombre == "eva":
            if word_name in ("amchay", "amthu"):
                chunks_para_este_archivo = 4
            elif idx_file < 19:
                chunks_para_este_archivo = 3
            else:
                chunks_para_este_archivo = 4
        else:
            chunks_para_este_archivo = 3

        logging.info(f"📂 [{idx_file+1:03d}/{len(files)}] Archivo: {filename} -> ID: {word_name} (Esperadas: {chunks_para_este_archivo} tomas)")
        
        count, errors = process_audio(
            os.path.join(input_dir, filename),
            word_name,
            output_dir,
            app_dir,
            max_chunks=chunks_para_este_archivo
        )
        total_real += count
        if errors:
            reporte_incidencias[filename] = errors

    print("\n" + "=" * 70)
    print(f"PROCESAMIENTO COMPLETADO: {total_real} tomas generadas en {output_dir}")
    if reporte_incidencias:
        print(f"⚠️ Advertencias/incidencias en {len(reporte_incidencias)} archivos.")
    else:
        print("✨ Todos los archivos fueron procesados y exportados sin incidencias.")
    print("=" * 70)


if __name__ == "__main__":
    main()
