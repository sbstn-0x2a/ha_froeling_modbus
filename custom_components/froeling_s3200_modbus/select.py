"""Auswahlentitäten aus der Registertabelle (Holding-Register mit Werteliste)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .device import tr_key as _tr_key
from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# ------------------------ Option-Definitionen (Codes → Keys) ----------------
# Die Übersetzungsschlüssel je Werteliste. Die Anzeigetexte stehen in
# translations/*.json unter entity.select.<entity>.state.<key>; die
# deutschen Texte der Doku dienen als Rückfall.
HK_MODE_CODE_TO_KEY = {0: "off", 1: "auto", 2: "extra", 3: "eco", 4: "eco_permanent", 5: "party"}
FUEL_CODE_TO_KEY = {0: "softwood", 1: "hardwood"}

DEFAULT_LABELS = {
    "hk_mode": {
        "off": "Aus",
        "auto": "Automatik",
        "extra": "Extraheizen",
        "eco": "Absenken",
        "eco_permanent": "Dauerabsenken",
        "party": "Partybetrieb",
    },
    "fuel": {
        "softwood": "weiches Holz",
        "hardwood": "hartes Holz",
    },
}

#: Werteliste der Registertabelle -> (Übersetzungsgruppe, Code -> Key)
OPTIONEN = {
    "betriebsart": ("hk_mode", HK_MODE_CODE_TO_KEY),
    "brennstoffauswahl": ("fuel", FUEL_CODE_TO_KEY),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    # Übersetzungen: nur der erlaubte "entity"-Namespace
    translations = await async_get_translations(hass, hass.config.language, "entity")

    async_add_entities(
        RegisterSelect(coordinator, translations, data, zeile)
        for zeile in zeilen_der_plattform(data, "select")
        if zeile.werteliste in OPTIONEN
    )


class RegisterSelect(FroelingRegisterEntity, SelectEntity):
    """Auswahl auf einem Holding-Register.

    Optionen und aktuelle Auswahl werden aus dem Rohwert abgeleitet. Ein Wert,
    der in der Tabelle fehlt, erscheint als dynamische Option "Wert <n>" --
    sonst liesse sich der Zustand der Anlage nicht anzeigen.
    """

    _plattform = "select"

    def __init__(self, coordinator, translations, data, zeile) -> None:
        super().__init__(coordinator, data, zeile)
        self._translations = translations
        self._group_key, code_to_key = OPTIONEN[zeile.werteliste]
        self._code_to_key = dict(code_to_key)
        self._key_to_code = {v: k for k, v in code_to_key.items()}
        self._option_keys = list(self._key_to_code.keys())
        # Gilt nach einer Auswahl, bis der Coordinator neu gelesen hat.
        self._optimistisch: int | None = None

    def _label_for_key(self, opt_key: str) -> str:
        entity_key = _tr_key(self._entity_id)
        return self._translations.get(
            f"component.{DOMAIN}.entity.select.{entity_key}.state.{opt_key}",
            DEFAULT_LABELS.get(self._group_key, {}).get(opt_key, opt_key),
        )

    @property
    def _rohwert(self) -> int | None:
        if self._optimistisch is not None:
            return self._optimistisch
        return self.coordinator.rohwert(self._register)

    @property
    def options(self) -> list[str]:
        bekannt = [self._label_for_key(k) for k in self._option_keys]
        roh = self._rohwert
        if roh is not None and roh not in self._code_to_key:
            bekannt.append(f"Wert {roh}")
        return bekannt

    @property
    def current_option(self) -> str | None:
        roh = self._rohwert
        if roh is None:
            return None
        schluessel = self._code_to_key.get(roh)
        return self._label_for_key(schluessel) if schluessel else f"Wert {roh}"

    def _handle_coordinator_update(self) -> None:
        self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str):
        code = None
        for k in self._option_keys:
            if self._label_for_key(k) == option:
                code = int(self._key_to_code[k])
                break
        if code is None and option.startswith("Wert "):
            try:
                code = int(option.split(" ", 1)[1])
            except ValueError:
                code = None
        if code is None:
            _LOGGER.error("Unbekannte Option %r für %s", option, self._entity_id)
            return
        if await self.coordinator.schreibe(self._register, code) is not None:
            return
        self._optimistisch = code
        self.async_write_ha_state()
