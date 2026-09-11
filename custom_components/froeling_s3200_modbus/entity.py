"""Gemeinsame Grundlage aller Entitäten.

Vorher stand dieser Code siebenmal da -- einmal je Plattform-Basisklasse, in
``time.py`` sogar zweimal. Bei jeder Änderung an der Kennungsbildung mussten
alle sieben Stellen mitgezogen werden; number.py war dabei schon einmal
abgedriftet.

Die Regel ``common-modules`` der Home-Assistant-Qualitätsskala verlangt genau
das: Coordinator in ``coordinator.py``, Basis-Entität in ``entity.py``.
"""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import device_info_for, objekt_id, tr_key
from .entitaeten import TOTE_DEAKTIVIERT, tote_register, tote_umgang
from .modbus import VERWORFEN
from .registertabelle import Register


class FroelingEntity(CoordinatorEntity[FroelingCoordinator]):
    """Kennung, Name und Gerätezuordnung -- für alle Plattformen gleich.

    Die Plattformmodule leiten davon ab und mischen ihre jeweilige
    HA-Entitätsklasse dazu, etwa ``class _Basis(FroelingEntity, SensorEntity)``.
    """

    #: Kein eigenes Polling: Die Werte kommen aus dem Coordinator.
    _attr_should_poll = False
    #: Der Anzeigename beschreibt nur die Entität; Home Assistant stellt den
    #: Gerätenamen voran.
    _attr_has_entity_name = True

    #: Von der abgeleiteten Klasse zu setzen -- "sensor", "number", ...
    #: Wird für die entity_id gebraucht, und zwar schon im Konstruktor, bevor
    #: Home Assistant die Plattform kennt.
    _plattform: str

    def __init__(self, coordinator, data, entity_id: str, device_key: str) -> None:
        super().__init__(coordinator)
        self._device_name = data["name"]
        self._entity_id = entity_id
        self._device_key = device_key
        self.entity_id = objekt_id(
            self._plattform, self._device_name, device_key, entity_id
        )
        self._attr_translation_key = tr_key(entity_id)

    @property
    def unique_id(self) -> str:
        """Bindet Historie, Statistik und Nutzeranpassungen.

        Enthält bewusst weiterhin den Anlagennamen und den ungekürzten
        internen Schlüssel -- sie darf sich nie ändern.
        """
        return f"{self._device_name}_{self._entity_id}"

    @property
    def device_info(self):
        return device_info_for(
            self._device_key,
            self._device_name,
            DOMAIN,
            self.coordinator.regler_id,
        )


class FroelingRegisterEntity(FroelingEntity):
    """Eine Entität, die aus einer Zeile der Registertabelle entsteht.

    Kennung und Gerät kommen aus der Zeile: Für die Entitäten der 0.4.0
    aus ``alter_schluessel`` und ``altes_geraet``, damit unique_id, entity_id
    und Gerät exakt bleiben; für neue Instanzen aus Instanzkennung und
    Schlüssel (``hk03_frostschutztemperatur`` am Gerät ``hk03``).
    """

    def __init__(self, coordinator, data, zeile: Register) -> None:
        geraet = zeile.altes_geraet or zeile.gruppe or "controller"
        super().__init__(coordinator, data, zeile.entitaetsschluessel, geraet)
        self._zeile = zeile
        self._register = zeile.nummer
        # Register, die die Erkennung beim Einrichten als wertlos eingestuft
        # hat (Fühler nicht belegt, Zähler bei 0, ...), werden angelegt, aber
        # nicht eingeschaltet. Bestehende Registry-Eintraege bleiben, wie sie
        # sind -- die Vorgabe wirkt nur beim Neuanlegen.
        self._grund = tote_register(data).get(zeile.nummer)
        if self._grund and tote_umgang(data) == TOTE_DEAKTIVIERT:
            self._attr_entity_registry_enabled_default = False

    @property
    def extra_state_attributes(self):
        """Register und Doku-Beschreibung, damit man in HA sieht, was dahintersteckt."""
        attribute = {"register": self._zeile.nummer, "beschreibung": self._zeile.name_de}
        if self._grund:
            attribute["hinweis_erkennung"] = self._grund
        return attribute

    async def _schreiben(self, rohwert: int) -> None:
        """Schreibt das eigene Register und macht einen Fehler in HA sichtbar.

        Vorher stand ein abgewiesener Schreibzugriff nur im Protokoll, und die
        Entitaet sprang still auf den alten Wert zurueck. Jetzt scheitert der
        Dienstaufruf mit Text -- etwa wenn die Anlage einen Wert ausserhalb
        ihres Bereichs mit Fehler 04 ablehnt.
        """
        err = await self.coordinator.schreibe(self._register, rohwert)
        if err is None:
            return
        if err == VERWORFEN:
            grund = "von der Regelung verworfen (Mindestschaltdauer 10 min der Fernsteuerung)"
        elif str(err).startswith("error("):
            grund = ("von der Anlage abgewiesen: Wert ausserhalb des zulaessigen "
                     "Bereichs oder MODBUS-Protokoll 2014 nicht aktiv")
        elif str(err).startswith("echo:"):
            grund = f"Anlage hat einen anderen Wert bestaetigt ({err})"
        else:
            grund = f"keine Verbindung ({err})"
        raise HomeAssistantError(f"Register {self._register} ({self._zeile.name_de}): {grund}")

    def _frisch_gelesen(self) -> bool:
        """Wurde das eigene Register im letzten Durchlauf wirklich gelesen?"""
        return self._register in self.coordinator.frisch

    def _rohwert_vorzeichen(self) -> int | None:
        """Rohwert als 16-Bit-Zweierkomplement."""
        roh = self.coordinator.rohwert(self._register)
        if roh is None:
            return None
        return roh - 65536 if roh > 32767 else roh
