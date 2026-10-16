#!/usr/bin/env python3
"""
sincronizar_unity.py
Sincronizador automático y seguro de contenido desde WSL hacia proyecto Unity en Windows.

Sincroniza de forma controlada ÚNICAMENTE:
  - UNITY/datos_app/ -> Assets/Content/Data/ (archivos .json)
  (Los audios y documentos Markdown quedan excluidos de esta sincronización).

Uso:
  python sincronizar_unity.py [--dry-run] [--delete] [--unity-path /ruta/unity]
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


# Archivos y extensiones excluidos explícitamente del runtime Unity
ARCHIVOS_EXCLUIDOS_DATOS = {
    "lecciones.json",
    "lexicon.txt",
    "tokens.txt",
}

EXTENSIONES_DATOS_PERMITIDAS = {".json"}


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
    """Valida la existencia de las rutas requeridas en WSL y Unity para los datos JSON."""
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
    rutas_wsl_requeridas = [
        unity_source,
        unity_source / "datos_app",
    ]

    for ruta in rutas_wsl_requeridas:
        if not ruta.exists() or not ruta.is_dir():
            print(f"[ERROR] Directorio requerido en WSL no encontrado: {ruta}")
            sys.exit(1)

    return unity_source


def obtener_destinos_autorizados(unity_root: Path) -> list[Path]:
    """Retorna la lista de rutas base autorizadas para escritura en Unity (exclusivamente Data JSON)."""
    return [
        (unity_root / "Assets" / "Content" / "Data").resolve(),
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

        if item.name in excluded:
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
    excluded_names: set[str] | None = None,
    recursive: bool = False,
) -> Estadisticas:
    """Sincroniza una categoría de origen a destino con comparación SHA-256 y detección de huérfanos."""
    stats = Estadisticas()
    print(f"\n[INFO] Sincronizando {nombre_categoria}...")

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    archivos_fuente = listar_archivos_fuente(
        source_dir=source_dir,
        allowed_extensions=allowed_extensions,
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
                print(f"[DRY-RUN][NUEVO] {rel_str}")
            else:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                print(f"[NUEVO] {rel_str}")
            stats.nuevos += 1
        else:
            sha_src = calcular_sha256(src_file)
            sha_dst = calcular_sha256(dst_file)

            if sha_src != sha_dst:
                if dry_run:
                    print(f"[DRY-RUN][ACTUALIZAR] {rel_str}")
                else:
                    shutil.copy2(src_file, dst_file)
                    print(f"[ACTUALIZADO] {rel_str}")
                stats.actualizados += 1
            else:
                print(f"[SIN CAMBIOS] {rel_str}")
                stats.sin_cambios += 1

    # Detección y gestión de huérfanos en destino
    if dest_dir.exists():
        dest_iterator = dest_dir.rglob("*") if recursive else dest_dir.glob("*")
        for dst_item in sorted(dest_iterator):
            if not dst_item.is_file():
                continue

            if dst_item.name.endswith(".meta") or dst_item.suffix.lower() == ".meta":
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
                        print(f"[DRY-RUN][ELIMINARIA] {rel_str}")
                    else:
                        is_asset = "Assets" in dst_item.parts
                        dst_item.unlink()
                        stats.eliminados += 1
                        if is_asset:
                            print(f"[INFO] Asset eliminado; Unity gestionará su metadata: {rel_str}")
                        else:
                            print(f"[ELIMINADO] {rel_str}")
                else:
                    if dry_run:
                        print(f"[DRY-RUN][HUERFANO] {rel_str}")
                    else:
                        print(f"[HUERFANO EN UNITY] {rel_str}")

    return stats


def mostrar_resumen(
    stats_datos: Estadisticas,
    unity_root: Path,
    dry_run: bool,
) -> None:
    """Muestra el resumen final formateado para la sincronización exclusiva de JSON."""
    print("\n================================================")
    print("SINCRONIZACIÓN WSL → UNITY COMPLETADA (SOLO JSON)")
    print("================================================")

    print("\nDatos JSON (Assets/Content/Data):")
    print(f"  Nuevos:        {stats_datos.nuevos}")
    print(f"  Actualizados:  {stats_datos.actualizados}")
    print(f"  Sin cambios:   {stats_datos.sin_cambios}")
    print(f"  Huérfanos:     {stats_datos.huerfanos}")

    print(f"\nDestino Unity:\n  {unity_root / 'Assets' / 'Content' / 'Data'}")

    print("\nEstado:")
    if dry_run:
        print("  SIMULACIÓN — no se modificó ningún archivo")
    else:
        print("  OK — Archivos JSON sincronizados exitosamente")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincronizador automático y seguro de archivos JSON desde WSL hacia el proyecto Unity (sin audios)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula las operaciones sin modificar ni crear archivos.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Elimina los archivos JSON huérfanos en Assets/Content/Data (sin tocar .meta).",
    )
    parser.add_argument(
        "--unity-path",
        type=str,
        default=None,
        help="Ruta al proyecto Unity (sobrescribe UNITY_PROJECT_PATH).",
    )

    args = parser.parse_args()

    wsl_root = obtener_raiz_proyecto()
    unity_root = obtener_configuracion(args.unity_path, wsl_root)

    print(f"[INFO] Proyecto WSL: {wsl_root}")
    print(f"[INFO] Proyecto Unity: {unity_root}")
    print("[INFO] Alcance: Sincronización EXCLUSIVA de archivos JSON (sin audios)")
    if args.dry_run:
        print("[INFO] Modo: SIMULACIÓN (--dry-run)")
    if args.delete:
        print("[INFO] Modo: Eliminación de huérfanos activada (--delete)")

    unity_source = validar_rutas(wsl_root, unity_root)
    authorized_roots = obtener_destinos_autorizados(unity_root)

    # Sincronizar únicamente datos JSON (UNITY/datos_app/ -> Assets/Content/Data/)
    stats_datos = sincronizar_categoria(
        nombre_categoria="datos JSON",
        source_dir=unity_source / "datos_app",
        dest_dir=unity_root / "Assets" / "Content" / "Data",
        allowed_extensions=EXTENSIONES_DATOS_PERMITIDAS,
        authorized_roots=authorized_roots,
        dry_run=args.dry_run,
        delete_orphans=args.delete,
        excluded_names=ARCHIVOS_EXCLUIDOS_DATOS,
        recursive=False,
    )

    mostrar_resumen(
        stats_datos=stats_datos,
        unity_root=unity_root,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print("\n[OK] Sincronización de JSON terminada exitosamente.")


if __name__ == "__main__":
    main()
