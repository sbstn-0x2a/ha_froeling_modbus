from homeassistant.components.number import NumberEntity, NumberDeviceClass
import logging
from datetime import datetime, timezone, timedelta
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FroelingCoordinator
from .device import tr_key as _tr_key, device_info_for, objekt_id

_LOGGER = logging.getLogger(__name__)

# Schreibzugriffe sind nicht gebuendelt, deshalb 1 statt 0.
PARALLEL_UPDATES = 1


# --- ENDE HELPER ---


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration
    translations = await async_get_translations(hass, hass.config.language, "entity")

    def create_numbers():
        nums: list[NumberEntity] = []

        # --- Kessel ---
        if data.get("kessel", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "kessel_solltemperatur", 40001, "°C", 2, 0, 70, 90, device_key="kessel"),
                FroelingNumberHolding(coordinator, translations, data, "bei_welcher_rl_temperatur_an_der_zirkulationsleitung_soll_die_pumpe_ausschalten", 40601, "°C", 2, 0, 20, 120, device_key="boiler01"),
            ])

        # --- Heizkreis 01 ---
        if data.get("hk01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "hk1_vorlauf_temperatur_10c_aussentemperatur", 41032, "°C", 2, 0, 10, 110, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_vorlauf_temperatur_minus_10c_aussentemperatur", 41033, "°C", 2, 0, 10, 110, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_heizkreispumpe_ausschalten_wenn_vorlauf_soll_kleiner_ist_als", 41040, "°C", 2, 0, 10, 30, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_absenkung_der_vorlauftemperatur_im_absenkbetrieb", 41034, "°C", 2, 0, 0, 70, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_aussentemperatur_unter_der_die_heizkreispumpe_im_heizbetrieb_einschaltet", 41037, "°C", 2, 0, -20, 50, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_aussentemperatur_unter_der_die_heizkreispumpe_im_absenkbetrieb_einschaltet", 41038, "°C", 2, 0, -20, 50, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_frostschutztemperatur", 41039, "°C", 2, 0, -30, 20, device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_temp_am_puffer_oben_ab_der_der_ueberhitzungsschutz_aktiv_wird", 41048, "°C", 1, 0, 60, 120, device_class="temperature", device_key="hk01"),
                FroelingNumberHolding(coordinator, translations, data, "hk1_vorlauf_soll_modbus", 48001, "°C", 2, 0, 0, 75, device_key="hk01"),
            ])

        # --- Heizkreis 02 ---
        if data.get("hk02", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "hk2_vorlauf_temperatur_10c_aussentemperatur", 41062, "°C", 2, 0, 10, 110, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_vorlauf_temperatur_minus_10c_aussentemperatur", 41063, "°C", 2, 0, 10, 110, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_heizkreispumpe_ausschalten_wenn_vorlauf_soll_kleiner_ist_als", 41070, "°C", 2, 0, 10, 30, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_absenkung_der_vorlauftemperatur_im_absenkbetrieb", 41064, "°C", 2, 0, 0, 70, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_aussentemperatur_unter_der_die_heizkreispumpe_im_heizbetrieb_einschaltet", 41067, "°C", 2, 0, -20, 50, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_aussentemperatur_unter_der_die_heizkreispumpe_im_absenkbetrieb_einschaltet", 41068, "°C", 2, 0, -20, 50, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_frostschutztemperatur", 41069, "°C", 2, 0, -10, 20, device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_temp_am_puffer_oben_ab_der_der_ueberhitzungsschutz_aktiv_wird", 41079, "°C", 1, 0, 60, 120, device_class="temperature", device_key="hk02"),
                FroelingNumberHolding(coordinator, translations, data, "hk2_vorlauf_soll_modbus", 48002, "°C", 2, 0, 0, 75, device_key="hk02"),
            ])

        # --- Boiler 01 ---
        if data.get("boiler01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "boiler_1_gewuenschte_boilertemperatur", 41632, "°C", 2, 0, 10, 100, device_key="boiler01"),
                FroelingNumberHolding(coordinator, translations, data, "boiler_1_nachladen_wenn_boilertemperatur_unter", 41633, "°C", 2, 0, 1, 90, device_key="boiler01"),
                FroelingNumberHolding(coordinator, translations, data, "boiler_1_solltemperatur_modbus", 48019, "°C", 2, 0, 0, 65, device_key="boiler01"),
            ])

        # --- Puffer 01 ---
        if data.get("puffer01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "puffer_1_delta_t_kessel_vs_grenzschicht", 42003, "°C", 2, 0, 0, 120, device_key="puffer01"),
                FroelingNumberHolding(coordinator, translations, data, "puffer_1_start_pufferladung_ab_ladezustand", 42022, "%", 1, 0, 0, 100, device_key="puffer01"),
                FroelingNumberHolding(coordinator, translations, data, "puffer_1_100_prozent_kesselleistung_bis_ladezustand", 42027, "%", 1, 0, 0, 100, device_key="puffer01"),
                FroelingNumberHolding(coordinator, translations, data, "puffer_1_0_prozent_kesselleistung_ab_ladezustand", 42028, "%", 1, 0, 0, 100, device_key="puffer01"),
            ])

        # --- Austragung ---
        if data.get("austragung", False):
            nums.extend([
                FroelingNumberHolding(coordinator, translations, data, "gefoerderte_pellets_100_prozent_einschub", 40319, "g", 1, 0, 0, 10000, device_key="austragung"),
                FroelingNumberHolding(coordinator, translations, data, "pelletlager_restbestand", 40320, "t", 10, 1, 0, 100, device_key="austragung"),
                FroelingNumberHolding(coordinator, translations, data, "pelletlager_mindestbestand", 40336, "t", 10, 1, 0, 100, device_key="austragung"),
            ])

        return nums

    numbers = create_numbers()
    async_add_entities(numbers)


class _BaseNumber(CoordinatorEntity[FroelingCoordinator], NumberEntity):
    """Gemeinsames Verhalten. Der Wert stammt aus dem Coordinator."""

    _attr_should_poll = False

    def __init__(self, coordinator, translations, data, entity_id, register, unit,
                 scaling_factor, decimal_places=0, min_value=0, max_value=0,
                 device_key="controller", device_class: str | NumberDeviceClass | None = None):
        super().__init__(coordinator)
        self._translations = translations
        self._device_name = data["name"]
        self._entity_id = entity_id
        self.entity_id = objekt_id("number", self._device_name, self._entity_id)
        self._register = register
        self._unit = unit
        self._scaling_factor = scaling_factor
        self._decimal_places = decimal_places
        self._min_value = float(min_value)
        self._max_value = float(max_value)
        self._device_key = device_key
        # Nach einem Schreibvorgang gilt dieser Wert, bis der Coordinator das
        # Register erneut gelesen hat.
        self._optimistisch: float | None = None

        key = _tr_key(self._entity_id)
        self._attr_name = self._translations.get(
            f"component.{DOMAIN}.entity.number.{key}.name",
            self._entity_id.replace("_", " ")
        )

        dc = device_class
        if isinstance(device_class, str):
            _MAP = {
                "temperature": getattr(NumberDeviceClass, "TEMPERATURE", None),
                "voltage": getattr(NumberDeviceClass, "VOLTAGE", None),
                "current": getattr(NumberDeviceClass, "CURRENT", None),
                "power": getattr(NumberDeviceClass, "POWER", None),
                "energy": getattr(NumberDeviceClass, "ENERGY", None),
                "frequency": getattr(NumberDeviceClass, "FREQUENCY", None),
                "pressure": getattr(NumberDeviceClass, "PRESSURE", None),
                "humidity": getattr(NumberDeviceClass, "HUMIDITY", None),
            }
            dc = _MAP.get(device_class.lower())
        self._attr_device_class = dc

    @property
    def unique_id(self): return f"{self._device_name}_{self._entity_id}"

    @property
    def native_value(self):
        if self._optimistisch is not None:
            return self._optimistisch
        roh = self.coordinator.rohwert(self._register)
        if roh is None:
            return None
        if roh > 32767:
            roh -= 65536
        wert = roh / float(self._scaling_factor if self._scaling_factor else 1)
        return round(wert, self._decimal_places)

    @property
    def native_unit_of_measurement(self): return self._unit
    @property
    def native_min_value(self): return self._min_value
    @property
    def native_max_value(self): return self._max_value

    @property
    def native_step(self):
        try:
            step = 1.0 / float(self._scaling_factor)
            return int(step) if step.is_integer() else round(step, max(0, self._decimal_places))
        except Exception:
            return None

    @property
    def device_info(self):
        return device_info_for(self._device_key, self._device_name, DOMAIN)

    def _handle_coordinator_update(self) -> None:
        # Frische Registerwerte loesen die optimistische Anzeige ab.
        self._optimistisch = None
        super()._handle_coordinator_update()


class FroelingNumberInput(_BaseNumber):
    """Input-Register (3xxxx) -- nur lesbar."""

    async def async_set_native_value(self, value):
        _LOGGER.debug("Schreibversuch auf Input-Register %s ignoriert", self._register)


class FroelingNumberHolding(_BaseNumber):
    """Holding-Register (4xxxx) -- les- und schreibbar."""

    _override_timeout = timedelta(minutes=2)
    _min_switch_interval = timedelta(minutes=10)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_write_utc: datetime | None = None

    @property
    def extra_state_attributes(self):
        now = datetime.now(timezone.utc)
        override_active = (
            self._last_write_utc is not None
            and now - self._last_write_utc <= self._override_timeout
        )
        return {
            "register": self._register,
            "last_write_utc": self._last_write_utc.isoformat() if self._last_write_utc else None,
            "modbus_override_active": override_active,
            "min_switch_interval_min": int(self._min_switch_interval.total_seconds() // 60),
            "override_timeout_min": int(self._override_timeout.total_seconds() // 60),
        }

    async def async_set_native_value(self, value):
        v = float(min(max(value, self._min_value), self._max_value))
        raw = int(round(v * float(self._scaling_factor)))

        now = datetime.now(timezone.utc)
        if self._last_write_utc and (now - self._last_write_utc) < self._min_switch_interval:
            _LOGGER.warning(
                "Schreibzugriff auf %s (Register %s) innerhalb der Mindestschaltdauer",
                self._entity_id, self._register,
            )

        if await self.coordinator.schreibe(self._register, raw) is not None:
            return

        self._last_write_utc = now
        self._optimistisch = round(raw / float(self._scaling_factor), self._decimal_places)
        self.async_write_ha_state()
