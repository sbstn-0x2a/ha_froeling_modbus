from __future__ import annotations
from datetime import time
import logging
from homeassistant.components.time import TimeEntity
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import tr_key as _tr_key, device_info_for, objekt_id
from .timeconv import register_to_time, time_to_register

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


# ---- Register ----
REGISTER_START_PELLETSBEFUELLUNG_1 = 40062  # R/W Tageszeit, Minuten seit Mitternacht (0..1439)
REGISTER_START_PELLETSBEFUELLUNG_2 = 40095  # R   Tageszeit, Minuten seit Mitternacht (0..1439)
REGISTER_VERZOEGERUNG_NACH_SCHEITHOLZ = 40252  # R/W Dauer in 0,1 h (0..24, skaliert)

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    if not data.get("austragung", False):
        return

    translations = await async_get_translations(hass, hass.config.language, "entity")

    entities = [
        # 40062 – Start 1. Pelletsbefüllung (R/W, echte Tageszeit)
        FroelingAustragungTimeOfDay(
            coordinator=coordinator, translations=translations, data=data,
            entity_id="pelletsbefuellung_1_startzeit", register=REGISTER_START_PELLETSBEFUELLUNG_1,
            device_key="austragung",
        ),
        # 40095 – Start 2. Pelletsbefüllung (R, echte Tageszeit)
        FroelingAustragungTimeOfDayReadOnly(
            coordinator=coordinator, translations=translations, data=data,
            entity_id="pelletsbefuellung_2_startzeit", register=REGISTER_START_PELLETSBEFUELLUNG_2,
            device_key="austragung",
        ),
        # 40252 – Verzögerung als HH:MM anzeigen, intern 0,1 h schreiben/lesen
        FroelingAustragungDelayAsTime(
            coordinator=coordinator, translations=translations, data=data,
            entity_id="verzoegerung_pufferladung_nach_scheitholzbetrieb",
            register=REGISTER_VERZOEGERUNG_NACH_SCHEITHOLZ,
            device_key="austragung",
        ),
    ]

    async_add_entities(entities)

# ---------------- Basisklasse: Tageszeit ----------------
class _BaseTimeOfDay(CoordinatorEntity[FroelingCoordinator], TimeEntity):
    """Tageszeit aus einem Holding-Register (Minuten seit Mitternacht)."""

    _attr_should_poll = False

    def __init__(self, coordinator, translations, data, entity_id: str,
                 register: int, device_key="controller"):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self.entity_id = objekt_id("time", self._device_name, self._entity_id)
        self._register = register
        self._device_key = device_key
        # Gilt nach einem Schreibvorgang, bis der Coordinator neu gelesen hat.
        self._optimistisch: time | None = None

    @property
    def unique_id(self) -> str:
        return f"{self._device_name}_{self._entity_id}"

    @property
    def name(self) -> str:
        key = _tr_key(self._entity_id)
        return self._translations.get(
            f"component.{DOMAIN}.entity.time.{key}.name",
            self._entity_id.replace("_", " "),
        )

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)

    @property
    def native_value(self) -> time | None:
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        return None if roh is None else register_to_time(roh)

    def _handle_coordinator_update(self) -> None:
        self._optimistisch = None
        super()._handle_coordinator_update()


class FroelingAustragungTimeOfDay(_BaseTimeOfDay):
    """R/W Tageszeit (40062)."""

    async def async_set_value(self, value: time) -> None:
        if await self.coordinator.schreibe(self._register, time_to_register(value)) is not None:
            return
        self._optimistisch = value
        self.async_write_ha_state()


class FroelingAustragungTimeOfDayReadOnly(_BaseTimeOfDay):
    """R/O Tageszeit (40095)."""


class FroelingAustragungDelayAsTime(CoordinatorEntity[FroelingCoordinator], TimeEntity):
    """Dauer 40252 (0..24 h in 0,1-h-Schritten), dargestellt als HH:MM.

    Keine Tageszeit: Der Rohwert zaehlt Zehntelstunden, deshalb eigene
    Umrechnung statt register_to_time.
    """

    _attr_should_poll = False

    def __init__(self, coordinator, translations, data, entity_id: str,
                 register: int, device_key="controller"):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self.entity_id = objekt_id("time", self._device_name, self._entity_id)
        self._register = register
        self._device_key = device_key
        self._optimistisch: time | None = None

        key = _tr_key(self._entity_id)
        self._attr_name = self._translations.get(
            f"component.{DOMAIN}.entity.time.{key}.name",
            "Nach Scheitholzbetrieb: Pufferladung mit Pellets verzögern um",
        )

    @property
    def unique_id(self) -> str:
        return f"{self._device_name}_{self._entity_id}"

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)

    @staticmethod
    def _als_zeit(rohwert: int) -> time:
        minuten = (max(0, min(240, rohwert)) * 6) % 1440   # 0,1 h = 6 min
        return time(hour=(minuten // 60) % 24, minute=minuten % 60)

    @property
    def native_value(self) -> time | None:
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        return None if roh is None else self._als_zeit(roh)

    def _handle_coordinator_update(self) -> None:
        self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        minuten = value.hour * 60 + value.minute
        roh = max(0, min(240, int(round(minuten / 6.0))))
        if await self.coordinator.schreibe(self._register, roh) is not None:
            return
        # Auf das 6-Minuten-Raster gerundet zurueckmelden.
        self._optimistisch = self._als_zeit(roh)
        self.async_write_ha_state()
