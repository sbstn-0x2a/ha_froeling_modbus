"""Schalter aus der Registertabelle (Holding-Register 0/1, FC06)."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity

from .const import FERNSTEUERUNG_HINWEIS
from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    async_add_entities(
        (RegisterFernsteuerSwitch if zeile.kategorie == "fernsteuerung" else RegisterSwitch)(
            coordinator, data, zeile
        )
        for zeile in zeilen_der_plattform(data, "switch")
    )


class RegisterSwitch(FroelingRegisterEntity, SwitchEntity):
    """Holding-Register: FC=03 lesen, FC=06 schreiben."""

    _plattform = "switch"

    def __init__(self, coordinator, data, zeile) -> None:
        super().__init__(coordinator, data, zeile)
        # Gilt nach einem Schaltvorgang, bis der Coordinator neu gelesen hat.
        self._optimistisch: bool | None = None

    @property
    def is_on(self):
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        return None if roh is None else bool(roh)

    def _handle_coordinator_update(self) -> None:
        self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        await self._schalten(True)

    async def async_turn_off(self, **kwargs):
        await self._schalten(False)

    async def _schalten(self, ein: bool):
        if await self.coordinator.schreibe(self._register, 1 if ein else 0) is not None:
            return
        self._optimistisch = ein
        self.async_write_ha_state()


class RegisterFernsteuerSwitch(RegisterSwitch):
    """Freigabe eines Heizkreises über die Kesselfernsteuerung (48029-48046).

    Standardmäßig deaktiviert. Ein Klick schaltet die Sollwertvorgabe der
    Anlage für alle Heizkreise und Boiler ein, mit dem aktuellen Inhalt der
    übrigen Fernsteuerregister; nach zwei Minuten ohne weiteren Schreibzugriff
    fällt die Anlage zurück, während der Schalter weiter "an" zeigt. Am Gerät
    am 09.09.2026 gemessen, Einzelheiten im Befund zur Parameteranalyse.
    """

    _attr_entity_registry_enabled_default = False

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, "hinweis": FERNSTEUERUNG_HINWEIS}
