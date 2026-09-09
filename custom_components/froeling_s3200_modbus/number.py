from homeassistant.components.number import NumberEntity, NumberDeviceClass
import logging

from .const import DOMAIN, FERNSTEUERUNG_HINWEIS
from .entity import FroelingEntity

_LOGGER = logging.getLogger(__name__)

# Schreibzugriffe sind nicht gebuendelt, deshalb 1 statt 0.
PARALLEL_UPDATES = 1


# --- ENDE HELPER ---


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    def create_numbers():
        nums: list[NumberEntity] = []

        # --- Kessel ---
        if data.get("kessel", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "kessel_solltemperatur", 40001, "°C", 2, 0, 70, 90, device_key="kessel"),
                FroelingNumberHolding(coordinator, data, "bei_welcher_rl_temperatur_an_der_zirkulationsleitung_soll_die_pumpe_ausschalten", 40601, "°C", 2, 0, 20, 120, device_key="boiler01"),
            ])

        # --- Heizkreis 01 ---
        if data.get("hk01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "hk1_vorlauf_temperatur_10c_aussentemperatur", 41032, "°C", 2, 0, 10, 110, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_vorlauf_temperatur_minus_10c_aussentemperatur", 41033, "°C", 2, 0, 10, 110, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_heizkreispumpe_ausschalten_wenn_vorlauf_soll_kleiner_ist_als", 41040, "°C", 2, 0, 10, 30, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_absenkung_der_vorlauftemperatur_im_absenkbetrieb", 41034, "°C", 2, 0, 0, 70, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_aussentemperatur_unter_der_die_heizkreispumpe_im_heizbetrieb_einschaltet", 41037, "°C", 2, 0, -20, 50, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_aussentemperatur_unter_der_die_heizkreispumpe_im_absenkbetrieb_einschaltet", 41038, "°C", 2, 0, -20, 50, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_frostschutztemperatur", 41039, "°C", 2, 0, -30, 20, device_key="hk01"),
                FroelingNumberHolding(coordinator, data, "hk1_temp_am_puffer_oben_ab_der_der_ueberhitzungsschutz_aktiv_wird", 41048, "°C", 1, 0, 60, 120, device_class="temperature", device_key="hk01"),
                FroelingNumberFernsteuerung(coordinator, data, "hk1_vorlauf_soll_modbus", 48001, "°C", 2, 0, 0, 75, device_key="hk01"),
            ])

        # --- Heizkreis 02 ---
        if data.get("hk02", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "hk2_vorlauf_temperatur_10c_aussentemperatur", 41062, "°C", 2, 0, 10, 110, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_vorlauf_temperatur_minus_10c_aussentemperatur", 41063, "°C", 2, 0, 10, 110, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_heizkreispumpe_ausschalten_wenn_vorlauf_soll_kleiner_ist_als", 41070, "°C", 2, 0, 10, 30, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_absenkung_der_vorlauftemperatur_im_absenkbetrieb", 41064, "°C", 2, 0, 0, 70, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_aussentemperatur_unter_der_die_heizkreispumpe_im_heizbetrieb_einschaltet", 41067, "°C", 2, 0, -20, 50, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_aussentemperatur_unter_der_die_heizkreispumpe_im_absenkbetrieb_einschaltet", 41068, "°C", 2, 0, -20, 50, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_frostschutztemperatur", 41069, "°C", 2, 0, -10, 20, device_key="hk02"),
                FroelingNumberHolding(coordinator, data, "hk2_temp_am_puffer_oben_ab_der_der_ueberhitzungsschutz_aktiv_wird", 41079, "°C", 1, 0, 60, 120, device_class="temperature", device_key="hk02"),
                FroelingNumberFernsteuerung(coordinator, data, "hk2_vorlauf_soll_modbus", 48002, "°C", 2, 0, 0, 75, device_key="hk02"),
            ])

        # --- Boiler 01 ---
        if data.get("boiler01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "boiler_1_gewuenschte_boilertemperatur", 41632, "°C", 2, 0, 10, 100, device_key="boiler01"),
                FroelingNumberHolding(coordinator, data, "boiler_1_nachladen_wenn_boilertemperatur_unter", 41633, "°C", 2, 0, 1, 90, device_key="boiler01"),
                FroelingNumberFernsteuerung(coordinator, data, "boiler_1_solltemperatur_modbus", 48019, "°C", 2, 0, 0, 65, device_key="boiler01"),
            ])

        # --- Puffer 01 ---
        if data.get("puffer01", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "puffer_1_delta_t_kessel_vs_grenzschicht", 42003, "°C", 2, 0, 0, 120, device_key="puffer01"),
                FroelingNumberHolding(coordinator, data, "puffer_1_start_pufferladung_ab_ladezustand", 42022, "%", 1, 0, 0, 100, device_key="puffer01"),
                FroelingNumberHolding(coordinator, data, "puffer_1_100_prozent_kesselleistung_bis_ladezustand", 42027, "%", 1, 0, 0, 100, device_key="puffer01"),
                FroelingNumberHolding(coordinator, data, "puffer_1_0_prozent_kesselleistung_ab_ladezustand", 42028, "%", 1, 0, 0, 100, device_key="puffer01"),
            ])

        # --- Austragung ---
        if data.get("austragung", False):
            nums.extend([
                FroelingNumberHolding(coordinator, data, "gefoerderte_pellets_100_prozent_einschub", 40319, "g", 1, 0, 0, 10000, device_key="austragung"),
                FroelingNumberHolding(coordinator, data, "pelletlager_restbestand", 40320, "t", 10, 1, 0, 100, device_key="austragung"),
                FroelingNumberHolding(coordinator, data, "pelletlager_mindestbestand", 40336, "t", 10, 1, 0, 100, device_key="austragung"),
            ])

        return nums

    numbers = create_numbers()
    async_add_entities(numbers)


class _BaseNumber(FroelingEntity, NumberEntity):
    """Gemeinsames Verhalten. Der Wert stammt aus dem Coordinator."""

    _plattform = "number"

    def __init__(self, coordinator, data, entity_id, register, unit,
                 scaling_factor, decimal_places=0, min_value=0, max_value=0,
                 device_key="controller", device_class: str | NumberDeviceClass | None = None):
        super().__init__(coordinator, data, entity_id, device_key)
        self._register = register
        self._unit = unit
        self._scaling_factor = scaling_factor
        self._decimal_places = decimal_places
        self._min_value = float(min_value)
        self._max_value = float(max_value)
        # Nach einem Schreibvorgang gilt dieser Wert, bis der Coordinator das
        # Register erneut gelesen hat.
        self._optimistisch: float | None = None

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

    def _handle_coordinator_update(self) -> None:
        # Frische Registerwerte loesen die optimistische Anzeige ab.
        self._optimistisch = None
        super()._handle_coordinator_update()


class FroelingNumberInput(_BaseNumber):
    """Input-Register (3xxxx) -- nur lesbar."""

    async def async_set_native_value(self, value):
        _LOGGER.debug("Schreibversuch auf Input-Register %s ignoriert", self._register)


class FroelingNumberHolding(_BaseNumber):
    """Holding-Register (4xxxx) -- les- und schreibbar.

    Vorher trug jede Instanz die Attribute ``modbus_override_active``,
    ``min_switch_interval_min`` und ``override_timeout_min`` -- Reste eines
    Ansatzes für die Kesselfernsteuerung, berechnet nur aus dem eigenen
    letzten Schreibzeitpunkt. An der Kessel-Solltemperatur hatten sie keine
    Bedeutung, und an den Fernsteuerregistern stimmten sie nicht: Die
    Sollwertvorgabe wird von *jedem* Register 48001-48046 aktiviert, nicht nur
    vom eigenen. Sie sind entfernt.
    """

    @property
    def extra_state_attributes(self):
        return {"register": self._register}

    async def async_set_native_value(self, value):
        v = float(min(max(value, self._min_value), self._max_value))
        raw = int(round(v * float(self._scaling_factor)))
        if await self.coordinator.schreibe(self._register, raw) is not None:
            return
        self._optimistisch = round(raw / float(self._scaling_factor), self._decimal_places)
        self.async_write_ha_state()


class FroelingNumberFernsteuerung(FroelingNumberHolding):
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
        return {"register": self._register, "hinweis": FERNSTEUERUNG_HINWEIS}
