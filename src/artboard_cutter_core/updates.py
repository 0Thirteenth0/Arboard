from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

from .version import APP_VERSION, UPDATE_MANIFEST_URL


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    notes_url: str = ""
    sha256: str = ""

    @property
    def is_newer(self) -> bool:
        candidate = _version_tuple(self.version)
        current = _version_tuple(APP_VERSION)
        length = max(len(candidate), len(current))
        return candidate + (0,) * (length - len(candidate)) > current + (0,) * (length - len(current))


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(part) for part in str(value).strip().split("."))
        return parts if parts and all(part >= 0 for part in parts) else (0,)
    except ValueError:
        return (0,)


def check_for_update(manifest_url: str = UPDATE_MANIFEST_URL, timeout: float = 5.0) -> UpdateInfo:
    if not manifest_url:
        raise ValueError("No update manifest URL is configured for this build.")
    if not manifest_url.lower().startswith("https://"):
        raise ValueError("The update manifest must use HTTPS.")
    request = Request(manifest_url, headers={"User-Agent": f"ArtboardCutter/{APP_VERSION}"})
    with urlopen(request, timeout=timeout) as response:
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("The update manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The update manifest must contain a JSON object.")
    version = str(payload.get("version", "")).strip()
    download_url = str(payload.get("download_url", "")).strip()
    if not version or not download_url.lower().startswith("https://"):
        raise ValueError("The update manifest is missing a valid version or HTTPS download URL.")
    return UpdateInfo(
        version=version,
        download_url=download_url,
        notes_url=str(payload.get("notes_url", "")).strip(),
        sha256=str(payload.get("sha256", "")).strip().lower(),
    )
