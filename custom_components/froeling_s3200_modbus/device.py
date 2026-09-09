"""Gerätezuordnung und Namensbildung.

Vorher in allen sechs Plattformmodulen dupliziert; number.py war dabei bereits
abgedriftet (DEVICE_NAME fehlte ein Eintrag).
"""

from __future__ import annotations

from homeassistant.util import slugify

from .const import VERSION

#: Anzeigenamen der Untergeräte. Der Regler selbst traegt den Namen, den der
#: Nutzer bei der Einrichtung vergeben hat.
DEVICE_NAME = {
    "kessel": "Kessel",
    "boiler01": "Boiler 01",
    "hk01": "Heizkreis 01",
    "hk02": "Heizkreis 02",
    "puffer01": "Puffer 01",
    "austragung": "Austragung",
    "zirkulationspumpe": "Zirkulationspumpe",
}

#: Baureihe. Steht im Modellfeld aller Geraete, auch der Untergeraete -- sie
#: sind Teile derselben Anlage, kein eigenes Modell.
MODELL = "SP Dual Compact"


def device_info_for(device_key: str, device_name_from_config: str, domain: str):
    """Geraeteangaben fuer eine Entitaet.

    Der Regler ist das Hauptgeraet und traegt den bei der Einrichtung
    vergebenen Namen. Vorher stand dort fest "SP Dual Compact" -- wer seine
    Anlage anders nannte, fand den Namen nirgends wieder.
    """
    if device_key == "controller":
        return {
            "identifiers": {(domain, f"{device_name_from_config}:controller")},
            "name": device_name_from_config,
            "manufacturer": "Fröling",
            "model": MODELL,
            "sw_version": VERSION,
        }
    return {
        "identifiers": {(domain, f"{device_name_from_config}:{device_key}")},
        "name": DEVICE_NAME.get(device_key, device_key),
        "manufacturer": "Fröling",
        "model": MODELL,
        "via_device": (domain, f"{device_name_from_config}:controller"),
        "sw_version": VERSION,
    }


def tr_key(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in s)


def objekt_id(plattform: str, device_name_from_config: str, entity_key: str) -> str:
    """Vorschlag fuer die entity_id einer Entitaet.

    Gebildet aus dem bei der Einrichtung vergebenen Anlagennamen und dem
    internen Schluessel -- nicht aus dem uebersetzten Anzeigenamen. Sonst
    haengt die entity_id an der Sprache von Home Assistant, und dieselbe
    Anlage traegt in zwei Installationen verschiedene Kennungen.

    Home Assistant nimmt den Vorschlag nur an, wenn die Entitaet neu
    angelegt wird; ein bestehender Registry-Eintrag behaelt seine
    entity_id. Bestandsinstallationen aendern sich also nicht.
    """
    return f"{plattform}.{slugify(device_name_from_config)}_{slugify(entity_key)}"
