"""Gemeinsame Grundlage aller Entitäten.

Vorher stand dieser Code siebenmal da -- einmal je Plattform-Basisklasse, in
``time.py`` sogar zweimal. Bei jeder Änderung an der Kennungsbildung mussten
alle sieben Stellen mitgezogen werden; number.py war dabei schon einmal
abgedriftet.

Die Regel ``common-modules`` der Home-Assistant-Qualitätsskala verlangt genau
das: Coordinator in ``coordinator.py``, Basis-Entität in ``entity.py``.
"""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import device_info_for, objekt_id, tr_key


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
