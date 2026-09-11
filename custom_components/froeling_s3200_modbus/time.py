"""Zeitentitäten aus der Registertabelle.

Zwei Arten: Tageszeiten (Minuten seit Mitternacht, siehe Befund vom
07.09.2026) und die Dauer 40252 in Zehntelstunden, als HH:MM dargestellt.
"""

from __future__ import annotations

from datetime import time
import logging

from homeassistant.components.time import TimeEntity

from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity
from .timeconv import register_to_time, time_to_register

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

#: Register, die eine Dauer in 0,1 h enthalten statt einer Tageszeit.
DAUER_REGISTER = {40252}


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    entities = []
    for zeile in zeilen_der_plattform(data, "time"):
        if zeile.nummer in DAUER_REGISTER:
            klasse = RegisterDauer
        elif zeile.rw == "R/W":
            klasse = RegisterTageszeit
        else:
            klasse = RegisterTageszeitNurLesen
        entities.append(klasse(coordinator, data, zeile))
    async_add_entities(entities)


class _Basis(FroelingRegisterEntity, TimeEntity):
    _plattform = "time"

    def __init__(self, coordinator, data, zeile) -> None:
        super().__init__(coordinator, data, zeile)
        # Gilt nach einem Schreibvorgang, bis der Coordinator neu gelesen hat.
        self._optimistisch: time | None = None

    def _handle_coordinator_update(self) -> None:
        if self._frisch_gelesen():
            self._optimistisch = None
        super()._handle_coordinator_update()


class RegisterTageszeitNurLesen(_Basis):
    """Tageszeit aus einem Holding-Register (Minuten seit Mitternacht), nur lesbar."""

    @property
    def native_value(self) -> time | None:
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        return None if roh is None else register_to_time(roh)


class RegisterTageszeit(RegisterTageszeitNurLesen):
    """Tageszeit, schreibbar."""

    async def async_set_value(self, value: time) -> None:
        if await self.coordinator.schreibe(self._register, time_to_register(value)) is not None:
            return
        self._optimistisch = value
        self.async_write_ha_state()


class RegisterDauer(_Basis):
    """Dauer 0..24 h in 0,1-h-Schritten, dargestellt als HH:MM.

    Keine Tageszeit: Der Rohwert zaehlt Zehntelstunden, deshalb eigene
    Umrechnung statt register_to_time.
    """

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

    async def async_set_value(self, value: time) -> None:
        minuten = value.hour * 60 + value.minute
        roh = max(0, min(240, int(round(minuten / 6.0))))
        if await self.coordinator.schreibe(self._register, roh) is not None:
            return
        # Auf das 6-Minuten-Raster gerundet zurueckmelden.
        self._optimistisch = self._als_zeit(roh)
        self.async_write_ha_state()
