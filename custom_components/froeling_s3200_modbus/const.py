"""Konstanten der Integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

DOMAIN = "froeling_s3200_modbus"

_LOGGER = logging.getLogger(__name__)
_MANIFEST = Path(__file__).parent / "manifest.json"


def _version_aus_manifest() -> str:
    """Liest die Version aus manifest.json.

    Die manifest.json ist damit die einzige Stelle, an der die Versionsnummer
    gepflegt wird. Vorher stand sie zusaetzlich in sechs Plattformmodulen und
    lief bei jedem Release Gefahr, dort zu veralten.
    """
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        _LOGGER.warning("Version konnte nicht aus %s gelesen werden", _MANIFEST)
        return "unknown"


VERSION = _version_aus_manifest()
