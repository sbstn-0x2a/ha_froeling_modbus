"""Gerätezuordnung und Namensbildung.

Vorher in allen sechs Plattformmodulen dupliziert; number.py war dabei bereits
abgedriftet (DEVICE_NAME fehlte ein Eintrag).
"""

from __future__ import annotations

import re

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


#: Deutsche Umlaute vor dem Slug ausschreiben. Home Assistants slugify wirft
#: die Punkte weg -- aus "Fröling" wuerde "froling", nicht "froeling".
_UMLAUTE = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)


def _slug(text: str) -> str:
    return slugify(text.translate(_UMLAUTE))


#: Viele interne Schluessel nennen ihre Gruppe schon selbst, in wechselnder
#: Schreibweise (hk01_, hk1_, hk_01_). Da die Gruppe jetzt ein eigenes Segment
#: bekommt, faellt sie im Schluessel weg -- das vereinheitlicht die
#: Schreibweisen gleich mit.
_GRUPPENPRAEFIX = {
    "kessel": (r"^kessel_",),
    "hk01": (r"^hk_?0?1_", r"_heizkreis_0?1$"),
    "hk02": (r"^hk_?0?2_", r"_heizkreis_0?2$"),
    "boiler01": (r"^boiler_?0?1_",),
    "puffer01": (r"^puffer_?0?1_",),
    "austragung": (r"^austragung_",),
    "zirkulationspumpe": (r"^zirkulationspumpe_",),
}


def objekt_id(
    plattform: str, device_name_from_config: str, device_key: str, entity_key: str
) -> str:
    """Vorschlag fuer die entity_id: Anlage, Geraet, Groesse.

        sensor.froeling_kessel_kesseltemperatur
        sensor.froeling_aussentemperatur          (Regler)

    Gebildet aus dem bei der Einrichtung vergebenen Anlagennamen, dem
    Geraeteschluessel und dem internen Schluessel -- nicht aus dem
    uebersetzten Anzeigenamen. Sonst haengt die entity_id an der Sprache von
    Home Assistant, und dieselbe Anlage traegt in zwei Installationen
    verschiedene Kennungen.

    Der Regler bekommt kein eigenes Segment: Er *ist* die Anlage und traegt
    ihren Namen, "froeling_controller_..." waere eine Dopplung.

    Home Assistant nimmt den Vorschlag nur an, wenn die Entitaet neu angelegt
    wird; ein bestehender Registry-Eintrag behaelt seine entity_id.
    Bestandsinstallationen aendern sich also nicht.
    """
    rest = entity_key
    for muster in _GRUPPENPRAEFIX.get(device_key, ()):
        rest = re.sub(muster, "", rest)
    rest = rest or entity_key

    teile = [_slug(device_name_from_config)]
    if device_key != "controller":
        teile.append(_slug(device_key))
    teile.append(_slug(rest))
    return f"{plattform}." + "_".join(t for t in teile if t)
