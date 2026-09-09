"""Binäre Zustände aus der Registertabelle."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    async_add_entities(
        RegisterBinarySensor(coordinator, data, zeile)
        for zeile in zeilen_der_plattform(data, "binary_sensor")
    )


class RegisterBinarySensor(FroelingRegisterEntity, BinarySensorEntity):
    """Coil, Discrete Input oder Register -- ungleich null bedeutet an.

    Der Coordinator legt alle Werte in einer gemeinsamen Tabelle ab: Register
    unter ihrer 3xxxx-/4xxxx-Nummer, Discrete Inputs unter ihrer 1xxxx-Nummer,
    Coils unter ihrer Adresse. Die Nummernkreise überschneiden sich nicht.
    Input-Register werden vorzeichenbehaftet ausgewertet.
    """

    _plattform = "binary_sensor"

    @property
    def is_on(self):
        if self._zeile.typ == "input":
            roh = self._rohwert_vorzeichen()
        else:
            roh = self.coordinator.rohwert(self._register)
        return None if roh is None else bool(roh)
