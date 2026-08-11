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
        return _version_tuple(self.version) > _version_tuple(APP_VERSION)


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).strip().split("."))
    except ValueError:
        return (0,)


def check_for_update(manifest_url: str = UPDATE_MANIFEST_URL, timeout: float = 5.0) -> UpdateInfo:
    if not manifest_url:
        raise ValueError("No update manifest URL is configured for this build.")
    if not manifest_url.lower().startswith("https://"):
        raise ValueError("The update manifest must use HTTPS.")
    request = Request(manifest_url, headers={"User-Agent": f"ArtboardCutter/{APP_VERSION}"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
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
