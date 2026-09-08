from homeassistant.components.binary_sensor import BinarySensorEntity
import logging
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import tr_key as _tr_key, device_info_for

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


# -----------------------------------------------

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    translations = await async_get_translations(hass, hass.config.language, "entity")

    def create_binary_sensors():
        bs: list[BinarySensorEntity] = []

        # ----- DISCRETE INPUTS (FC=02, 1xxxx) -----
        bs.append(FroelingBinaryDI(coordinator, translations, data, "tuerkontaktschalter", 10001, device_key="controller"))
        bs.append(FroelingBinaryDI(coordinator, translations, data, "stb_eingang", 10002, device_key="controller"))
        bs.append(FroelingBinaryDI(coordinator, translations, data, "not_aus_eingang", 10003, device_key="controller"))
        bs.append(FroelingBinaryDI(coordinator, translations, data, "kesselfreigabe_eingang", 10004, device_key="controller"))
        
        if data.get("hk01", False):
            # ----- COILS (FC=01) -----
            bs.append(FroelingBinaryCoil(coordinator, translations, data, "hk1_pumpe_an_aus", 1030, device_key="hk01"))
            # ----- HOLDING REGISTER (FC=03, 4xxxx) -----
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "hk1_boilervorrang_heizen_erlaubt", 41044, device_key="hk01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "hk1_hochtemperatur_anforderung_boilerladung", 41046, device_key="hk01"))

        if data.get("hk02", False):
            # ----- COILS (FC=01) -----
            bs.append(FroelingBinaryCoil(coordinator, translations, data, "hk2_pumpe_an_aus", 1060, device_key="hk02"))
            # ----- HOLDING REGISTER (FC=03, 4xxxx) -----
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "hk2_boilervorrang_heizen_erlaubt", 41074, device_key="hk02"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "hk2_hochtemperatur_anforderung_boilerladung", 41076, device_key="hk02"))

        if data.get("kessel", False):
            # ----- INPUT REGISTER (FC=04, 3xxxx) -----
            bs.append(FroelingBinaryInput(coordinator, translations, data, "kesselanforderung_steht_an", 30057, device_key="kessel"))
            # ----- HOLDING REGISTER (FC=03, 4xxxx) -----
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "lambda_auto_kalibrierung_aktiv", 43020, device_key="kessel"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "nachlegeberechnung_aktiv", 42031, device_key="puffer01"))

        if data.get("boiler01", False):
            # ----- HOLDING REGISTER (FC=03, 4xxxx) -----
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "boiler1_restwaermenutzung", 41635, device_key="boiler01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "boiler1_nur_einmal_pro_tag_aufladen", 41636, device_key="boiler01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "boiler1_legionellen_aufheizung_aktiv", 41637, device_key="boiler01"))

        if data.get("puffer01", False):
            # ----- HOLDING REGISTER (FC=03, 4xxxx) -----
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "puffer1_restwaermenutzung", 42002, device_key="puffer01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "puffer1_puffermitte_regelung_aktiv", 42014, device_key="puffer01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "puffer1_sp_dual_nach_puffermitte_beenden", 42015, device_key="puffer01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "pufferanforderung_nach_systemumfeld", 42025, device_key="puffer01"))
            bs.append(FroelingBinaryHolding(coordinator, translations, data, "puffer1_hygienespeicher_verwendet", 42030, device_key="puffer01"))

        return bs

    sensors = create_binary_sensors()
    async_add_entities(sensors)


# ---------------- Basisklasse ----------------
class _BaseBin(CoordinatorEntity[FroelingCoordinator], BinarySensorEntity):
    """Binaerer Zustand aus einem Register oder Bit.

    Der Coordinator legt alle Werte in einer gemeinsamen Tabelle ab: Register
    unter ihrer 3xxxx-/4xxxx-Nummer, Discrete Inputs unter ihrer 1xxxx-Nummer,
    Coils unter ihrer Adresse. Die Nummernkreise ueberschneiden sich nicht,
    deshalb genuegt hier eine gemeinsame Nachschlagefunktion.
    """

    _attr_should_poll = False

    def __init__(self, coordinator, translations, data, entity_id,
                 adresse: int, device_key="controller"):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self._adresse = adresse
        self._device_key = device_key

        key = _tr_key(self._entity_id)
        self._attr_name = self._translations.get(
            f"component.{DOMAIN}.entity.binary_sensor.{key}.name",
            self._entity_id.replace("_", " ")
        )

    @property
    def unique_id(self):
        return f"{self._device_name}_{self._entity_id}"

    @property
    def is_on(self):
        roh = self.coordinator.rohwert(self._adresse)
        return None if roh is None else bool(roh)

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)


class FroelingBinaryCoil(_BaseBin):
    """Coil (FC=01), direkt adressiert."""


class FroelingBinaryDI(_BaseBin):
    """Discrete Input (FC=02), echte 1xxxx-Nummer."""


class FroelingBinaryHolding(_BaseBin):
    """Holding-Register (FC=03), ungleich null bedeutet an."""


class FroelingBinaryInput(_BaseBin):
    """Input-Register (FC=04), vorzeichenbehaftet ausgewertet."""

    @property
    def is_on(self):
        roh = self.coordinator.rohwert(self._adresse)
        if roh is None:
            return None
        if roh > 32767:          # 16 Bit, Zweierkomplement
            roh -= 65536
        return roh != 0
