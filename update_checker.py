from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_REPO = "NexarSistemas/nexar-finanzas"
CHECK_INTERVAL_SECONDS = 6 * 60 * 60
REQUEST_TIMEOUT = 2.5


def _parse_version(version: str) -> tuple[int, int, int]:
    raw = (version or "0.0.0").strip().lstrip("vV")
    parts = []
    for chunk in raw.split(".")[:3]:
        number = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(number or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _release_api_url() -> str:
    repo = os.getenv("NEXAR_UPDATE_REPOSITORY", DEFAULT_REPO).strip() or DEFAULT_REPO
    return f"https://api.github.com/repos/{repo}/releases/latest"


def get_update_platform() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Linux":
        return "linux"
    if system == "Darwin":
        return "macos"
    return "unsupported"


def _asset_matches_platform(name: str) -> bool:
    normalized = name.lower()
    current_platform = get_update_platform()
    if current_platform == "windows":
        return normalized.startswith("nexarfinanzas_v") and normalized.endswith("_setup.exe")
    if current_platform == "linux":
        return normalized.startswith("nexarfinanzas_v") and normalized.endswith("_linux_amd64.deb")
    return False


def _installer_kind(asset_name: str) -> str:
    if asset_name.lower().endswith(".exe"):
        return "windows"
    if asset_name.lower().endswith(".deb"):
        return "linux"
    return ""


def check_latest_release(current_version: str) -> dict[str, Any]:
    if os.getenv("NEXAR_DISABLE_UPDATE_CHECK", "").lower() in {"1", "true", "yes"}:
        return {"available": False}

    response = requests.get(
        _release_api_url(),
        headers={"Accept": "application/vnd.github+json", "User-Agent": "NexarFinanzas"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    release = response.json()
    latest = (release.get("tag_name") or "").strip().lstrip("vV")
    if not latest:
        return {"available": False}

    available = _parse_version(latest) > _parse_version(current_version)
    assets = release.get("assets") or []
    installer_asset = next(
        (
            asset for asset in assets
            if _asset_matches_platform(str(asset.get("name") or ""))
        ),
        None,
    )
    asset_name = installer_asset.get("name") if installer_asset else ""
    current_platform = get_update_platform()
    manual_install = current_platform == "macos"
    return {
        "available": available,
        "current": current_version,
        "latest": latest,
        "url": release.get("html_url") or f"https://github.com/{DEFAULT_REPO}/releases/latest",
        "name": release.get("name") or f"Nexar Finanzas v{latest}",
        "asset_name": asset_name,
        "asset_url": installer_asset.get("browser_download_url") if installer_asset else "",
        "asset_kind": _installer_kind(asset_name),
        "platform": current_platform,
        "install_mode": (
            "manual"
            if manual_install
            else ("unsupported" if current_platform == "unsupported" else "automatic")
        ),
        "install_message": (
            "La actualización automática no está disponible en macOS. "
            "Descargá e instalá manualmente el archivo .dmg o .zip desde la release."
            if manual_install
            else (
                "La actualización automática no está disponible para esta plataforma."
                if current_platform == "unsupported"
                else ""
            )
        ),
    }


def get_cached_update_info(app, current_version: str) -> dict[str, Any]:
    now = time.time()
    cached = app.config.get("UPDATE_INFO_CACHE")
    if cached and now - cached.get("checked_at", 0) < CHECK_INTERVAL_SECONDS:
        return cached.get("data", {"available": False})

    try:
        data = check_latest_release(current_version)
    except Exception:
        data = {"available": False}

    app.config["UPDATE_INFO_CACHE"] = {"checked_at": now, "data": data}
    return data


def download_release_asset(asset_url: str, destination_dir: Path) -> Path:
    if not asset_url or not asset_url.startswith("https://"):
        raise ValueError("No hay un instalador descargable para esta version.")

    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(asset_url.split("?", 1)[0]).name
    if not _asset_matches_platform(filename) or "/" in filename:
        raise ValueError("El instalador de actualizacion no es valido.")

    target = destination_dir / filename
    partial = destination_dir / f"{filename}.part"
    with requests.get(asset_url, stream=True, timeout=30) as response:
        response.raise_for_status()
        with partial.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    partial.replace(target)
    return target
