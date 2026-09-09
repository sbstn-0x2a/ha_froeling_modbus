from __future__ import annotations
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import tr_key as _tr_key, device_info_for, objekt_id

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


# ------------------------ Option-Definitionen (Codes → Keys) ----------------
# HK-Betriebsarten (Register 48047/48048)
HK_MODE_CODE_TO_KEY = {
    0: "off",
    1: "auto",
    2: "extra",
    3: "eco",
    4: "eco_permanent",
    5: "party",
}
HK_MODE_KEY_TO_CODE = {v: k for k, v in HK_MODE_CODE_TO_KEY.items()}

# Brennstoffauswahl (Register 40441)
FUEL_CODE_TO_KEY = {
    0: "softwood",
    1: "hardwood",
}
FUEL_KEY_TO_CODE = {v: k for k, v in FUEL_CODE_TO_KEY.items()}

# Fallback-Labels (falls Übersetzung fehlt)
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

# ------------------------ Register (Holding) ------------------------
REG_HK1_BETRIEBSART = 48047     # Select HK1 - Betriebsart
REG_HK2_BETRIEBSART = 48048     # Select HK2 - Betriebsart
REG_BRENNSTOFFAUSWAHL = 40441   # Select Brennstoffauswahl

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    # Übersetzungen: nur der erlaubte "entity"-Namespace
    translations = await async_get_translations(hass, hass.config.language, "entity")


    def create_selects():
        entities: list[SelectEntity] = []

        # 48047 – HK1 Betriebsart
        if data.get("hk01", False):
            entities.append(
                FroelingSelect(
                    coordinator=coordinator,
                    translations=translations,
                    data=data,
                    entity_id="betriebsart_heizkreis_01",
                    register=REG_HK1_BETRIEBSART,
                    device_key="hk01",
                    group_key="hk_mode",
                    code_to_key=HK_MODE_CODE_TO_KEY,
                    key_to_code=HK_MODE_KEY_TO_CODE,
                    name_fallback="Betriebsart Heizkreis 01",
                )
            )

        # 48048 – HK2 Betriebsart
        if data.get("hk02", False):
            entities.append(
                FroelingSelect(
                    coordinator=coordinator,
                    translations=translations,
                    data=data,
                    entity_id="betriebsart_heizkreis_02",
                    register=REG_HK2_BETRIEBSART,
                    device_key="hk02",
                    group_key="hk_mode",
                    code_to_key=HK_MODE_CODE_TO_KEY,
                    key_to_code=HK_MODE_KEY_TO_CODE,
                    name_fallback="Betriebsart Heizkreis 02",
                )
            )

        # 40441 – Brennstoffauswahl (Kessel)
        if data.get("kessel", False):
            entities.append(
                FroelingSelect(
                    coordinator=coordinator,
                    translations=translations,
                    data=data,
                    entity_id="brennstoffauswahl",
                    register=REG_BRENNSTOFFAUSWAHL,
                    device_key="kessel",
                    group_key="fuel",
                    code_to_key=FUEL_CODE_TO_KEY,
                    key_to_code=FUEL_KEY_TO_CODE,
                    name_fallback="Brennstoffauswahl",
                )
            )

        return entities

    entities = create_selects()
    async_add_entities(entities)


# --------------------------- Entity ---------------------------
class FroelingSelect(CoordinatorEntity[FroelingCoordinator], SelectEntity):
    """Auswahl auf einem Holding-Register.

    Optionen und aktuelle Auswahl werden aus dem Rohwert abgeleitet. Ein Wert,
    der in der Tabelle fehlt, erscheint als dynamische Option "Wert <n>" --
    sonst liesse sich der Zustand der Anlage nicht anzeigen.
    """

    _attr_should_poll = False
    # Der Anzeigename beschreibt nur die Entität; Home Assistant
    # stellt den Gerätenamen voran.
    _attr_has_entity_name = True

    def __init__(self, coordinator, translations, data, entity_id: str,
                 register: int, device_key: str, group_key: str,
                 code_to_key: dict[int, str], key_to_code: dict[str, int],
                 name_fallback: str):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self.entity_id = objekt_id("select", self._device_name, self._entity_id)
        self._attr_translation_key = _tr_key(self._entity_id)
        self._register = register
        self._device_key = device_key
        self._group_key = group_key
        self._code_to_key = dict(code_to_key)
        self._key_to_code = dict(key_to_code)
        self._option_keys = list(self._key_to_code.keys())
        self._name_fallback = name_fallback
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
    def unique_id(self) -> str:
        return f"{self._device_name}_{self._entity_id}"

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

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)

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
