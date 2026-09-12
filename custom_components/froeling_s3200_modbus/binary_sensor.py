"""Binäre Zustände aus der Registertabelle."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entitaeten import zeilen_der_plattform
from .entity import FroelingEntity, FroelingRegisterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    entities = [
        RegisterBinarySensor(coordinator, data, zeile)
        for zeile in zeilen_der_plattform(data, "binary_sensor")
    ]
    if laufzeit.fernsteuerung is not None and laufzeit.fernsteuerung.zeilen:
        entities.append(FernsteuerungAktivSensor(coordinator, data, laufzeit.fernsteuerung))
    async_add_entities(entities)


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


class FernsteuerungAktivSensor(FroelingEntity, BinarySensorEntity):
    """Wirkt die Kesselfernsteuerung -- nach dem, was Home Assistant weiss?

    An, wenn die Regelung bei Home Assistant liegt **und** der letzte
    erfolgreiche Schreibzugriff juenger als zwei Minuten ist. Danach hat die
    Anlage wieder selbst uebernommen (B1200522 Kap. 2.6; gemessen 54-129 s).
    Das ist eine Ableitung aus HA-Sicht, kein Istwert: Ob die Anlage die
    Vorgabe wirklich anwendet, zeigen ihre Vorlauf-Sollwerte (31032/31062)
    und die Heizkreispumpen (Coils 1030/1060).
    """

    _plattform = "binary_sensor"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, data, fernsteuerung) -> None:
        super().__init__(coordinator, data, "fernsteuerung_aktiv", "fernsteuerung")
        self._fernsteuerung = fernsteuerung

    @property
    def available(self) -> bool:
        # Abgeleitet aus HA-Zustand, nicht aus dem Lesen: Faellt die
        # Verbindung aus, bleibt der Sensor bedienbar und geht nach zwei
        # Minuten ohne Erfolg auf "aus" -- das ist die ehrliche Anzeige.
        return True

    @property
    def is_on(self) -> bool:
        return self._fernsteuerung.aktiv()

    @property
    def extra_state_attributes(self):
        f = self._fernsteuerung
        return {
            "regelung": f.master,
            "letzter_erfolg": f.letzter_erfolg.isoformat() if f.letzter_erfolg else None,
            "fenster_ueberschritten": f.fenster_ueberschritten,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._fernsteuerung.zuhoerer_hinzufuegen(self.async_write_ha_state))

    def _handle_coordinator_update(self) -> None:
        # Jeder Lesedurchlauf schreibt den Zustand neu: So kippt der Sensor
        # auch dann auf "aus", wenn der Heartbeat selbst nicht mehr laeuft.
        self.async_write_ha_state()
