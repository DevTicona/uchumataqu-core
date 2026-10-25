#!/usr/bin/env python3
"""
sincronizar_unity.py
Sincronizador automático y seguro de contenido desde WSL hacia proyecto Unity en Windows.

Sincroniza de forma controlada y eficiente:
  - Datos JSON: UNITY/datos_app/ -> Assets/Content/Data/
    (lecciones_compiladas.json, palabras.json, oraciones.json)
  - Datos PLN (HFST): PLN/hfst/export/pln-hfst-v1/ -> Assets/Content/Data/PLN/
    (analyses.json, lookup-index.json)
  - Audios Palabras: UNITY/audios_palabras/ -> Assets/Content/Audio/Palabras/ (*.wav)
  - Audios Oraciones: UNITY/audios_oraciones/ -> Assets/Content/Audio/Oraciones/ (*.wav)

Condición estricta de sincronización:
  - Solo copia archivos si son NUEVOS o si están ACTUALIZADOS (modificados por hash SHA-256).
  - Los archivos idénticos sin cambios NO se transfieren ni sobrescriben.
  - Los archivos .meta de Unity son preservados intactos.

Uso:
  python sincronizar_unity.py [--dry-run] [--delete] [--verbose] [--unity-path /ruta/unity]
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
from dataclasses import dataclass


# Ruta predeterminada del proyecto Unity en Windows
DEFAULT_UNITY_PATH = r"D:\unity\Uchumataqu"


@dataclass
class Estadisticas:
    nuevos: int = 0
    actualizados: int = 0
    sin_cambios: int = 0
    huerfanos: int = 0
    eliminados: int = 0


# Archivos JSON permitidos explícitamente para Unity
ARCHIVOS_DATOS_PERMITIDOS = {
    "lecciones_compiladas.json",
    "palabras.json",
    "oraciones.json",
}

# Archivos PLN (HFST) permitidos para Unity
ARCHIVOS_PLN_PERMITIDOS = {
    "analyses.json",
    "lookup-index.json",
}

EXTENSIONES_DATOS_PERMITIDAS = {".json"}
EXTENSIONES_AUDIO_PERMITIDAS = {".wav"}


def obtener_raiz_proyecto() -> Path:
    """Retorna la raíz del proyecto WSL donde se ubica este script."""
    return Path(__file__).resolve().parent


def obtener_directorio_fuente_unity(wsl_root: Path) -> Path:
    """Retorna la carpeta de contenido para Unity (prefiere UNITY/, fallback a Para_Unity/)."""
    dir_unity = wsl_root / "UNITY"
    if dir_unity.exists() and dir_unity.is_dir():
        return dir_unity
    return wsl_root / "Para_Unity"


def convertir_ruta_windows_a_wsl(path_str: str) -> Path:
    """Convierte rutas en formato Windows (ej: D:\\unity\\Uchumataqu) a ruta WSL (/mnt/d/unity/Uchumataqu)."""
    p = path_str.strip().strip("\"'")
    match = re.match(r"^([a-zA-Z]):[\\/](.*)", p)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}").resolve()
    return Path(p).resolve()


def cargar_env_local(wsl_root: Path) -> dict[str, str]:
    """Carga variables desde un archivo .env local si existe."""
    env_vars = {}
    env_file = wsl_root / ".env"
    if env_file.is_file():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key:
                        env_vars[key] = val
        except Exception as e:
            print(f"[WARN] No se pudo leer .env: {e}")
    return env_vars


def obtener_configuracion(cli_unity_path: str | None, wsl_root: Path) -> Path:
    """Obtiene y resuelve la ruta del proyecto Unity desde CLI, os.environ, .env o la ruta por defecto."""
    path_str = cli_unity_path
    if not path_str:
        path_str = os.environ.get("UNITY_PROJECT_PATH")
    if not path_str:
        env_vars = cargar_env_local(wsl_root)
        path_str = env_vars.get("UNITY_PROJECT_PATH")
    if not path_str:
        path_str = DEFAULT_UNITY_PATH

    return convertir_ruta_windows_a_wsl(path_str)


def validar_rutas(wsl_root: Path, unity_root: Path) -> Path:
    """Valida la existencia de las rutas requeridas en WSL y Unity para los datos y audios."""
    # Validación Unity
    if not unity_root.exists():
        print(f"[ERROR] La ruta del proyecto Unity no existe: {unity_root}")
        sys.exit(1)

    unity_assets = unity_root / "Assets"
    if not unity_assets.exists() or not unity_assets.is_dir():
        print(f"[ERROR] No se encontró el directorio Assets en Unity: {unity_assets}")
        sys.exit(1)

    # Validación WSL
    if not wsl_root.exists():
        print(f"[ERROR] La raíz del proyecto WSL no existe: {wsl_root}")
        sys.exit(1)

    unity_source = obtener_directorio_fuente_unity(wsl_root)
    pln_source = wsl_root / "PLN" / "hfst" / "export" / "pln-hfst-v1"
    asr_source = wsl_root / "ASR" / "models" / "exported_onnx"
    rutas_wsl_requeridas = [
        unity_source,
        unity_source / "datos_app",
        unity_source / "audios_palabras",
        unity_source / "audios_oraciones",
        pln_source,
        asr_source,
    ]

    for ruta in rutas_wsl_requeridas:
        if not ruta.exists() or not ruta.is_dir():
            print(f"[ERROR] Directorio requerido en WSL no encontrado: {ruta}")
            sys.exit(1)

    return unity_source


def obtener_destinos_autorizados(unity_root: Path) -> list[Path]:
    """Retorna la lista de rutas base autorizadas para escritura en Unity."""
    return [
        (unity_root / "Assets" / "Content" / "Data").resolve(),
        (unity_root / "Assets" / "Content" / "Data" / "PLN").resolve(),
        (unity_root / "Assets" / "Content" / "Audio" / "Palabras").resolve(),
        (unity_root / "Assets" / "Content" / "Audio" / "Oraciones").resolve(),
        (unity_root / "Assets" / "StreamingAssets" / "sherpa").resolve(),
    ]


def es_destino_autorizado(target_path: Path, authorized_roots: list[Path]) -> bool:
    """Verifica estrictamente que target_path pertenezca a uno de los destinos autorizados."""
    resolved = target_path.resolve()
    for auth_root in authorized_roots:
        if resolved == auth_root:
            return True
        try:
            resolved.relative_to(auth_root)
            return True
        except ValueError:
            continue
    return False


def calcular_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en bloques."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def listar_archivos_fuente(
    source_dir: Path,
    allowed_extensions: set[str],
    allowed_names: set[str] | None = None,
    excluded_names: set[str] | None = None,
    recursive: bool = False,
) -> list[Path]:
    """Lista los archivos válidos desde el origen aplicando filtros."""
    excluded = excluded_names or set()
    archivos = []

    iterator = source_dir.rglob("*") if recursive else source_dir.glob("*")
    for item in sorted(iterator):
        if not item.is_file():
            continue

        if item.name.endswith(".meta") or item.suffix.lower() == ".meta":
            continue

        if excluded and item.name in excluded:
            continue

        if allowed_names and item.name not in allowed_names:
            continue

        if item.suffix.lower() not in allowed_extensions:
            continue

        archivos.append(item)

    return archivos


def sincronizar_categoria(
    nombre_categoria: str,
    source_dir: Path,
    dest_dir: Path,
    allowed_extensions: set[str],
    authorized_roots: list[Path],
    dry_run: bool,
    delete_orphans: bool,
    allowed_names: set[str] | None = None,
    excluded_names: set[str] | None = None,
    recursive: bool = False,
    verbose: bool = False,
) -> Estadisticas:
    """Sincroniza una categoría de origen a destino con comparación SHA-256 y detección de huérfanos."""
    stats = Estadisticas()
    print(f"\n[INFO] Sincronizando {nombre_categoria}...")

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    archivos_fuente = listar_archivos_fuente(
        source_dir=source_dir,
        allowed_extensions=allowed_extensions,
        allowed_names=allowed_names,
        excluded_names=excluded_names,
        recursive=recursive,
    )

    fuente_rel_set: set[str] = set()

    for src_file in archivos_fuente:
        rel_path = src_file.relative_to(source_dir)
        rel_str = str(rel_path)
        fuente_rel_set.add(rel_str)
        dst_file = dest_dir / rel_path

        if not es_destino_autorizado(dst_file, authorized_roots):
            print(f"[ERROR] Intento de escritura fuera de destino autorizado: {dst_file}")
            sys.exit(1)

        if not dst_file.exists():
            if dry_run:
                print(f"  [DRY-RUN][NUEVO] {rel_str}")
            else:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                print(f"  [NUEVO] {rel_str}")
            stats.nuevos += 1
        else:
            # Comprobación rápida por tamaño y luego SHA-256 exacta
            tam_src = src_file.stat().st_size
            tam_dst = dst_file.stat().st_size

            cambiado = False
            if tam_src != tam_dst:
                cambiado = True
            else:
                sha_src = calcular_sha256(src_file)
                sha_dst = calcular_sha256(dst_file)
                cambiado = (sha_src != sha_dst)

            if cambiado:
                if dry_run:
                    print(f"  [DRY-RUN][ACTUALIZAR] {rel_str}")
                else:
                    shutil.copy2(src_file, dst_file)
                    print(f"  [ACTUALIZADO] {rel_str}")
                stats.actualizados += 1
            else:
                if verbose:
                    print(f"  [SIN CAMBIOS] {rel_str}")
                stats.sin_cambios += 1

    if not verbose and stats.sin_cambios > 0:
        print(f"  ({stats.sin_cambios} archivos sin cambios no requirieron sincronización)")

    # Detección y gestión de huérfanos en destino
    if dest_dir.exists():
        dest_iterator = dest_dir.rglob("*") if recursive else dest_dir.glob("*")
        for dst_item in sorted(dest_iterator):
            if not dst_item.is_file():
                continue

            if dst_item.name.endswith(".meta") or dst_item.suffix.lower() == ".meta":
                continue

            # Si hay un conjunto estricto de nombres permitidos, solo evaluar huérfanos entre ellos
            if allowed_names and dst_item.name not in allowed_names:
                continue

            if dst_item.suffix.lower() not in allowed_extensions:
                continue

            rel_path = dst_item.relative_to(dest_dir)
            rel_str = str(rel_path)

            if rel_str not in fuente_rel_set:
                stats.huerfanos += 1

                if not es_destino_autorizado(dst_item, authorized_roots):
                    print(f"[ERROR] Ruta de destino no autorizada detectada: {dst_item}")
                    sys.exit(1)

                if delete_orphans:
                    if dry_run:
                        print(f"  [DRY-RUN][ELIMINARIA] {rel_str}")
                    else:
                        dst_item.unlink()
                        stats.eliminados += 1
                        print(f"  [INFO] Asset eliminado; Unity gestionará su metadata: {rel_str}")
                else:
                    if dry_run:
                        print(f"  [DRY-RUN][HUERFANO] {rel_str}")
                    else:
                        print(f"  [HUERFANO EN UNITY] {rel_str}")

    return stats


def sincronizar_asr_sherpa(
    wsl_root: Path,
    unity_root: Path,
    authorized_roots: list[Path],
    dry_run: bool = False,
    verbose: bool = False,
) -> Estadisticas:
    """Sincroniza el modelo ASR cuantizado INT8 (model.int8.bin) y tokens.txt a Assets/StreamingAssets/sherpa/."""
    stats = Estadisticas()
    dest_dir = unity_root / "Assets" / "StreamingAssets" / "sherpa"

    print("\n[INFO] Sincronizando modelo ASR Sherpa-ONNX (model.int8.bin, tokens.txt)...")

    mapeo_archivos = [
        (wsl_root / "ASR" / "models" / "exported_onnx" / "model.int8.onnx", dest_dir / "model.int8.bin"),
        (wsl_root / "ASR" / "models" / "exported_onnx" / "tokens.txt", dest_dir / "tokens.txt"),
    ]

    for src_file, dst_file in mapeo_archivos:
        if not src_file.exists():
            print(f"[ERROR] Archivo fuente de ASR no encontrado: {src_file}")
            sys.exit(1)

        if not es_destino_autorizado(dst_file, authorized_roots):
            print(f"[ERROR] Intento de escritura fuera de destino autorizado: {dst_file}")
            sys.exit(1)

        rel_str = dst_file.name
        if not dst_file.exists():
            if dry_run:
                print(f"  [DRY-RUN][NUEVO] {rel_str}")
            else:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                print(f"  [NUEVO] {rel_str}")
            stats.nuevos += 1
        else:
            tam_src = src_file.stat().st_size
            tam_dst = dst_file.stat().st_size
            cambiado = False
            if tam_src != tam_dst:
                cambiado = True
            else:
                sha_src = calcular_sha256(src_file)
                sha_dst = calcular_sha256(dst_file)
                cambiado = (sha_src != sha_dst)

            if cambiado:
                if dry_run:
                    print(f"  [DRY-RUN][ACTUALIZAR] {rel_str}")
                else:
                    shutil.copy2(src_file, dst_file)
                    print(f"  [ACTUALIZADO] {rel_str}")
                stats.actualizados += 1
            else:
                if verbose:
                    print(f"  [SIN CAMBIOS] {rel_str}")
                stats.sin_cambios += 1

    if not verbose and stats.sin_cambios > 0:
        print(f"  ({stats.sin_cambios} archivos sin cambios no requirieron sincronización)")

    return stats


def mostrar_resumen(
    stats_datos: Estadisticas,
    stats_pln: Estadisticas,
    stats_audios_palabras: Estadisticas,
    stats_audios_oraciones: Estadisticas,
    stats_asr: Estadisticas,
    unity_root: Path,
    dry_run: bool,
) -> None:
    """Muestra el resumen final formateado de la sincronización."""
    print("\n================================================")
    print("RESUMEN DE SINCRONIZACIÓN WSL → UNITY")
    print("================================================")

    def imprimir_bloque(titulo: str, stats: Estadisticas, ruta_dest: Path):
        print(f"\n{titulo} ({ruta_dest.name}):")
        print(f"  Nuevos:        {stats.nuevos}")
        print(f"  Actualizados:  {stats.actualizados}")
        print(f"  Sin cambios:   {stats.sin_cambios}")
        if stats.huerfanos > 0:
            print(f"  Huérfanos:     {stats.huerfanos}")
        if stats.eliminados > 0:
            print(f"  Eliminados:    {stats.eliminados}")

    imprimir_bloque(
        "Datos JSON",
        stats_datos,
        unity_root / "Assets" / "Content" / "Data",
    )
    imprimir_bloque(
        "Datos PLN (HFST)",
        stats_pln,
        unity_root / "Assets" / "Content" / "Data" / "PLN",
    )
    imprimir_bloque(
        "Audios Palabras",
        stats_audios_palabras,
        unity_root / "Assets" / "Content" / "Audio" / "Palabras",
    )
    imprimir_bloque(
        "Audios Oraciones",
        stats_audios_oraciones,
        unity_root / "Assets" / "Content" / "Audio" / "Oraciones",
    )
    imprimir_bloque(
        "Modelo ASR (Sherpa)",
        stats_asr,
        unity_root / "Assets" / "StreamingAssets" / "sherpa",
    )

    total_nuevos = stats_datos.nuevos + stats_pln.nuevos + stats_audios_palabras.nuevos + stats_audios_oraciones.nuevos + stats_asr.nuevos
    total_actualizados = stats_datos.actualizados + stats_pln.actualizados + stats_audios_palabras.actualizados + stats_audios_oraciones.actualizados + stats_asr.actualizados
    total_sin_cambios = stats_datos.sin_cambios + stats_pln.sin_cambios + stats_audios_palabras.sin_cambios + stats_audios_oraciones.sin_cambios + stats_asr.sin_cambios

    print("\n------------------------------------------------")
    print(f"TOTAL: {total_nuevos} nuevos, {total_actualizados} actualizados, {total_sin_cambios} sin cambios")
    print("------------------------------------------------")

    print("\nEstado:")
    if dry_run:
        print("  SIMULACIÓN — no se modificó ningún archivo en Unity")
    else:
        print("  OK — Sincronización completada exitosamente")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincronizador automático y seguro de JSON (lecciones_compiladas, palabras, oraciones) y Audios desde WSL hacia Unity."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula las operaciones sin modificar ni crear archivos.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Elimina los archivos huérfanos en destinos autorizados de Unity (sin tocar .meta).",
    )
    parser.add_argument(
        "--unity-path",
        type=str,
        default=None,
        help="Ruta al proyecto Unity (sobrescribe UNITY_PROJECT_PATH).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Muestra todos los archivos sin cambios en detalle.",
    )

    args = parser.parse_args()

    wsl_root = obtener_raiz_proyecto()
    unity_root = obtener_configuracion(args.unity_path, wsl_root)

    print(f"[INFO] Proyecto WSL: {wsl_root}")
    print(f"[INFO] Proyecto Unity: {unity_root}")
    print("[INFO] Alcance:")
    print("  - Datos JSON: lecciones_compiladas.json, palabras.json, oraciones.json")
    print("  - Datos PLN (HFST): PLN/hfst/export/pln-hfst-v1/ -> Assets/Content/Data/PLN/ (analyses.json, lookup-index.json)")
    print("  - Audios Palabras: UNITY/audios_palabras/ -> Assets/Content/Audio/Palabras/")
    print("  - Audios Oraciones: UNITY/audios_oraciones/ -> Assets/Content/Audio/Oraciones/")
    print("  - Modelo ASR (Sherpa): ASR/models/exported_onnx/ -> Assets/StreamingAssets/sherpa/ (model.int8.bin, tokens.txt)")
    if args.dry_run:
        print("[INFO] Modo: SIMULACIÓN (--dry-run)")
    if args.delete:
        print("[INFO] Modo: Eliminación de huérfanos activada (--delete)")

    unity_source = validar_rutas(wsl_root, unity_root)
    authorized_roots = obtener_destinos_autorizados(unity_root)

    # 1. Sincronizar datos JSON (EXCLUSIVAMENTE lecciones_compiladas.json, palabras.json, oraciones.json)
    stats_datos = sincronizar_categoria(
        nombre_categoria="datos JSON (lecciones_compiladas, palabras, oraciones)",
        source_dir=unity_source / "datos_app",
        dest_dir=unity_root / "Assets" / "Content" / "Data",
        allowed_extensions=EXTENSIONES_DATOS_PERMITIDAS,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        delete_orphans=args.delete,
        allowed_names=ARCHIVOS_DATOS_PERMITIDOS,
        recursive=False,
        verbose=args.verbose,
    )

    # 2. Sincronizar datos PLN (analyses.json y lookup-index.json)
    stats_pln = sincronizar_categoria(
        nombre_categoria="datos PLN (analyses.json, lookup-index.json)",
        source_dir=wsl_root / "PLN" / "hfst" / "export" / "pln-hfst-v1",
        dest_dir=unity_root / "Assets" / "Content" / "Data" / "PLN",
        allowed_extensions=EXTENSIONES_DATOS_PERMITIDAS,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        delete_orphans=args.delete,
        allowed_names=ARCHIVOS_PLN_PERMITIDOS,
        recursive=False,
        verbose=args.verbose,
    )

    # 3. Sincronizar Audios Palabras (UNITY/audios_palabras/ -> Assets/Content/Audio/Palabras/)
    stats_audios_palabras = sincronizar_categoria(
        nombre_categoria="audios de palabras",
        source_dir=unity_source / "audios_palabras",
        dest_dir=unity_root / "Assets" / "Content" / "Audio" / "Palabras",
        allowed_extensions=EXTENSIONES_AUDIO_PERMITIDAS,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        delete_orphans=args.delete,
        recursive=False,
        verbose=args.verbose,
    )

    # 4. Sincronizar Audios Oraciones (UNITY/audios_oraciones/ -> Assets/Content/Audio/Oraciones/)
    stats_audios_oraciones = sincronizar_categoria(
        nombre_categoria="audios de oraciones",
        source_dir=unity_source / "audios_oraciones",
        dest_dir=unity_root / "Assets" / "Content" / "Audio" / "Oraciones",
        allowed_extensions=EXTENSIONES_AUDIO_PERMITIDAS,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        delete_orphans=args.delete,
        recursive=False,
        verbose=args.verbose,
    )

    # 5. Sincronizar Modelo ASR (Sherpa-ONNX model.int8.bin y tokens.txt)
    stats_asr = sincronizar_asr_sherpa(
        wsl_root=wsl_root,
        unity_root=unity_root,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    mostrar_resumen(
        stats_datos=stats_datos,
        stats_pln=stats_pln,
        stats_audios_palabras=stats_audios_palabras,
        stats_audios_oraciones=stats_audios_oraciones,
        stats_asr=stats_asr,
        unity_root=unity_root,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print("\n[OK] Sincronización completada exitosamente.")


if __name__ == "__main__":
    main()
