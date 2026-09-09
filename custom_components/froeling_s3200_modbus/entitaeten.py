"""Welche Zeilen der Registertabelle zu Entitäten werden.

Heute: genau die 177 Entitäten der Fassung 0.4.0 (Zeilen mit
``alter_schluessel``), gefiltert nach den gewählten Anlagenteilen des
Config-Entry. Die Erkennung beim Einrichten und die zusätzlichen Register
der Kundenebene setzen später hier an, ohne dass die Plattformen sich ändern.
"""

from __future__ import annotations

from typing import Any

from .registertabelle import TABELLE, Register


def alle_zeilen() -> tuple[Register, ...]:
    """Jede Zeile, die überhaupt eine Entität werden kann."""
    return tuple(z for z in TABELLE if z.alter_schluessel is not None)


def zeilen_fuer(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Zeilen für die gewählten Anlagenteile eines Config-Entry.

    ``alte_gruppe`` ist der Schlüssel des Hakens im Config-Flow (``hk02``,
    ``boiler01`` …). Zeilen ohne Gruppe -- die Reglerwerte -- gibt es immer.
    """
    return tuple(
        z for z in alle_zeilen()
        if z.alte_gruppe is None or konfiguration.get(z.alte_gruppe, False)
    )


def zeilen_der_plattform(konfiguration: dict[str, Any], plattform: str) -> tuple[Register, ...]:
    return tuple(z for z in zeilen_fuer(konfiguration) if z.plattform == plattform)
