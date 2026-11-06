"""
prepare_uchumataqu.py
Convierte los manifests JSON propios del corpus Uchumataqu al formato Lhotse
(cuts.jsonl.gz) y prepara el directorio lang_bpe requerido por las recetas
oficiales de k2-fsa/icefall (train.py, finetune.py, decode.py).

Este script es el puente entre el pipeline de preparación de datos propio del
proyecto (scripts/entrenamiento/preparar_dataset.py) y las recetas oficiales
de icefall (icefall_repo/egs/librispeech/ASR/zipformer/).

Fuentes:
  - ASR/data/manifests/train_manifest.json
  - ASR/data/manifests/val_manifest.json
  - ASR/data/manifests/test_manifest.json
  - ASR/datos_asr/corpus_asr_texto.txt
  - ASR/datos_asr/tokens.txt

Salidas en ASR/data/lhotse/:
  - uchumataqu_cuts_train.jsonl.gz (+ librispeech_cuts_train-clean-100.jsonl.gz)
  - uchumataqu_cuts_val.jsonl.gz   (+ librispeech_cuts_dev-clean.jsonl.gz, dev-other)
  - uchumataqu_cuts_test.jsonl.gz  (+ librispeech_cuts_test-clean.jsonl.gz, test-other)

Salidas en ASR/data/lang_bpe/:
  - bpe.model (modelo SentencePiece)
  - tokens.txt (inventario con <blk>=0)
  - words.txt (tabla de palabras para decodificación)

Uso:
  python3 ASR/pipeline_icefall/uchumataqu/prepare_uchumataqu.py
"""

import os
import sys
import json
import gzip
import shutil
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))
pipeline_icefall_dir = os.path.dirname(script_dir)
asr_dir = os.path.dirname(pipeline_icefall_dir)
project_root = os.path.dirname(asr_dir)


def convertir_entry_a_lhotse_cut(entry: dict, cut_idx: int) -> dict:
    """
    Convierte una entrada del manifest JSON propio a un objeto Cut de Lhotse.
    """
    utt_id = entry.get("utt_id", f"uch_{cut_idx:06d}")
    audio_path = entry.get("audio_path", "")
    duracion = float(entry.get("duracion", 0.0))
    locutor = entry.get("locutor", "unknown")
    fonemas = entry.get("fonemas", "")
    texto_uch = entry.get("texto_uch", "")
    texto_es = entry.get("texto_es", "")
    tipo = entry.get("tipo", "palabra")
    toma = entry.get("toma", 1)

    cut = {
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
                    "toma": toma
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
            "num_samples": int(duracion * 16000),
            "duration": duracion,
            "channel_ids": [0]
        },
        "custom": {
            "speaker": locutor,
            "tipo": tipo
        }
    }
    return cut


def convertir_manifest_a_lhotse(ruta_manifest_json: str, ruta_salida_gz: str) -> int:
    """Lee un manifest JSON propio y escribe el correspondiente cuts.jsonl.gz."""
    if not os.path.exists(ruta_manifest_json):
        print(f"[ERROR] No existe el manifest: {ruta_manifest_json}")
        return 0

    with open(ruta_manifest_json, "r", encoding="utf-8") as f:
        entries = json.load(f)

    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida_gz)), exist_ok=True)

    n_ok = 0
    n_skip = 0

    with gzip.open(ruta_salida_gz, "wt", encoding="utf-8") as gz_out:
        for idx, entry in enumerate(entries):
            audio_path = entry.get("audio_path", "")
            fonemas = entry.get("fonemas", "").strip()

            if not fonemas:
                n_skip += 1
                continue

            if not os.path.isabs(audio_path):
                audio_path = os.path.join(project_root, audio_path)
                entry["audio_path"] = audio_path

            if not os.path.exists(audio_path):
                n_skip += 1
                continue

            cut = convertir_entry_a_lhotse_cut(entry, idx)
            gz_out.write(json.dumps(cut, ensure_ascii=False) + "\n")
            n_ok += 1

    print(f"  [OK] {n_ok} cuts generados -> {os.path.basename(ruta_salida_gz)}")
    if n_skip > 0:
        print(f"  [AVISO] {n_skip} entradas omitidas (audio faltante o sin transcripción)")
    return n_ok


def crear_enlace_o_copia(src: str, dst: str):
    """Crea symlink relativo si es posible, o copia el archivo si ya existe o falla."""
    if os.path.exists(dst) or os.path.islink(dst):
        try:
            os.remove(dst)
        except OSError:
            pass
    try:
        os.symlink(os.path.basename(src), dst)
    except Exception:
        shutil.copyfile(src, dst)


def crear_aliases_receta_librispeech(output_dir: str, use_pitch_aug: bool = False):
    """
    Crea los archivos con nombres esperados por LibriSpeechAsrDataModule:
    - librispeech_cuts_train-clean-100.jsonl.gz -> uchumataqu_cuts_train.jsonl.gz (o _pitch)
    - librispeech_cuts_train-all-shuf.jsonl.gz  -> uchumataqu_cuts_train.jsonl.gz (o _pitch)
    - librispeech_cuts_dev-clean.jsonl.gz      -> uchumataqu_cuts_val.jsonl.gz
    - librispeech_cuts_dev-other.jsonl.gz      -> archivo gzip vacío
    - librispeech_cuts_test-clean.jsonl.gz     -> uchumataqu_cuts_test.jsonl.gz
    - librispeech_cuts_test-other.jsonl.gz     -> archivo gzip vacío
    """
    train_src = os.path.join(output_dir, "uchumataqu_cuts_train.jsonl.gz")
    pitch_src = os.path.join(output_dir, "uchumataqu_cuts_train_pitch.jsonl.gz")
    if use_pitch_aug and os.path.exists(pitch_src):
        train_src = pitch_src
        print(f"  [OK] Aliases de entrenamiento configurados con PITCH SHIFTING ({os.path.basename(pitch_src)})")
    else:
        print(f"  [OK] Aliases de entrenamiento configurados con audio estándar ({os.path.basename(train_src)})")

    val_src = os.path.join(output_dir, "uchumataqu_cuts_val.jsonl.gz")
    test_src = os.path.join(output_dir, "uchumataqu_cuts_test.jsonl.gz")

    if os.path.exists(train_src):
        crear_enlace_o_copia(train_src, os.path.join(output_dir, "librispeech_cuts_train-clean-100.jsonl.gz"))
        crear_enlace_o_copia(train_src, os.path.join(output_dir, "librispeech_cuts_train-all-shuf.jsonl.gz"))
        crear_enlace_o_copia(train_src, os.path.join(output_dir, "cuts_S.jsonl.gz"))

    if os.path.exists(val_src):
        crear_enlace_o_copia(val_src, os.path.join(output_dir, "librispeech_cuts_dev-clean.jsonl.gz"))
        crear_enlace_o_copia(val_src, os.path.join(output_dir, "cuts_DEV.jsonl.gz"))

    # Crear dev-other vacío para que train.py no falle al buscar dev_other_cuts()
    dev_other = os.path.join(output_dir, "librispeech_cuts_dev-other.jsonl.gz")
    with gzip.open(dev_other, "wt", encoding="utf-8") as f:
        pass

    if os.path.exists(test_src):
        crear_enlace_o_copia(test_src, os.path.join(output_dir, "librispeech_cuts_test-clean.jsonl.gz"))
        crear_enlace_o_copia(test_src, os.path.join(output_dir, "cuts_TEST.jsonl.gz"))

    # Crear test-other vacío
    test_other = os.path.join(output_dir, "librispeech_cuts_test-other.jsonl.gz")
    with gzip.open(test_other, "wt", encoding="utf-8") as f:
        pass

    print("  [OK] Aliases para LibriSpeechAsrDataModule (y Gigaspeech) generados correctamente en data/lhotse/")


def preparar_lang_bpe(lang_dir: str):
    """
    Prepara el directorio lang_bpe requerido por Zipformer:
    - words.txt: tabla de palabras para decodificación y grafo LG
    - tokens.txt: tabla de tokens fonéticos canónicos
    - bpe.model: modelo SentencePiece (si sentencepiece está disponible)
    """
    os.makedirs(lang_dir, exist_ok=True)
    lexicon_path = os.path.join(asr_dir, "datos_asr", "lexicon.txt")
    tokens_src = os.path.join(asr_dir, "datos_asr", "tokens.txt")
    corpus_text = os.path.join(asr_dir, "datos_asr", "corpus_asr_texto.txt")

    # 1. Generar words.txt
    words_dst = os.path.join(lang_dir, "words.txt")
    palabras = set()
    if os.path.exists(lexicon_path):
        with open(lexicon_path, "r", encoding="utf-8") as f:
            for line in f:
                p = line.strip().split("\t")[0]
                if p:
                    palabras.add(p)

    palabras_ordenadas = sorted(list(palabras))
    with open(words_dst, "w", encoding="utf-8") as f:
        f.write("<eps> 0\n")
        f.write("!SIL 1\n")
        f.write("<UNK> 2\n")
        idx = 3
        for p in palabras_ordenadas:
            f.write(f"{p} {idx}\n")
            idx += 1
        f.write(f"#0 {idx}\n")
        f.write(f"<s> {idx+1}\n")
        f.write(f"</s> {idx+2}\n")
    print(f"  [OK] words.txt generado en {words_dst} ({len(palabras_ordenadas)} palabras)")

    # 2. Copiar tokens.txt a lang_dir
    tokens_dst = os.path.join(lang_dir, "tokens.txt")
    if os.path.exists(tokens_src):
        shutil.copyfile(tokens_src, tokens_dst)
        print(f"  [OK] tokens.txt sincronizado en {tokens_dst}")

    # 3. Entrenar bpe.model si sentencepiece está disponible
    bpe_model_path = os.path.join(lang_dir, "bpe.model")
    try:
        import sentencepiece as spm
        if os.path.exists(corpus_text):
            model_prefix = os.path.join(lang_dir, "bpe_uchumataqu")
            spm.SentencePieceTrainer.train(
                input=corpus_text,
                vocab_size=60,
                model_type="unigram",
                model_prefix=model_prefix,
                character_coverage=1.0,
                user_defined_symbols=["<blk>", "<sos/eos>"],
                unk_id=2,
                bos_id=-1,
                eos_id=-1
            )
            shutil.copyfile(model_prefix + ".model", bpe_model_path)
            print(f"  [OK] bpe.model entrenado exitosamente en {bpe_model_path}")
    except ImportError:
        print("  [INFO] sentencepiece no está instalado en este entorno de Python.")
        print("         Se compilará automáticamente en el contenedor Docker o al instalar requirements.txt.")


def main():
    parser = argparse.ArgumentParser(
        description="Convierte manifests JSON de Uchumataqu a formato Lhotse y prepara lang_bpe para icefall"
    )
    parser.add_argument(
        "--manifests_dir",
        type=str,
        default=os.path.join(asr_dir, "data", "manifests"),
        help="Directorio con train/val/test_manifest.json"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=os.path.join(asr_dir, "data", "lhotse"),
        help="Directorio de salida para cuts.jsonl.gz"
    )
    parser.add_argument(
        "--lang_dir",
        type=str,
        default=os.path.join(asr_dir, "data", "lang_bpe"),
        help="Directorio lang para bpe.model, tokens.txt y words.txt"
    )
    parser.add_argument(
        "--use_pitch_aug",
        type=int,
        default=0,
        help="Si es 1, enlaza los aliases de entrenamiento al dataset aumentado por Pitch Shifting"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("PREPARACIÓN INTEGRAL LHOTSE Y LANG_BPE PARA RECETAS ICEFALL")
    print("=" * 70)

    splits = {
        "train": "train_manifest.json",
        "val": "val_manifest.json",
        "test": "test_manifest.json"
    }

    total = 0
    for split_name, fname in splits.items():
        ruta_json = os.path.join(args.manifests_dir, fname)
        ruta_gz = os.path.join(args.output_dir, f"uchumataqu_cuts_{split_name}.jsonl.gz")

        if not os.path.exists(ruta_json):
            print(f"[AVISO] No encontrado: {ruta_json}. Omitiendo split '{split_name}'.")
            print("  -> Ejecuta primero: python3 scripts/entrenamiento/preparar_dataset.py")
            continue

        n = convertir_manifest_a_lhotse(ruta_json, ruta_gz)
        total += n

    # Generar aliases para que las recetas oficiales lean los cortes
    crear_aliases_receta_librispeech(args.output_dir, use_pitch_aug=(args.use_pitch_aug == 1))

    # Preparar lang_bpe
    preparar_lang_bpe(args.lang_dir)

    print("\n" + "=" * 70)
    print(f"PREPARACIÓN COMPLETADA CON ÉXITO.")
    print(f"Cortes Lhotse: {args.output_dir} ({total} cuts procesados)")
    print(f"Lang/BPE dir : {args.lang_dir}")
    print("=" * 70)
    print("\nTodo listo para entrenar con las recetas oficiales de Icefall:")
    print("  bash pipeline_icefall/run_train_scratch.sh   # Entrenamiento desde cero")
    print("  bash pipeline_icefall/run_finetune.sh        # Fine-tuning con checkpoint")
    print("  bash pipeline_icefall/run_decode.sh          # Evaluación en test set")


if __name__ == "__main__":
    main()
