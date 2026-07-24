from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator


APP_DATA_DIR_NAME = "NexarFinanzas"
CACHE_FILE_NAME = "license_cache.json"
_FINANZAS_PRODUCT_NAMES = {"nexar-finanzas", "nexar_finanzas", "nexarfinanzas"}


def get_user_data_dir(
    *,
    system: str | None = None,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the native per-user data directory used by licensing files."""
    current_system = system or platform.system()
    env = os.environ if environ is None else environ
    user_home = Path.home() if home is None else Path(home)

    if current_system == "Windows":
        base = env.get("LOCALAPPDATA")
        if not base:
            base = str(user_home / "AppData" / "Local")
        return Path(base).expanduser() / APP_DATA_DIR_NAME

    if current_system == "Darwin":
        return user_home.expanduser() / "Library" / "Application Support" / APP_DATA_DIR_NAME

    base = Path(env["XDG_DATA_HOME"]).expanduser() if env.get("XDG_DATA_HOME") else None
    if base is None or not base.is_absolute():
        base = user_home.expanduser() / ".local" / "share"
    return base / APP_DATA_DIR_NAME


def get_license_cache_path(**kwargs) -> Path:
    return get_user_data_dir(**kwargs) / CACHE_FILE_NAME


def ensure_license_cache_directory(cache_path: Path | None = None) -> Path:
    destination = Path(cache_path) if cache_path is not None else get_license_cache_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _known_legacy_cache_paths() -> tuple[Path, ...]:
    candidates = [Path.cwd() / CACHE_FILE_NAME]
    source_root = Path(__file__).resolve().parent.parent
    candidates.append(source_root / CACHE_FILE_NAME)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / CACHE_FILE_NAME)

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def _is_finanzas_cache(payload: object, source: Path) -> bool:
    lowered_parts = {part.lower().replace(" ", "").replace("_", "-") for part in source.parts}
    if any(
        "nexar-tienda" in part
        or "nexartienda" in part
        or "nexar-comercio" in part
        or "nexarcomercio" in part
        for part in lowered_parts
    ):
        return False
    if not isinstance(payload, dict):
        return False

    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload
    product = (
        data.get("product")
        or data.get("producto")
        or data.get("product_name")
        or payload.get("product")
        or payload.get("producto")
    )
    if product:
        return str(product).strip().lower() in _FINANZAS_PRODUCT_NAMES

    normalized_source = str(source.parent).lower().replace(" ", "").replace("_", "-")
    return "nexar-finanzas" in normalized_source or "nexarfinanzas" in normalized_source


def atomic_write_json(destination: Path, payload: object) -> None:
    destination = ensure_license_cache_directory(Path(destination))
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def migrate_legacy_license_cache(
    destination: Path | None = None,
    *,
    legacy_paths: Iterable[Path] | None = None,
) -> bool:
    target = ensure_license_cache_directory(destination)
    if target.exists():
        return False

    for source in legacy_paths or _known_legacy_cache_paths():
        candidate = Path(source)
        if candidate == target or not candidate.is_file():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as legacy_file:
                payload = json.load(legacy_file)
            if not _is_finanzas_cache(payload, candidate):
                logging.warning("[LICENSE] Cache legacy ignorado por no pertenecer a Nexar Finanzas: %s", candidate)
                continue
            atomic_write_json(target, payload)
            logging.info("[LICENSE] Cache legacy migrado desde %s hacia %s", candidate, target)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, TypeError, ValueError) as exc:
            logging.warning("[LICENSE] No se pudo migrar el cache legacy %s: %s", candidate, exc)
    return False


def atomic_save_license_cache(
    license_data: dict,
    *,
    destination: Path | None = None,
    last_check: str | None = None,
) -> None:
    if not isinstance(license_data, dict) or not license_data:
        raise ValueError("Los datos de licencia para cache deben ser un objeto JSON no vacio.")
    atomic_write_json(
        destination or get_license_cache_path(),
        {
            "data": license_data,
            "last_check": last_check or datetime.now().isoformat(),
        },
    )


@contextmanager
def sdk_cache_transaction(config) -> Iterator[tuple[object, Callable[[], None]]]:
    """
    Isolate the SDK's non-atomic writer in a temporary file and atomically
    promote a valid result to the canonical cache after successful validation.
    """
    canonical = Path(config.resolved_cache_file)
    ensure_license_cache_directory(canonical)
    migrate_legacy_license_cache(canonical)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{canonical.name}.sdk.",
        suffix=".tmp",
        dir=canonical.parent,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    if canonical.exists():
        shutil.copyfile(canonical, temporary)
    else:
        temporary.unlink(missing_ok=True)

    transactional_config = replace(config, cache_file=temporary, cache_dir=None)
    committed = False

    def commit() -> None:
        nonlocal committed
        if not temporary.is_file():
            raise OSError(f"El SDK no genero el cache temporal esperado: {temporary}")
        with temporary.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
        if not _is_finanzas_cache(payload, temporary):
            raise ValueError("El SDK genero un cache invalido o de otro producto.")
        os.replace(temporary, canonical)
        committed = True

    try:
        yield transactional_config, commit
    finally:
        if not committed:
            temporary.unlink(missing_ok=True)
