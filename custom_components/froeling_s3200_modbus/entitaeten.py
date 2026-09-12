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

from .fernsteuerung import boilerregister_zum_lesen, satz_zeilen
from .registertabelle import TABELLE, Register


def alle_zeilen() -> tuple[Register, ...]:
    """Jede Zeile, die überhaupt eine Entität werden kann."""
    return tuple(z for z in TABELLE if z.freigegeben and z.plattform)


#: Umgang mit Registern, die die Erkennung als wertlos eingestuft hat.
TOTE_DEAKTIVIERT = "deaktiviert"   # anlegen, aber in der Registry ausgeschaltet
TOTE_WEGLASSEN = "weglassen"       # gar nicht anlegen und nicht lesen
TOTE_NORMAL = "normal"             # wie jedes andere Register
TOTE_UMGANG = (TOTE_DEAKTIVIERT, TOTE_WEGLASSEN, TOTE_NORMAL)


def tote_umgang(konfiguration: dict[str, Any]) -> str:
    wert = konfiguration.get("tote")
    if wert in TOTE_UMGANG:
        return wert
    # Fassung vor 0.5: ein Haken "tote_deaktivieren".
    return TOTE_DEAKTIVIERT if konfiguration.get("tote_deaktivieren", True) else TOTE_NORMAL


def fernsteuerung_aktiv(konfiguration: dict[str, Any]) -> bool:
    """Haken „Kesselfernsteuerung“ im Config-Entry. Vorgabe aus -- auch für
    Bestandseinträge ohne den Schlüssel: Wer die Fernsteuerung will, schaltet
    sie bewusst ein, und erst dann entstehen ihre Entitäten und der Heartbeat."""
    return bool(konfiguration.get("fernsteuerung", False))


def _zeilen_der_gruppen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Freigegebene Zeilen der gewählten Anlagenteile -- die Grundmenge.

    Ohne die Fernsteuerregister: Die hängen nicht am Anlagenteil, sondern
    am Haken „Kesselfernsteuerung“ (``fernsteuer_zeilen``)."""
    weg = tote_register(konfiguration) if tote_umgang(konfiguration) == TOTE_WEGLASSEN else {}
    return tuple(
        z for z in TABELLE
        if z.freigegeben and z.kategorie != "fernsteuerung"
        and (z.gruppe is None or konfiguration.get(z.gruppe, False))
        and z.nummer not in weg
    )


def fernsteuer_zeilen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Fernsteuerzeilen (48001-48046), die Entitäten werden: bei aktiver
    Fernsteuerung genau der Satz -- alle vorhandenen Instanzen (Haken oder
    Erkennung), unabhängig von ``freigegeben`` in der Tabelle. Heizkreis 03
    oder Boiler 02 bekommen so ihre Vorgabe-Entitäten, sobald es sie gibt."""
    if not fernsteuerung_aktiv(konfiguration):
        return ()
    return satz_zeilen(konfiguration)


def zeilen_zum_lesen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Alles, was der Coordinator für diesen Entry liest -- auch Zeilen ohne
    eigene Entität: der Fehlerpuffer für den Meldungssensor und, bei aktiver
    Fernsteuerung, die „Gewünschte Boilertemperatur“ jedes Boilers im Satz.
    Letztere braucht die Kesselfernsteuerung als neutralen Boiler-Sollwert;
    ohne sie bliebe der Boiler aus dem Satz -- oder bekäme, schlimmer, eine
    0 (Ladung aus). Ist die Fernsteuerung aus, wird 48001-48046 nicht
    gelesen; die Betriebsart 48047 ff. gehört zum Heizkreis und bleibt."""
    grund = _zeilen_der_gruppen(konfiguration) + fernsteuer_zeilen(konfiguration)
    if not fernsteuerung_aktiv(konfiguration):
        return grund
    nummern = {(z.typ, z.nummer) for z in grund}
    zusatz = tuple(
        z for z in boilerregister_zum_lesen(konfiguration) if (z.typ, z.nummer) not in nummern
    )
    return grund + zusatz


def zeilen_fuer(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Zeilen, die Entitäten werden: die der gewählten Anlagenteile und die
    Fernsteuerzeilen. Bewusst nicht aus ``zeilen_zum_lesen``: Die nur zum
    Lesen ergänzten Boilerregister dürfen keine Entität werden."""
    return tuple(z for z in _zeilen_der_gruppen(konfiguration) if z.plattform) + fernsteuer_zeilen(konfiguration)


def zeilen_der_plattform(konfiguration: dict[str, Any], plattform: str) -> tuple[Register, ...]:
    return tuple(z for z in zeilen_fuer(konfiguration) if z.plattform == plattform)


def tote_register(konfiguration: dict[str, Any]) -> dict[int, str]:
    """Register, die die Erkennung als wertlos eingestuft hat: Nummer -> Grund."""
    erkannt = konfiguration.get("erkannt") or {}
    return {int(k): v for k, v in (erkannt.get("tot") or {}).items()}
