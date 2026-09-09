"""Sensoren aus der Registertabelle.

Vorher stand hier je Entität ein Konstruktoraufruf, 116 Stück, plus die
Wertelisten für die Textsensoren. Jetzt liefert ``entitaeten.zeilen_fuer``
die Zeilen der Registertabelle, und zwei Klassen decken alles ab: Zahl mit
Skalierung, Text über eine Werteliste.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .entitaeten import zeilen_der_plattform
from .entity import FroelingRegisterEntity
from .registertabelle import WERTELISTEN

_LOGGER = logging.getLogger(__name__)

# Der Coordinator buendelt die Abfragen; die Plattform ist rein lesend.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    async_add_entities(
        (RegisterTextSensor if zeile.werteliste else RegisterZahlSensor)(coordinator, data, zeile)
        for zeile in zeilen_der_plattform(data, "sensor")
    )


class _Basis(FroelingRegisterEntity, SensorEntity):
    """Die Werte kommen aus dem Coordinator; die Entitäten lesen nichts selbst."""

    _plattform = "sensor"


class RegisterZahlSensor(_Basis):
    """Zahlenwert mit Skalierung und Vorzeichenbehandlung."""

    @property
    def unit_of_measurement(self):
        return self._zeile.einheit

    @property
    def device_class(self):
        return self._zeile.geraeteklasse

    @property
    def state_class(self):
        # Eine Einheit ist fuer die Langzeitstatistik nicht noetig: Die
        # HA-Dokumentation nennt als Bedingung allein die state_class, und der
        # Recorder prueft in _is_numeric nur, ob der Wert eine endliche Zahl
        # ist. Auf der Anlage bestaetigt -- 56 von 60 einheitenlosen Sensoren
        # anderer Integrationen fuehren dort Statistik.
        if self._zeile.zustandsklasse == "total_increasing":
            return SensorStateClass.TOTAL_INCREASING
        return SensorStateClass.MEASUREMENT

    @property
    def state(self):
        roh = self._rohwert_vorzeichen()
        if roh is None:
            return None
        wert = roh / (self._zeile.faktor or 1)
        if self._zeile.dezimalen == 0:
            return int(round(wert))
        return round(wert, self._zeile.dezimalen)


class RegisterTextSensor(_Basis):
    """Zustandstext über eine Werteliste der Doku."""

    @property
    def state(self):
        roh = self.coordinator.rohwert(self._register)
        if roh is None:
            return None
        return WERTELISTEN[self._zeile.werteliste].get(roh, f"Unknown ({roh})")
