"""Einstellbare Zahlen aus der Registertabelle (Holding-Register, FC06)."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode

from .const import FERNSTEUERUNG_HINWEIS
from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity

_LOGGER = logging.getLogger(__name__)

# Schreibzugriffe sind nicht gebuendelt, deshalb 1 statt 0.
PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    async_add_entities(
        (RegisterNumberFernsteuerung if zeile.kategorie == "fernsteuerung" else RegisterNumber)(
            coordinator, data, zeile
        )
        for zeile in zeilen_der_plattform(data, "number")
    )


class RegisterNumber(FroelingRegisterEntity, NumberEntity):
    """Holding-Register (4xxxx) -- les- und schreibbar.

    Vorher trug jede Instanz die Attribute ``modbus_override_active``,
    ``min_switch_interval_min`` und ``override_timeout_min`` -- Reste eines
    Ansatzes für die Kesselfernsteuerung, berechnet nur aus dem eigenen
    letzten Schreibzeitpunkt. Sie sind entfernt.
    """

    _plattform = "number"
    #: Eingabefeld statt Schieberegler: Bei Temperaturen und Prozentwerten
    #: sieht man am Regler den aktuellen Wert nicht.
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, data, zeile) -> None:
        super().__init__(coordinator, data, zeile)
        # Nach einem Schreibvorgang gilt dieser Wert, bis der Coordinator das
        # Register erneut gelesen hat.
        self._optimistisch: float | None = None
        gkl = zeile.geraeteklasse
        self._attr_device_class = getattr(NumberDeviceClass, gkl.upper(), None) if gkl else None

    @property
    def native_value(self):
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self._rohwert_vorzeichen()
        if roh is None or roh == -1:
            # 0xFFFF: Register auf dieser Anlage nicht vorhanden -> kein Wert,
            # statt -0,5 °C unterhalb des erlaubten Bereichs.
            return None
        return round(roh / float(self._zeile.faktor or 1), self._zeile.dezimalen)

    @property
    def native_unit_of_measurement(self):
        return self._zeile.einheit

    @property
    def native_min_value(self):
        return float(self._zeile.minimum if self._zeile.minimum is not None else 0)

    @property
    def native_max_value(self):
        return float(self._zeile.maximum if self._zeile.maximum is not None else 0)

    @property
    def native_step(self):
        # Vorher wurde auf ``dezimalen`` gerundet -- bei Faktor 2 und null
        # Dezimalen ergab das den Schritt 0.0. Der Schritt ist die Auflösung
        # des Registers, unabhängig von der Anzeige.
        step = 1.0 / float(self._zeile.faktor or 1)
        return int(step) if step.is_integer() else round(step, 3)

    def _handle_coordinator_update(self) -> None:
        # Nur ein frisch gelesenes Register loest die optimistische Anzeige
        # ab -- ein ausgesetzter Block darf den geschriebenen Wert nicht
        # mit dem alten ueberschreiben.
        if self._frisch_gelesen():
            self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value):
        v = float(min(max(value, self.native_min_value), self.native_max_value))
        raw = int(round(v * float(self._zeile.faktor)))
        # Negative Werte (Frostschutz -5 °C) als 16-Bit-Zweierkomplement senden;
        # pymodbus packt nur 0..65535.
        if await self.coordinator.schreibe(self._register, raw & 0xFFFF) is not None:
            return
        self._optimistisch = round(raw / float(self._zeile.faktor), self._zeile.dezimalen)
        self.async_write_ha_state()


class RegisterNumberFernsteuerung(RegisterNumber):
    """Sollwert der Kesselfernsteuerung (48001-48026).

    Standardmäßig deaktiviert: Ein einzelner Schreibzugriff aktiviert die
    Sollwertvorgabe der Anlage global und nur für zwei Minuten (B1200522
    Kap. 2.6, am Gerät 09.09.2026 gemessen). Als Einzelentität ohne zyklisches
    Nachschreiben ist das irreführend. Wer es bewusst nutzt, kann die Entität
    in der Registry einschalten.
    """

    _attr_entity_registry_enabled_default = False

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, "hinweis": FERNSTEUERUNG_HINWEIS}
