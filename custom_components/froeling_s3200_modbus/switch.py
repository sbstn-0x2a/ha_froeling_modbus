from homeassistant.components.switch import SwitchEntity
import logging
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import tr_key as _tr_key, device_info_for, objekt_id

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


# --- ENDE HELPER ---

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    translations = await async_get_translations(hass, hass.config.language, "entity")

    def create_switches():
        sw: list[SwitchEntity] = []

        # --- Kessel ---
        if data.get("kessel", False):
            # 40136 Automatisch Zünden (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, translations, data, "automatisch_zuenden", 40136, device_key="kessel"))

        # --- Heizkreis 01 ---
        if data.get("hk01", False):
            # 48029 Freigabe Heizkreis 01 (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, translations, data, "hk1_freigabe", 48029, device_key="hk01"))

        # --- Heizkreis 02 ---
        if data.get("hk02", False):
            # 48030 Freigabe Heizkreis 02 (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, translations, data, "hk2_freigabe", 48030, device_key="hk02"))

        # --- Austragung ---
        if data.get("austragung", False):
            # 40265 Automatische Pelletsaustragung deaktivieren (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, translations, data, "pelletsaustragung_deaktivieren", 40265, device_key="austragung"))

        return sw

    switches = create_switches()
    async_add_entities(switches)


# ---------------- Basisklasse ----------------
class _BaseSwitch(CoordinatorEntity[FroelingCoordinator], SwitchEntity):
    """Schalter auf einem Holding-Register. Wert aus dem Coordinator."""

    _attr_should_poll = False

    def __init__(self, coordinator, translations, data, entity_id: str,
                 register: int, device_key="controller"):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self.entity_id = objekt_id("switch", self._device_name, self._entity_id)
        self._register = register
        self._device_key = device_key
        # Gilt nach einem Schaltvorgang, bis der Coordinator neu gelesen hat.
        self._optimistisch: bool | None = None

        key = _tr_key(self._entity_id)
        self._attr_name = self._translations.get(
            f"component.{DOMAIN}.entity.switch.{key}.name",
            self._entity_id.replace("_", " ")
        )

    @property
    def unique_id(self):
        return f"{self._device_name}_{self._entity_id}"

    @property
    def is_on(self):
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        return None if roh is None else bool(roh)

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)

    def _handle_coordinator_update(self) -> None:
        self._optimistisch = None
        super()._handle_coordinator_update()


class FroelingHoldingSwitch(_BaseSwitch):
    """Holding-Register: FC=03 lesen, FC=06 schreiben."""

    async def async_turn_on(self, **kwargs):
        await self._schalten(True)

    async def async_turn_off(self, **kwargs):
        await self._schalten(False)

    async def _schalten(self, ein: bool):
        if await self.coordinator.schreibe(self._register, 1 if ein else 0) is not None:
            return
        self._optimistisch = ein
        self.async_write_ha_state()
