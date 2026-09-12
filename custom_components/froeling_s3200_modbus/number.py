"""Einstellbare Zahlen aus der Registertabelle (Holding-Register, FC06)."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.helpers.restore_state import RestoreEntity

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
        RegisterNumberFernsteuerung(coordinator, data, zeile, laufzeit.fernsteuerung)
        if zeile.kategorie == "fernsteuerung"
        else RegisterNumber(coordinator, data, zeile)
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
        # Der Schritt folgt den Dezimalstellen der Doku, nicht der
        # Registerauflösung: Bei Faktor 2 könnte das Register halbe Grad
        # speichern, das Bediengerät zeigt aber ganze -- also Schritt 1.
        # Beim Pelletlager (Faktor 10, eine Dezimale) bleibt es bei 0,1.
        if self._zeile.dezimalen <= 0:
            return 1
        return round(10 ** -self._zeile.dezimalen, self._zeile.dezimalen)

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
        await self._schreiben(raw & 0xFFFF)
        self._optimistisch = round(raw / float(self._zeile.faktor), self._zeile.dezimalen)
        self.async_write_ha_state()


class RegisterNumberFernsteuerung(RegisterNumber, RestoreEntity):
    """Sollwert der Kesselfernsteuerung (48001-48026) -- ein **Vorgabewert**.

    Schreibt seit 0.6.0 nichts mehr selbst. Vorher schaltete ein einzelner
    Wert hier die Sollwertvorgabe der Anlage global ein und verfiel nach zwei
    Minuten, waehrend die Entitaet ihn weiter anzeigte (B1200522 Kap. 2.6,
    am Geraet 09.09.2026 gemessen); deshalb war sie standardmaessig
    deaktiviert. Jetzt haelt ``Fernsteuerung`` den Wert und sendet ihn im
    Heartbeat, sobald die Regelung bei Home Assistant liegt -- die Entitaet
    ist damit ungefaehrlich und wieder standardmaessig aktiv. Bestehende
    Registry-Eintraege bleiben, wie sie sind.

    Gezeigt wird die Vorgabe, nicht der Registerinhalt: Lesen liefert nur den
    zuletzt angenommenen Wert und sagt nichts ueber den Zustand. Der
    Registerinhalt steht als Attribut ``register_wert`` daneben.
    """

    #: Der Wert ist eine Annahme in HA, kein Istwert der Anlage.
    _attr_assumed_state = True

    def __init__(self, coordinator, data, zeile, fernsteuerung) -> None:
        super().__init__(coordinator, data, zeile)
        self._fernsteuerung = fernsteuerung
        # Nicht erneut deaktivieren, wenn die Erkennung das Register als
        # "wertlos" fuehrt: Der Befund beurteilt Registerinhalte, hier ist es
        # eine Vorgabe.
        self._attr_entity_registry_enabled_default = True

    @property
    def available(self) -> bool:
        # Die Vorgabe lebt in HA; sie darf auch ohne Verbindung zur Anlage
        # gesetzt werden. Ob sie ankommt, zeigt "Fernsteuerung aktiv".
        return True

    @property
    def native_value(self):
        roh = self._fernsteuerung.wert(self._register)
        if roh is None:
            # Boiler ohne lesbare "Gewuenschte Boilertemperatur": kein
            # neutraler Wert -- lieber unbekannt als eine erfundene 0.
            return None
        return round(roh / float(self._zeile.faktor or 1), self._zeile.dezimalen)

    @property
    def extra_state_attributes(self):
        roh = self._rohwert_vorzeichen()
        register_wert = None
        if roh is not None and roh != -1:
            register_wert = round(roh / float(self._zeile.faktor or 1), self._zeile.dezimalen)
        return {
            "register": self._zeile.nummer,
            "beschreibung": self._zeile.name_de,
            "hinweis": FERNSTEUERUNG_HINWEIS,
            "register_wert": register_wert,
            "neutral": self._fernsteuerung.ist_neutral(self._register),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Vorgabe aus der Zeit vor dem Neustart uebernehmen -- aber nur eine,
        # die diese Fassung als bewusste Vorgabe geschrieben hat (Attribut
        # ``neutral`` gleich False). Ein Zustand aus 0.5.0 war der gelesene
        # Registerinhalt, meist 0; als Vorgabe uebernommen hiesse das
        # "Boiler aus" beim ersten Einschalten. Kein Schreibzugriff: Master
        # ist nach dem Start immer Kessel.
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.attributes.get("neutral") is False:
            try:
                wert = float(letzter.state)
            except (TypeError, ValueError):
                wert = None
            if wert is not None:
                # Wie beim Setzen auf den Bereich klemmen: Ein Wert ausserhalb
                # (etwa nach geaenderten Grenzen) darf nicht ungeprueft an
                # die Anlage gehen.
                wert = float(min(max(wert, self.native_min_value), self.native_max_value))
                roh = int(round(wert * float(self._zeile.faktor or 1)))
                self._fernsteuerung.vorgabe_wiederherstellen(self._register, roh & 0xFFFF)
        self.async_on_remove(self._fernsteuerung.zuhoerer_hinzufuegen(self.async_write_ha_state))

    def _handle_coordinator_update(self) -> None:
        # Kein optimistischer Wert: Der Zustand ist die Vorgabe, nur das
        # Attribut register_wert aendert sich mit dem Lesen.
        self.async_write_ha_state()

    async def async_set_native_value(self, value):
        v = float(min(max(value, self.native_min_value), self.native_max_value))
        raw = int(round(v * float(self._zeile.faktor or 1)))
        # Bei Master Kessel nur merken; bei Master HA sendet die Fernsteuerung
        # sofort einen Satz. Ein Schaltwechsel innerhalb der Sperre wartet dort.
        await self._fernsteuerung.async_vorgabe_setzen(self._register, raw & 0xFFFF)
        self.async_write_ha_state()
