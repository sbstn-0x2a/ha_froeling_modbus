from homeassistant.components.switch import SwitchEntity
import logging

from .const import DOMAIN
from .entity import FroelingEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


# --- ENDE HELPER ---

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    def create_switches():
        sw: list[SwitchEntity] = []

        # --- Kessel ---
        if data.get("kessel", False):
            # 40136 Automatisch Zünden (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, data, "automatisch_zuenden", 40136, device_key="kessel"))

        # --- Heizkreis 01 ---
        if data.get("hk01", False):
            # 48029 Freigabe Heizkreis 01 (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, data, "hk1_freigabe", 48029, device_key="hk01"))

        # --- Heizkreis 02 ---
        if data.get("hk02", False):
            # 48030 Freigabe Heizkreis 02 (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, data, "hk2_freigabe", 48030, device_key="hk02"))

        # --- Austragung ---
        if data.get("austragung", False):
            # 40265 Automatische Pelletsaustragung deaktivieren (R/W, 0/1)
            sw.append(FroelingHoldingSwitch(coordinator, data, "pelletsaustragung_deaktivieren", 40265, device_key="austragung"))

        return sw

    switches = create_switches()
    async_add_entities(switches)


# ---------------- Basisklasse ----------------
class _BaseSwitch(FroelingEntity, SwitchEntity):
    """Schalter auf einem Holding-Register. Wert aus dem Coordinator."""

    _plattform = "switch"

    def __init__(self, coordinator, data, entity_id: str,
                 register: int, device_key="controller"):
        super().__init__(coordinator, data, entity_id, device_key)
        self._register = register
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
