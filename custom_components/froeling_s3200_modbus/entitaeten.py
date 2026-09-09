"""Welche Zeilen der Registertabelle gelesen werden und Entitäten werden.

Freigegeben sind die 177 Entitäten der 0.4.0 (``alter_schluessel``) und die
Register der Kundenebene aus der Parameteranalyse vom 09.09.2026
(``scripts/kundenebene.json``). Gefiltert wird nach den gewählten
Anlagenteilen des Config-Entry: ``gruppe`` ist der Schlüssel des Hakens
(``hk02``, ``boiler01``, ``efilter`` …); Zeilen ohne Gruppe -- die Reglerwerte
und der Fehlerpuffer -- gibt es immer.
"""

from __future__ import annotations

from typing import Any

from .registertabelle import TABELLE, Register


def alle_zeilen() -> tuple[Register, ...]:
    """Jede Zeile, die überhaupt eine Entität werden kann."""
    return tuple(z for z in TABELLE if z.freigegeben and z.plattform)


def zeilen_zum_lesen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Alles, was der Coordinator für diesen Entry liest -- auch Zeilen ohne
    eigene Entität (Fehlerpuffer für den Meldungssensor)."""
    return tuple(
        z for z in TABELLE
        if z.freigegeben and (z.gruppe is None or konfiguration.get(z.gruppe, False))
    )


def zeilen_fuer(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Zeilen, die für die gewählten Anlagenteile Entitäten werden."""
    return tuple(z for z in zeilen_zum_lesen(konfiguration) if z.plattform)


def zeilen_der_plattform(konfiguration: dict[str, Any], plattform: str) -> tuple[Register, ...]:
    return tuple(z for z in zeilen_fuer(konfiguration) if z.plattform == plattform)


def tote_register(konfiguration: dict[str, Any]) -> dict[int, str]:
    """Register, die die Erkennung als wertlos eingestuft hat: Nummer -> Grund."""
    erkannt = konfiguration.get("erkannt") or {}
    return {int(k): v for k, v in (erkannt.get("tot") or {}).items()}
