"""Schalter aus der Registertabelle (Holding-Register 0/1, FC06)."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

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
        RegisterFernsteuerSwitch(coordinator, data, zeile, laufzeit.fernsteuerung)
        if zeile.kategorie == "fernsteuerung"
        else RegisterSwitch(coordinator, data, zeile)
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
        if self._frisch_gelesen():
            self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        await self._schalten(True)

    async def async_turn_off(self, **kwargs):
        await self._schalten(False)

    async def _schalten(self, ein: bool):
        await self._schreiben(1 if ein else 0)
        self._optimistisch = ein
        self.async_write_ha_state()


class RegisterFernsteuerSwitch(RegisterSwitch, RestoreEntity):
    """Freigabe eines Heizkreises ueber die Kesselfernsteuerung (48029-48046)
    -- ein **Vorgabewert**, neutral "an".

    Schreibt seit 0.6.0 nichts mehr selbst; siehe RegisterNumberFernsteuerung
    und fernsteuerung.py. Gerade dieser Schalter war vorher gefaehrlich: Ein
    "Aus" innerhalb der Zehn-Minuten-Sperre wurde verworfen und schaltete den
    Heizkreis zwei weitere Minuten *ein* (gemessen 09.09.2026 16:16). Die
    Fernsteuerung sendet einen solchen Wechsel erst nach Ablauf der Sperre.
    """

    _attr_assumed_state = True

    def __init__(self, coordinator, data, zeile, fernsteuerung) -> None:
        super().__init__(coordinator, data, zeile)
        self._fernsteuerung = fernsteuerung
        self._attr_entity_registry_enabled_default = True

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self):
        return bool(self._fernsteuerung.wert(self._register))

    @property
    def extra_state_attributes(self):
        roh = self.coordinator.rohwert(self._register)
        return {
            "register": self._zeile.nummer,
            "beschreibung": self._zeile.name_de,
            "hinweis": FERNSTEUERUNG_HINWEIS,
            "register_wert": None if roh is None or roh == 0xFFFF else bool(roh),
            "neutral": self._fernsteuerung.ist_neutral(self._register),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Nur eine bewusste Vorgabe dieser Fassung wiederherstellen (neutral
        # False); der Zustand aus 0.5.0 war der Registerinhalt, meist "off".
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.attributes.get("neutral") is False and letzter.state in ("on", "off"):
            self._fernsteuerung.vorgabe_wiederherstellen(self._register, 1 if letzter.state == "on" else 0)
        self.async_on_remove(self._fernsteuerung.zuhoerer_hinzufuegen(self.async_write_ha_state))

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def _schalten(self, ein: bool):
        await self._fernsteuerung.async_vorgabe_setzen(self._register, 1 if ein else 0)
        self.async_write_ha_state()
