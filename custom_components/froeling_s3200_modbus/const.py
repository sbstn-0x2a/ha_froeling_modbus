"""Konstanten der Integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

DOMAIN = "froeling_s3200_modbus"

# Abfrageintervall in Sekunden.
#
# Die HA-Regel appropriate-polling verbietet einstellbare Intervalle. Hier wird
# bewusst abgewichen: Sie zielt auf Cloud-Dienste, waehrend hier ein lokales
# Geraet befragt wird, das seit der Umstellung auf Blocklesungen in rund 400 ms
# antwortet. Am Geraet gemessen aendern sich Werte im Abstand von zwei
# Sekunden; ein Anlauf der Austragschnecke dauerte elf Sekunden und faellt bei
# 60 s Abfrageintervall leicht ganz zwischen zwei Abfragen.
#
# Die Untergrenze verhindert, dass ein Vertipper das Gateway ueberrennt.
MIN_INTERVALL = 15
STANDARD_INTERVALL = 30
MAX_INTERVALL = 3600

#: Attribut der Entitaeten auf den Fernsteuerregistern 48001-48046. Sie sind
#: standardmaessig deaktiviert; wer sie einschaltet, soll wissen, was sie tun.
#: Verhalten laut B1200522 Kap. 2.6, am Geraet am 09.09.2026 bestaetigt.
FERNSTEUERUNG_HINWEIS = (
    "Kesselfernsteuerung: Jeder Schreibzugriff auf ein Register 48001-48046 "
    "schaltet die Sollwertvorgabe für alle Heizkreise und Boiler ein. Ohne "
    "weiteren Schreibzugriff fällt die Anlage nach zwei Minuten in ihre "
    "eigene Regelung zurück; der hier gezeigte Wert bleibt trotzdem stehen. "
    "Ein Wechsel innerhalb von zehn Minuten wird verworfen."
)

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


def eindeutige_kennung(host: str, port, unit_id) -> str:
    """Kennung eines Config-Entries.

    Der Registersatz der Anlage enthaelt keine Serien- oder Anlagennummer,
    deshalb identifiziert die Verbindung das Geraet: Wer zweimal denselben
    Modbus-Endpunkt einrichtet, meint dieselbe Heizung.
    """
    return f"{host}:{int(port)}:{int(unit_id)}"
