from homeassistant.components.sensor import SensorEntity, SensorStateClass
import logging
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity import FroelingEntity

_LOGGER = logging.getLogger(__name__)

# Der Coordinator buendelt die Abfragen; die Plattform ist rein lesend.
PARALLEL_UPDATES = 0


# -------------------------------------------------------------------

async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    ent_reg = er.async_get(hass)
    dev_name = data["name"]
    to_remove = []
    if not data.get("kessel", False):
        to_remove.append(f"{dev_name}_kesselzustand")
    if not data.get("boiler01", False):
        to_remove.append(f"{dev_name}_legionellentag")
    if not data.get("hk01", False):
        to_remove.append(f"{dev_name}_hk_01_pufferversorgung")
    if not data.get("hk02", False):
        to_remove.append(f"{dev_name}_hk_02_pufferversorgung")
    for e in list(ent_reg.entities.values()):
        if e.platform == DOMAIN and e.unique_id in to_remove:
            ent_reg.async_remove(e.entity_id)

    # ---------- TEXT-SENSOREN ----------
    def create_text_sensors():
        items = []
        items.append(FroelingTextSensor(coordinator, data, "anlagenzustand", 34001, ANLAGENZUSTAND_MAPPING, device_key="controller"))
        if data.get("kessel", False):
            items.append(
                FroelingTextSensor(coordinator, data, "kesselzustand", 34002, KESSELZUSTAND_MAPPING, device_key="kessel")
                )
        if data.get("boiler01", False):
            items.append(
                FroelingTextHoldingSensor(coordinator, data, "legionellentag", 41638, LEGIONELLENTAG_MAPPING, device_key="boiler01")
                )
        if data.get("hk01", False):
            items.append(
                FroelingTextHoldingSensor(coordinator, data, "hk_01_pufferversorgung", 41045, HK01PUFFERVERSORGUNG_MAPPING, device_key="hk01")
                )
        if data.get("hk02", False):
            items.append(
                FroelingTextHoldingSensor(coordinator, data, "hk_02_pufferversorgung", 41075, HK02PUFFERVERSORGUNG_MAPPING, device_key="hk02")
                )
        return items
    # ---------- CONTROLLER-SENSOREN ----------
    def create_controller_sensors():
        return [
            FroelingSensor(coordinator, data, "boardtemperatur", 30003, "°C", 2, 0, device_class="temperature", device_key="controller"),
            FroelingSensor(coordinator, data, "boardtemperatur_pelletsmodul", 30018, "°C", 2, 0, device_class="temperature", device_key="controller"),
            FroelingSensor(coordinator, data, "betriebsstunden", 30021, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "anzahl_der_brennerstarts", 30023, "", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_in_der_feuererhaltung", 30025, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_stokerschnecke", 30040, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_foerderschnecke", 30041, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_ruettler", 30043, "min", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_wos", 30045, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_ascheschnecke", 30046, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_zuendung", 30047, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_lambdasonde", 30048, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_saugturbinen", 30049, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "betriebsstunden_austragsschnecke", 30050, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "lambdasondenspannung_gemessen", 30055, "mV", 100, 2, device_class="voltage", device_key="controller"),
            FroelingSensor(coordinator, data, "stunden_seit_letzter_wartung", 30056, "h", 1, 0, device_key="controller"),
            FroelingSensor(coordinator, data, "stunden_im_pelletsbetrieb", 30063, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "stunden_im_heizen", 30064, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "stunden_in_teillastbetrieb", 30075, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "stunden_im_scheitholzbetrieb", 30077, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "tagesertrag", 30085, "kWh", 1, 0, device_key="controller"),
            FroelingSensor(coordinator, data, "gesamtertrag", 30086, "kWh", 1, 0, device_key="controller"),
            FroelingSensor(coordinator, data, "betriebsstunden_saugturbine", 30098, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "anzahl_der_reinigungen", 30102, "", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "zeit_bis_zur_naechsten_reinigung", 30103, "min", 1, 0, device_key="controller"),
            FroelingSensor(coordinator, data, "betriebsstunden_e_filter", 30104, "h", 1, 0, device_key="controller",
                           state_class=SensorStateClass.TOTAL_INCREASING),
            FroelingSensor(coordinator, data, "aussentemperatur", 31001, "°C", 2, 0, device_class="temperature", device_key="controller"),
        ]

    # ---------- KOMPLETTER SENSOR-AUFBAU ----------
    def create_sensors():
        sensors: list[SensorEntity] = []
        # Controller zuerst
        sensors.extend(create_controller_sensors())

        # KESSEL
        if data.get("kessel", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "kessel_kesseltemperatur", 30001, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_abgastemperatur", 30002, "°C", 1, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_restsauerstoffgehalt", 30004, "%", 10, 1, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_position_primaerluftklappe", 30005, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_saugzugdrehzahl", 30007, "Upm", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_fuehler_1", 30008, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_abgastemperatur_nach_brennwertwaermetauscher", 30009, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_ruecklauffuehler", 30010, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_luftgeschwindigkeit_ansaug", 30011, "m/s", 100, 2, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_primaerluft", 30012, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_saugzug_ansteuerung", 30013, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_sekundaerluft", 30014, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_kesselstellgroesse", 30015, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_abgas_solltemperatur", 30016, "°C", 1, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_sauerstoffregler", 30017, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_ansauglufttemperatur", 30019, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_errechnete_kesselsolltemperatur", 30028, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_ruecklaufpumpen_ansteuerung", 30037, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_drehzahl_kesselladepumpe", 30068, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_verbleibende_heizstunden_bis_asche_entleeren", 30087, "h", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_feuerraumtemperatur", 30089, "°C", 1, 0, device_class="temperature", device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_saugzug_ansteuerung_alt", 30105, "%", 1, 0, device_key="kessel"),
                FroelingSensor(coordinator, data, "kessel_waermemenge_vom_kessel", 30171, "MWh", 10, 1, device_key="kessel"),

                # Holding 4xxxx -> eigene Klasse
                FroelingHoldingSensor(coordinator, data, "kessel_abschalten_wenn_kesseltemperatur_ueber_soll", 40002, "°C", 2, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_maximale_anheizzeit", 40003, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_kesseltemperatur_ab_pumpen_freigabe", 40008, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_immer_abschalten_ueber_kesselsoll_plus", 40009, "°C", 2, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_sollwert_restsauerstoff", 40027, "%", 10, 1, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_restsauerstoff_fuer_feuer_aus", 40028, "%", 10, 1, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_restsauerstoff_ohne_verbrennung", 40029, "%", 10, 1, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_dauer_vorwaermen", 40043, "s", 1, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_maximale_zuenddauer", 40045, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_abstellen_warten_1", 40046, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_mind_dauer_geblaesenachlauf1", 40047, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_mind_dauer_abstellen", 40048, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_abstellen_warten_2", 40049, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_mind_dauer_geblaesenachlauf2", 40050, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_sicherheitszeit", 40051, "min", 60, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_wos_laufzeit", 40061, "s", 1, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_mindesttemperatur_ruecklauf", 40067, "°C", 2, 0, device_class="temperature", device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_laufzeit_mischer", 40070, "s", 1, 0, device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_abgastemperatur_feuer_aus", 40073, "°C", 1, 0, device_class="temperature", device_key="kessel"),
                FroelingHoldingSensor(coordinator, data, "kessel_nach_wie_viel_mal_abstellen_abreinigen", 40085, "", 1, 0, device_key="kessel"),
            ])

        # HEIZKREIS 01
        if data.get("hk01", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "hk01_vorlauf_isttemperatur", 31031, "°C", 2, 0, device_class="temperature", device_key="hk01"),
                FroelingSensor(coordinator, data, "hk01_vorlauf_solltemperatur", 31032, "°C", 2, 0, device_class="temperature", device_key="hk01"),
                FroelingHoldingSensor(coordinator, data, "hk01_maximale_vorlauftemperatur", 41035, "°C", 2, 0, device_class="temperature", device_key="hk01"),
                FroelingHoldingSensor(coordinator, data, "hk01_laufzeit_mischer", 41043, "s", 1, 0, device_key="hk01"),
                FroelingHoldingSensor(coordinator, data, "hk01_maximale_boiler_vorlauftemperatur", 41047, "°C", 2, 0, device_class="temperature", device_key="hk01"),
            ])

        # HEIZKREIS 02
        if data.get("hk02", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "hk02_vorlauf_isttemperatur", 31061, "°C", 2, 0, device_class="temperature", device_key="hk02"),
                FroelingSensor(coordinator, data, "hk02_vorlauf_solltemperatur", 31062, "°C", 2, 0, device_class="temperature", device_key="hk02"),
                FroelingHoldingSensor(coordinator, data, "hk02_maximale_vorlauftemperatur", 41065, "°C", 2, 0, device_class="temperature", device_key="hk02"),
                FroelingHoldingSensor(coordinator, data, "hk02_laufzeit_mischer", 41073, "s", 1, 0, device_key="hk02"),
                FroelingHoldingSensor(coordinator, data, "hk02_maximale_boiler_vorlauftemperatur", 41078, "°C", 2, 0, device_class="temperature", device_key="hk02"),
            ])

        # PUFFER 01
        if data.get("puffer01", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "puffer_1_temperatur_oben", 32001, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingSensor(coordinator, data, "puffer_1_temperatur_mitte", 32002, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingSensor(coordinator, data, "puffer_1_temperatur_unten", 32003, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingSensor(coordinator, data, "puffer_1_pufferpumpen_ansteuerung", 32004, "%", 1, 0, device_key="puffer01"),
                FroelingSensor(coordinator, data, "puffer_1_ladezustand", 32007, "%", 1, 0, device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_heizkreisfreigabe_ab_puffertemperatur", 42001, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_minimale_drehzahl_pufferpumpe", 42004, "%", 1, 0, device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_kesselstart_diff_kesselsoll_oben", 42005, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_durchgeladen_diff_kesselsoll_unten", 42006, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_maximale_drehzahl_pufferpumpe", 42012, "%", 1, 0, device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_puffer_puffer_diff", 42018, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_ladezustand_100_prozent_beikesselsoll", 42020, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_ladezustand_0_prozent_ab_temp", 42021, "°C", 2, 0, device_class="temperature", device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_systemumfeld_ausschaltverzoegerung", 42026, "min", 60, 0, device_key="puffer01"),
                FroelingHoldingSensor(coordinator, data, "puffer_1_volumen", 42029, "l", 1, 0, device_key="puffer01"),
            ])

        # BOILER 01
        if data.get("boiler01", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "boiler_1_temperatur_oben", 31631, "°C", 2, 0, device_class="temperature", device_key="boiler01"),
                FroelingSensor(coordinator, data, "boiler_1_pumpe_ansteuerung", 31633, "%", 1, 0, device_key="boiler01"),
                FroelingHoldingSensor(coordinator, data, "boiler_1_laden_bei_puffer_und_boiler_tempdiff_von", 41634, "°C", 2, 0, device_class="temperature", device_key="boiler01"),
                FroelingHoldingSensor(coordinator, data, "boiler_1_laden_bei_kessel_und_boiler_tempdiff_von", 41639, "°C", 2, 0, device_class="temperature", device_key="boiler01"),
                FroelingHoldingSensor(coordinator, data, "boiler_1_soll_diff_kessel_boiler", 41640, "°C", 2, 0, device_class="temperature", device_key="boiler01"),
                FroelingHoldingSensor(coordinator, data, "boiler_1_min_drehzahl_boilerpumpe", 41641, "%", 1, 0, device_key="boiler01"),
                FroelingHoldingSensor(coordinator, data, "boiler_1_max_drehzahl_boilerpumpe", 41646, "%", 1, 0, device_key="boiler01"),
            ])

        # AUSTRAGUNG
        if data.get("austragung", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "stromaufnahme_der_austragsschnecke", 30020, "A", 1000, 2, device_key="austragung"),
                FroelingSensor(coordinator, data, "fuellstand_im_pelletsbehaelter", 30022, "%", 207, 1, device_key="austragung"),
                FroelingSensor(coordinator, data, "resetierbarer_kg_zaehler", 30082, "kg", 1, 0, device_key="austragung"),
                FroelingSensor(coordinator, data, "resetierbarer_t_zaehler", 30083, "t", 1, 0, device_key="austragung"),
                FroelingSensor(coordinator, data, "pelletverbrauch_gesamt", 30084, "t", 10, 1, device_key="austragung",
                           state_class=SensorStateClass.TOTAL_INCREASING),
                FroelingHoldingSensor(coordinator, data, "dauer_des_ruettelns", 40125, "s", 1, 0, device_key="austragung"),  # Holding
            ])

        # ZIRKULATIONSPUMPE (unter Boiler 01 gruppiert)
        if data.get("zirkulationspumpe", False):
            sensors.extend([
                FroelingSensor(coordinator, data, "ruecklauftemperatur_an_der_zirkulations_leitung", 30712, "°C", 2, 0, device_class="temperature", device_key="boiler01"),
                FroelingSensor(coordinator, data, "stoemungsschalter_an_der_brauchwasser_leitung", 30601, "", 2, 0, device_key="boiler01"),
                FroelingSensor(coordinator, data, "drehzahl_der_zirkulations_pumpe", 30711, "%", 1, 0, device_key="boiler01"),
            ])

        return sensors

    # ——— Entitäten anlegen ———
    text_sensors = create_text_sensors()
    async_add_entities(text_sensors)

    sensors = create_sensors()
    async_add_entities(sensors)


# --------------------- Basisklassen ---------------------
class _FroelingBasis(FroelingEntity, SensorEntity):
    """Gemeinsames Verhalten aller Sensoren dieser Plattform.

    Die Werte kommen aus dem Coordinator; die Entitäten lesen selbst nicht mehr
    von der Anlage. Ob ein Register ein Input- oder Holding-Register ist,
    entscheidet die Registerlandkarte -- die Nummernkreise 3xxxx und 4xxxx
    überschneiden sich nicht.
    """

    _plattform = "sensor"

    def __init__(self, coordinator, data, entity_id, register, device_key):
        super().__init__(coordinator, data, entity_id, device_key)
        self._register = register


class _FroelingZahl(_FroelingBasis):
    """Zahlenwert mit Skalierung und Vorzeichenbehandlung."""

    def __init__(self, coordinator, data, entity_id, register,
                 unit, scaling_factor, decimal_places=0, device_class=None,
                 device_key="controller",
                 state_class=SensorStateClass.MEASUREMENT):
        super().__init__(coordinator, data, entity_id, register, device_key)
        self._unit = unit
        self._scaling_factor = scaling_factor
        self._decimal_places = decimal_places
        self._device_class = device_class
        self._state_class = state_class

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        # Eine Einheit ist fuer die Langzeitstatistik nicht noetig: Die
        # HA-Dokumentation nennt als Bedingung allein die state_class, und der
        # Recorder prueft in _is_numeric nur, ob der Wert eine endliche Zahl
        # ist. Auf der Anlage bestaetigt -- 56 von 60 einheitenlosen Sensoren
        # anderer Integrationen fuehren dort Statistik.
        return self._state_class

    @property
    def state(self):
        roh = self.coordinator.rohwert(self._register)
        if roh is None:
            return None
        if roh > 32767:          # 16 Bit, Zweierkomplement
            roh -= 65536
        wert = roh / (self._scaling_factor if self._scaling_factor else 1)
        if self._decimal_places == 0:
            return int(round(wert))
        return round(wert, self._decimal_places)


class _FroelingText(_FroelingBasis):
    """Zustandstext über eine Wertetabelle."""

    def __init__(self, coordinator, data, entity_id, register,
                 mapping, device_key="controller"):
        super().__init__(coordinator, data, entity_id, register, device_key)
        self._mapping = mapping

    @property
    def state(self):
        roh = self.coordinator.rohwert(self._register)
        if roh is None:
            return None
        return self._mapping.get(roh, f"Unknown ({roh})")


class FroelingSensor(_FroelingZahl):
    """Input-Register (3xxxx)."""


class FroelingHoldingSensor(_FroelingZahl):
    """Holding-Register (4xxxx)."""


class FroelingTextSensor(_FroelingText):
    """Text-Mapping über ein Input-Register (3xxxx)."""


class FroelingTextHoldingSensor(_FroelingText):
    """Text-Mapping über ein Holding-Register (4xxxx)."""


# --------------------- Text-Mappings ---------------------
ANLAGENZUSTAND_MAPPING = {
    0:"Dauerlast",1:"Brauchwasser",2:"Automatik",3:"Scheitholzbetr",4:"Reinigen",5:"Ausgeschaltet",6:"Extraheizen",7:"Kaminkehrer",8:"Reinigen"
}

KESSELZUSTAND_MAPPING = {
    0:"STÖRUNG",1:"Kessel Aus",2:"Anheizen",3:"Heizen",4:"Feuererhaltung",5:"Feuer Aus",6:"Tür offen",7:"Vorbereitung",8:"Vorwärmen",9:"Zünden",
    10:"Abstellen Warten",11:"Abstellen Warten1",12:"Abstellen Einschub1",13:"Abstellen Warten2",14:"Abstellen Einschub2",15:"Abreinigen",
    16:"2h warten",17:"Saugen / Heizen",18:"Fehlzündung",19:"Betriebsbereit",20:"Rost schließen",21:"Stoker leeren",22:"Vorheizen",23:"Saugen",
    24:"RSE schließen",25:"RSE öffnen",26:"Rost kippen",27:"Vorwärmen-Zünden",28:"Resteinschub",29:"Stoker auffüllen",30:"Lambdasonde aufheizen",
    31:"Gebläsenachlauf I",32:"Gebläsenachlauf II",33:"Abgestellt",34:"Nachzünden",35:"Zünden Warten",36:"FB: RSE schließen",37:"FB: Kessel belüften",
    38:"FB: Zünden",39:"FB: min. Einschub",40:"RSE schließen",41:"STÖRUNG: STB/NA",42:"STÖRUNG: Kipprost",43:"STÖRUNG: FR-Überdr.",44:"STÖRUNG: Türkont.",
    45:"STÖRUNG: Saugzug",46:"STÖRUNG: Umfeld",47:"FEHLER: STB/NA",48:"FEHLER: Kipprost",49:"FEHLER: FR-Überdr.",50:"FEHLER: Türkont.",
    51:"FEHLER: Saugzug",52:"FEHLER: Umfeld",53:"FEHLER: Stoker",54:"STÖRUNG: Stoker",55:"FB: Stoker leeren",56:"Vorbelüften",57:"STÖRUNG: Hackgut",
    58:"FEHLER: Hackgut",59:"NB: Tür offen",60:"NB: Anheizen",61:"NB: Heizen",62:"FEHLER: STB/NA",63:"FEHLER: Allgemein",64:"NB: Feuer Aus",
    65:"Selbsttest aktiv",66:"Fehlerbeh. 20min",67:"FEHLER: Fallschacht",68:"STÖRUNG: Fallschacht",69:"Reinigen möglich",70:"Heizen - Reinigen",
    71:"SH Anheizen",72:"SH Heizen",73:"SH Heiz/Abstell",74:"STÖRUNG sicher",75:"AGR Nachlauf",76:"AGR reinigen",77:"Zündung AUS",78:"Filter reinigen",
    79:"Anheizassistent",80:"SH Zünden",81:"SH Störung",82:"Sensorcheck",
    89:"Abstellen Warten (SH)",90:"Abreinigen (SH)"
}

LEGIONELLENTAG_MAPPING = {
    1:"Montag",2:"Dienstag",3:"Mittwoch",4:"Donnerstag",5:"Freitag",6:"Samstag",7:"Sonntag"
}
HK01PUFFERVERSORGUNG_MAPPING = {
    0:"Kessel",1:"Puffer01",2:"Puffer02",3:"Puffer03",4:"Puffer04"
}
HK02PUFFERVERSORGUNG_MAPPING = {
    0:"Kessel",1:"Puffer01",2:"Puffer02",3:"Puffer03",4:"Puffer04"
}
