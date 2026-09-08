"""Umrechnung der Tageszeit-Register (40062, 40095).

Bewusst frei von Home-Assistant- und pymodbus-Importen, damit die Logik ohne
laufende HA-Instanz testbar ist.

Das Register enthält **Minuten seit Mitternacht** (0..1439) in der lokalen
Uhrzeit des Reglers. Am Gerät verifiziert: Bediengerät auf 07:50 gestellt
-> Register 40062 enthält 470 (= 7*60 + 50).

Die Modbus-Dokumentation B1200522 nennt für diese Register "Max 2400". Das ist
ein Wertebereich, keine HHMM-Kodierung -- in HHMM bräuchte man 2400, um 23:59
darzustellen, in Minuten genügen 1439. Frühere Fassungen dieser Integration
haben aus der 2400 auf HHMM geschlossen und zusätzlich eine Zeitzonen-
umrechnung angewandt. Beide Fehler hoben sich innerhalb von Home Assistant
gegenseitig auf (Schreiben und Lesen waren in sich konsistent), wichen aber
gemeinsam vom Gerät ab -- und die HHMM-Packung machte gut ein Drittel aller
Tagesminuten unerreichbar, weil ``h*100 + m`` niemals auf 60..99 endet.
"""

from __future__ import annotations

from datetime import time

MINUTES_PER_DAY = 1440


def register_to_time(raw: int) -> time:
    """Registerwert (Minuten seit Mitternacht) -> Tageszeit."""
    mins = raw % MINUTES_PER_DAY
    return time(hour=mins // 60, minute=mins % 60)


def time_to_register(value: time) -> int:
    """Tageszeit -> Registerwert (Minuten seit Mitternacht)."""
    return value.hour * 60 + value.minute
