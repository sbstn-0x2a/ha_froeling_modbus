"""Entitäts-IDs an das Schema der 0.4.0 angleichen (Options-Aktion).

Home Assistants eigenes „Entitäts-IDs neu erstellen“ baut die Kennung aus
Gerätename und Entitätsname. Für unsere Untergeräte („Kessel“) entstünden
IDs ohne Anlagennamen, die bei zwei Anlagen kollidieren. Deshalb eine eigene
Aktion mit derselben Regel wie beim Neuanlegen (``objekt_id``): Anlage,
Gerät, Größe. Die Registry zieht Historie und Statistik automatisch mit;
Automationen, Skripte und Dashboards nicht -- das steht im Dialog.

Nutzerentscheid vom 11.09.2026 (Plan „Für 0.6.0 vorgemerkt“).
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .device import objekt_id
from .entitaeten import fernsteuerung_aktiv, zeilen_fuer


def _erwartet(data: dict) -> list[tuple[str, str, str]]:
    """(Plattform, unique_id, vorgeschlagene entity_id) für jede Entität des Entry."""
    name = data["name"]
    liste = []
    for z in zeilen_fuer(data):
        if z.kategorie == "fernsteuerung":
            geraet = "fernsteuerung"
        else:
            geraet = z.altes_geraet or z.gruppe or "controller"
        liste.append((z.plattform, f"{name}_{z.entitaetsschluessel}",
                      objekt_id(z.plattform, name, geraet, z.entitaetsschluessel)))
    liste.append(("sensor", f"{name}_meldungen", objekt_id("sensor", name, "controller", "meldungen")))
    if fernsteuerung_aktiv(data):
        for plattform, schluessel in (("select", "fernsteuerung_regelung"),
                                      ("binary_sensor", "fernsteuerung_aktiv")):
            liste.append((plattform, f"{name}_{schluessel}",
                          objekt_id(plattform, name, "fernsteuerung", schluessel)))
    return liste


def vorschlaege(hass: HomeAssistant, data: dict) -> list[tuple[str, str]]:
    """Paare (alte entity_id, neue entity_id) für alle Entitäten, die vom Schema abweichen."""
    reg = er.async_get(hass)
    paare = []
    for plattform, unique_id, neu in _erwartet(data):
        alt = reg.async_get_entity_id(plattform, DOMAIN, unique_id)
        if alt and alt != neu:
            paare.append((alt, neu))
    return paare


def umbenennen(hass: HomeAssistant, paare: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """Benennt um; belegte Ziel-IDs werden übersprungen und zurückgemeldet."""
    reg = er.async_get(hass)
    ok, uebersprungen = 0, []
    for alt, neu in paare:
        if reg.async_get(neu) is not None or reg.async_get(alt) is None:
            uebersprungen.append(f"{alt} → {neu}")
            continue
        reg.async_update_entity(alt, new_entity_id=neu)
        ok += 1
    return ok, uebersprungen
