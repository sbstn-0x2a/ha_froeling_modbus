"""Einrichtung über die Oberfläche.

Vier Schritte: Verbindung prüfen, Anlage einlesen, Anlagenteile bestätigen,
Kesselfernsteuerung ein- oder ausschalten.

Die Verbindungsprüfung stand zuerst: Ohne sie nimmt der Dialog jede Eingabe
an, und ein Zahlendreher im Port führt zu einer scheinbar sauber
eingerichteten Integration, deren Entitäten dauerhaft leer bleiben.

Das Einlesen kam mit der Parameteranalyse vom 09.09.2026 dazu: Jede Anlage
ist anders bestückt, und die feste Auswahl erzeugte Entitäten für Teile, die
es gar nicht gibt (Heizkreis 01 an einer Anlage mit nur Heizkreis 02). Der
Scan liest alle Register einmal (rund 60 Anfragen, wenige Sekunden) und
belegt die Haken vor; der Nutzer sieht den Beleg und entscheidet. Es gibt
kein Register, das das Anlagenart-Menü des Bediengeräts abbildet, deshalb
bleibt es ein Vorschlag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from pymodbus.client import ModbusTcpClient

from . import erkennung, umbenennung
from .const import (
    DOMAIN,
    MAX_INTERVALL,
    MIN_INTERVALL,
    STANDARD_INTERVALL,
    eindeutige_kennung,
)
from .device import DEVICE_NAME, objekt_id
from .entitaeten import TOTE_DEAKTIVIERT, TOTE_UMGANG, ausgeschlossen, ausschluss_kandidaten
from .modbus import read_input_sync
from .registers import INPUT_BASE, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)

#: Zum Probelesen. Das erste bekannte Input-Register der Anlage.
PROBE_REGISTER = INPUT_REGISTERS[0]

#: Die acht Anlagenteile der 0.4.0 -- immer im Dialog, Schlüssel im Config-Entry.
BASISGRUPPEN = ("kessel", "boiler01", "hk01", "hk02", "austragung", "puffer01", "zirkulationspumpe", "efilter")
#: Folgeinstanzen (Spiegelung der Registertabelle). Sie erscheinen im Dialog
#: nur, wenn die Erkennung sie als vorhanden meldet oder sie schon angehakt
#: sind -- eine Anlage mit zwei Heizkreisen soll keine 30 Haken sehen.
ERWEITERTE_GRUPPEN = (
    *(f"hk{n:02d}" for n in range(3, 19)),
    *(f"boiler{n:02d}" for n in range(2, 9)),
    *(f"puffer{n:02d}" for n in range(2, 5)),
)
#: Muss mit __init__.GRUPPEN uebereinstimmen.
GRUPPEN = BASISGRUPPEN + ERWEITERTE_GRUPPEN

#: Instanzkennung der Erkennung -> Schlüssel im Config-Entry (sonst gleich).
INSTANZ_ZU_GRUPPE = {"zirkulation": "zirkulationspumpe"}
GRUPPE_ZU_INSTANZ = {v: k for k, v in INSTANZ_ZU_GRUPPE.items()}

VERBINDUNGSFELDER = ("host", "port", "unit_id", "update_interval")

#: Eingabepruefung fuer das Abfrageintervall.
_INTERVALL = vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVALL, max=MAX_INTERVALL))


# --------------------------------------------------------------------------
# Modbus-Zugriffe (Executor)
# --------------------------------------------------------------------------

def _probelesen(host: str, port: int, unit_id: int) -> str | None:
    """Liest ein einzelnes Register zur Probe.

    Rueckgabe ist der Uebersetzungsschluessel des Fehlers, oder None bei
    Erfolg. Die Unterscheidung ist fuer den Nutzer wesentlich: Kommt gar keine
    Verbindung zustande, stimmen Host oder Port nicht. Antwortet das Geraet
    und weist die Anfrage ab, ist meist die Unit-ID falsch -- und danach
    wuerde man an der falschen Stelle suchen.
    """
    client = ModbusTcpClient(host, port=port, timeout=3, retries=1)
    try:
        res, err = read_input_sync(client, unit_id, PROBE_REGISTER - INPUT_BASE, 1)
        if res is not None and hasattr(res, "registers") and not err:
            return None
        _LOGGER.debug(
            "Probelesen an %s:%s (unit_id %s) fehlgeschlagen: %s",
            host, port, unit_id, err,
        )
        if err and str(err).startswith("error("):
            # TCP stand, der Kessel hat die Anfrage abgelehnt.
            return "invalid_unit_id"
        return "cannot_connect"
    except Exception:  # noqa: BLE001 - jeder Fehler bedeutet: nicht erreichbar
        _LOGGER.debug("Probelesen an %s:%s warf eine Ausnahme", host, port, exc_info=True)
        return "cannot_connect"
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


def _scan(host: str, port: int, unit_id: int):
    client = ModbusTcpClient(host, port=port, timeout=5, retries=1)
    try:
        return erkennung.scan(client, unit_id)
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


async def pruefe_verbindung(hass: HomeAssistant, eingabe: dict) -> str | None:
    """Fehlerschluessel, oder None wenn die Anlage antwortet."""
    return await hass.async_add_executor_job(
        _probelesen,
        eingabe["host"],
        int(eingabe.get("port", 502)),
        int(eingabe.get("unit_id", 2)),
    )


async def anlage_einlesen(hass: HomeAssistant, eingabe: dict) -> erkennung.Befund | None:
    """Vollscan und Auswertung. None, wenn die Anlage gar nicht antwortet."""
    try:
        werte, fehler = await hass.async_add_executor_job(
            _scan, eingabe["host"], int(eingabe.get("port", 502)), int(eingabe.get("unit_id", 2))
        )
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Einlesen der Anlage fehlgeschlagen", exc_info=True)
        return None
    if not werte:
        return None
    if fehler:
        _LOGGER.warning("Einlesen unvollständig, %d Block/Blöcke ohne Antwort: %s",
                        len(fehler), fehler[:3])
    return erkennung.auswerten(werte, fehler)


# --------------------------------------------------------------------------
# Hilfen für die Formulare
# --------------------------------------------------------------------------

def erkannt_als_dict(befund: erkennung.Befund | None) -> dict:
    """Serialisierbarer Befund für den Config-Entry."""
    if befund is None:
        return {"zeit": datetime.now(timezone.utc).isoformat(), "vorschlag": {}, "belege": {}, "tot": {},
                "fehlende_bloecke": []}
    return {
        "zeit": datetime.now(timezone.utc).isoformat(),
        "vorschlag": befund.vorschlag(),
        "belege": befund.belege(),
        "tot": {str(k): v for k, v in sorted(befund.tot.items())},
        "fehlende_bloecke": list(befund.fehlende_bloecke),
    }


def _zustand(befund: erkennung.Befund | None, gruppe: str) -> str | None:
    if befund is None:
        return None
    instanz = GRUPPE_ZU_INSTANZ.get(gruppe, gruppe)
    eintrag = befund.instanzen.get(instanz)
    return eintrag.zustand if eintrag else None


def _zustand_aus_entry(cfg: dict, gruppe: str) -> str | None:
    """Zustand aus dem gespeicherten Befund (``erkannt.vorschlag``) -- für den
    Options-Flow, der ohne neues Einlesen auskommen muss."""
    vorschlag = (cfg.get("erkannt") or {}).get("vorschlag") or {}
    return vorschlag.get(GRUPPE_ZU_INSTANZ.get(gruppe, gruppe))


def _angeboten(gruppe: str, zustand: str | None, bisher: bool | None = None) -> bool:
    """Steht der Haken überhaupt im Formular?

    Die acht Basisgruppen immer. Eine Folgeinstanz nur, wenn die Erkennung
    sie als vorhanden meldet oder sie bereits angehakt ist -- auch nicht
    unter „weitere Anlagenteile“: Wer dort Heizkreis 03 bis 18 anbietet,
    zeigt einer Anlage mit zwei Heizkreisen 30 Haken.
    """
    if gruppe in BASISGRUPPEN:
        return True
    return zustand == erkennung.VORHANDEN or bool(bisher)


def _vorbelegung(befund: erkennung.Befund | None, gruppe: str, bisher: bool | None = None) -> bool:
    """Haken aus der Erkennung.

    Vorhanden -> an. Nicht vorhanden -> aus, **außer** das Teil ist bereits
    aktiv: Ein abgewähltes Teil wird samt Entitäten entfernt, und das nimmt
    die Historie mit. Deshalb schlägt das Neu-Einlesen kein Entfernen vor,
    sondern nennt es nur in der Beschreibung; der Nutzer nimmt den Haken
    selbst heraus. Unsicher oder unbekannt -> wie bisher. Kessel immer an.
    """
    if gruppe == "kessel":
        return True
    zustand = _zustand(befund, gruppe)
    if zustand == erkennung.VORHANDEN:
        return True
    if zustand == erkennung.NICHT_VORHANDEN:
        return bool(bisher)
    return bool(bisher) if bisher is not None else befund is None


def _sichtbar(befund: erkennung.Befund | None, gruppe: str, bisher: bool | None = None) -> bool:
    """Im ersten Formular stehen nur erkannte oder bereits gewählte Teile."""
    if befund is None or gruppe == "kessel" or bisher:
        return True
    return _zustand(befund, gruppe) in (erkennung.VORHANDEN, erkennung.UNSICHER)


def belege_text(befund: erkennung.Befund | None, gruppen=GRUPPEN, bisher: dict | None = None) -> str:
    """Eine Zeile je Anlagenteil, für die Beschreibung des Formulars."""
    if befund is None:
        return "Die Anlage konnte nicht gelesen werden; alle Teile sind vorbelegt."
    zeilen = []
    for gruppe in gruppen:
        instanz = GRUPPE_ZU_INSTANZ.get(gruppe, gruppe)
        eintrag = befund.instanzen.get(instanz)
        if eintrag is None:
            continue
        if gruppe not in BASISGRUPPEN and eintrag.zustand == erkennung.NICHT_VORHANDEN \
                and not (bisher and bisher.get(gruppe)):
            # 27 Zeilen "✘ Heizkreis 07 Istwerte 0" sagen nichts; nur
            # Folgeinstanzen mit Befund oder Haken kommen in den Text.
            continue
        name = DEVICE_NAME.get(gruppe, gruppe)
        marke = {erkennung.VORHANDEN: "✔", erkennung.NICHT_VORHANDEN: "✘", erkennung.UNSICHER: "?"}[eintrag.zustand]
        # Kurz halten: Das Fenster des Dialogs ist schmal, lange Zeilen
        # brechen unschoen um. Deshalb Aufzaehlung, Beleg ohne Registernamen.
        beleg = eintrag.beleg.replace("Vorlauf-Isttemperatur ", "").replace("Puffertemperatur ", "")
        beleg = beleg.replace("Boilertemperatur oben ", "").replace("Raumtemperatur ", "Raum ")
        zeile = f"- {marke} **{name}** {beleg}".rstrip()
        if bisher and bisher.get(gruppe) and eintrag.zustand == erkennung.NICHT_VORHANDEN:
            zeile += " (bisher aktiv, Haken entfernen löscht die Entitäten samt Historie)"
        zeilen.append(zeile)
    if befund.fehlende_bloecke:
        zeilen.append(f"- ⚠ {len(befund.fehlende_bloecke)} Registerblock/-blöcke ohne Antwort")
    return "\n".join(zeilen)


def tot_text(befund: erkennung.Befund | None) -> str:
    """Register ohne brauchbaren Wert, für die Beschreibung des Formulars."""
    if befund is None or not befund.tot:
        return "keine"
    from .registertabelle import NACH_NUMMER
    # Nur die Namen, nach Grund gebuendelt -- der Grund steht spaeter am
    # Attribut jeder Entitaet.
    je_grund: dict[str, list[str]] = {}
    for nummer, grund in sorted(befund.tot.items()):
        z = NACH_NUMMER.get(("input", nummer)) or NACH_NUMMER.get(("holding", nummer))
        kurz = grund.split(" (")[0].split(" nach ")[0]
        je_grund.setdefault(kurz, []).append(z.name_de if z else str(nummer))
    return "\n".join(f"- **{grund}:** {', '.join(namen)}" for grund, namen in je_grund.items())


#: Auswahl, was mit Registern ohne brauchbaren Wert geschieht.
_TOTE_AUSWAHL = SelectSelector(SelectSelectorConfig(
    options=list(TOTE_UMGANG), translation_key="tote", mode=SelectSelectorMode.LIST
))


def _gruppen_schema(gruppen, vorgabe) -> dict:
    return {vol.Optional(name, default=bool(vorgabe(name))): bool for name in gruppen}


def ausschluss_optionen(hass: HomeAssistant, cfg: dict) -> list[SelectOptionDict]:
    """Auswahlliste für „Entitäten entfernen“: Wert ist der Entitätsschlüssel,
    Beschriftung „Gerät · Name (entity_id)“, sortiert nach Gerät und Name.

    Name und entity_id kommen aus der Entity-Registry, damit der Nutzer
    seine eigenen Umbenennungen wiedererkennt. Eine bereits entfernte
    Entität hat keinen Registry-Eintrag mehr (Home Assistant hebt sie nur
    als geloescht auf); dann stehen der Doku-Name der Zeile und der
    Vorschlag von objekt_id da.
    """
    reg = er.async_get(hass)
    name = cfg["name"]
    eintraege = []
    for z in ausschluss_kandidaten(cfg):
        geraet = z.altes_geraet or z.gruppe or "controller"
        geraetename = name if geraet == "controller" else DEVICE_NAME.get(geraet, geraet)
        entity_id = reg.async_get_entity_id(z.plattform, DOMAIN, f"{name}_{z.entitaetsschluessel}")
        anzeigename = z.name_de
        if entity_id is not None:
            eintrag = reg.async_get(entity_id)
            anzeigename = eintrag.name or eintrag.original_name or z.name_de
        else:
            entity_id = objekt_id(z.plattform, name, geraet, z.entitaetsschluessel)
        eintraege.append((geraetename, anzeigename, entity_id, z.entitaetsschluessel))
    eintraege.sort(key=lambda e: (e[0].lower(), e[1].lower()))
    return [SelectOptionDict(value=schluessel, label=f"{geraet} · {anzeige} ({eid})")
            for geraet, anzeige, eid, schluessel in eintraege]


def _fernsteuerung_schema(vorgabe: bool) -> vol.Schema:
    """Ein Haken. Vorgabe aus: Die Fernsteuerung schreibt an die Anlage und
    uebernimmt alle Heizkreise und Boiler -- das schaltet man bewusst ein."""
    return vol.Schema({vol.Optional("fernsteuerung", default=bool(vorgabe)): bool})


# --------------------------------------------------------------------------
# Config-Flow
# --------------------------------------------------------------------------

@config_entries.HANDLERS.register(DOMAIN)
class FroelingModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstanlage über die Oberfläche."""

    def __init__(self) -> None:
        self._verbindung: dict = {}
        self._befund: erkennung.Befund | None = None
        self._gewaehlt: dict[str, bool] = {}
        self._tote = TOTE_DEAKTIVIERT
        self._fernsteuerung = False

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            # Dieselbe Anlage nicht zweimal einrichten. Ohne diese Pruefung
            # entstehen zwei Hubs mit denselben Geraeten und Entitaeten, nur
            # unter verschiedenen Namen.
            await self.async_set_unique_id(eindeutige_kennung(
                user_input["host"],
                user_input.get("port", 502),
                user_input.get("unit_id", 2),
            ))
            self._abort_if_unique_id_configured()

            fehler = await pruefe_verbindung(self.hass, user_input)
            if fehler is None:
                self._verbindung = dict(user_input)
                self._befund = await anlage_einlesen(self.hass, user_input)
                return await self.async_step_anlagenteile()
            errors["base"] = fehler

        # Bei einem Fehler die Eingaben erhalten, statt sie zu verwerfen.
        vorher = user_input or {}
        schema = vol.Schema({
            vol.Required("name", default=vorher.get("name", "Froeling")): str,
            vol.Required("host", default=vorher.get("host", "")): str,
            vol.Required("port", default=vorher.get("port", 502)): int,
            vol.Optional("unit_id", default=vorher.get("unit_id", 2)): int,
            vol.Required("update_interval",
                         default=vorher.get("update_interval", STANDARD_INTERVALL)): _INTERVALL,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_anlagenteile(self, user_input=None):
        """Erkannte Anlagenteile bestätigen."""
        sichtbar = [g for g in GRUPPEN
                    if _angeboten(g, _zustand(self._befund, g)) and _sichtbar(self._befund, g)]
        # "Weitere" kennt nur die Basisgruppen; Folgeinstanzen ohne Befund
        # gibt es im Dialog nicht.
        uebrige = [g for g in BASISGRUPPEN if g not in sichtbar]
        if user_input is not None:
            self._gewaehlt = {g: bool(user_input.get(g, False)) for g in sichtbar}
            self._tote = user_input.get("tote", TOTE_DEAKTIVIERT)
            if user_input.get("weitere") and uebrige:
                return await self.async_step_weitere()
            return await self.async_step_fernsteuerung()

        schema = {**_gruppen_schema(sichtbar, lambda g: _vorbelegung(self._befund, g))}
        if self._befund is not None and self._befund.tot:
            schema[vol.Optional("tote", default=TOTE_DEAKTIVIERT)] = _TOTE_AUSWAHL
        if uebrige:
            schema[vol.Optional("weitere", default=False)] = bool
        return self.async_show_form(
            step_id="anlagenteile",
            data_schema=vol.Schema(schema),
            description_placeholders={"belege": belege_text(self._befund),
                                      "tot": tot_text(self._befund)},
        )

    async def async_step_weitere(self, user_input=None):
        """Anlagenteile, die die Erkennung nicht gefunden hat."""
        uebrige = [g for g in BASISGRUPPEN if g not in self._gewaehlt]
        if user_input is not None:
            self._gewaehlt.update({g: bool(user_input.get(g, False)) for g in uebrige})
            return await self.async_step_fernsteuerung()
        return self.async_show_form(
            step_id="weitere",
            data_schema=vol.Schema(_gruppen_schema(uebrige, lambda g: False)),
            description_placeholders={"belege": belege_text(self._befund, uebrige)},
        )

    async def async_step_fernsteuerung(self, user_input=None):
        """Kesselfernsteuerung ein- oder ausschalten -- letzter Schritt.

        Eigener Schritt mit Erklaerung, weil die Fernsteuerung anders wirkt
        als ein Anlagenteil: Sie schreibt an die Anlage und uebernimmt bei
        Regelung "Home Assistant" die Sollwerte aller Heizkreise und Boiler.
        """
        if user_input is not None:
            self._fernsteuerung = bool(user_input.get("fernsteuerung", False))
            return self._anlegen()
        return self.async_show_form(
            step_id="fernsteuerung", data_schema=_fernsteuerung_schema(False)
        )

    def _anlegen(self):
        data = {
            **self._verbindung,
            **{g: self._gewaehlt.get(g, False) for g in BASISGRUPPEN},
            # Folgeinstanzen nur, wenn gewaehlt -- sonst staenden 27 False im Entry.
            **{g: True for g in ERWEITERTE_GRUPPEN if self._gewaehlt.get(g)},
            "erkannt": erkannt_als_dict(self._befund),
            "tote": self._tote,
            "fernsteuerung": self._fernsteuerung,
        }
        return self.async_create_entry(title=self._verbindung["name"], data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FroelingOptionsFlow()


# --------------------------------------------------------------------------
# Options-Flow
# --------------------------------------------------------------------------

class FroelingOptionsFlow(config_entries.OptionsFlow):
    """Nachträgliche Konfiguration: Verbindung, Anlagenteile, Fernsteuerung,
    neu einlesen, einzelne Entitäten entfernen, Entitäts-IDs angleichen."""

    def __init__(self) -> None:
        self._befund: erkennung.Befund | None = None

    @property
    def _cfg(self) -> dict:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["verbindung", "anlagenteile", "fernsteuerung", "neu_einlesen",
                          "entitaeten_entfernen", "entitaets_ids"],
        )

    async def async_step_entitaeten_entfernen(self, user_input=None):
        """Einzelne Entitäten ausschließen -- ohne die Entitätenliste von
        Home Assistant. Ausgeschlossene werden nicht angelegt und nicht
        gelesen; ihre Registry-Einträge räumt _verwaiste_entfernen beim
        Reload weg (Historie geht verloren). Abwählen bringt sie beim
        nächsten Speichern zurück: Home Assistant stellt gelöschte Einträge
        mit alter entity_id wieder her (Dev-HA, 12.09.2026).
        """
        cfg = self._cfg
        optionen = ausschluss_optionen(self.hass, cfg)
        angeboten = {o["value"] for o in optionen}
        bisher = ausgeschlossen(cfg)
        if user_input is not None:
            gewaehlt = {k for k in user_input.get("ausgeschlossen", []) if k in angeboten}
            # Schluessel abgewaehlter Anlagenteile stehen nicht im Formular;
            # sie bleiben stehen (harmlos), statt still zu verschwinden.
            neu = (bisher - angeboten) | gewaehlt
            return self.async_create_entry(
                title="", data={**self.config_entry.options, "ausgeschlossen": sorted(neu)}
            )
        auswahl = SelectSelector(SelectSelectorConfig(
            options=optionen, multiple=True, custom_value=False, mode=SelectSelectorMode.DROPDOWN,
        ))
        return self.async_show_form(
            step_id="entitaeten_entfernen",
            data_schema=vol.Schema({
                vol.Optional("ausgeschlossen", default=sorted(bisher & angeboten)): auswahl,
            }),
            description_placeholders={"anzahl": str(len(bisher & angeboten))},
        )

    async def async_step_fernsteuerung(self, user_input=None):
        """Kesselfernsteuerung ein- oder ausschalten. Speichern laedt neu;
        ausschalten entfernt die Fernsteuer-Entitaeten samt Historie."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options,
                      "fernsteuerung": bool(user_input.get("fernsteuerung", False))},
            )
        return self.async_show_form(
            step_id="fernsteuerung",
            data_schema=_fernsteuerung_schema(self._cfg.get("fernsteuerung", False)),
        )

    async def async_step_entitaets_ids(self, user_input=None):
        """Entitäts-IDs an das Schema angleichen (Anlage, Gerät, Größe).

        Zeigt alt → neu, benennt erst nach Bestätigung um. Historie und
        Statistik ziehen mit, Automationen und Dashboards nicht.
        """
        paare = umbenennung.vorschlaege(self.hass, self._cfg)
        if not paare:
            return self.async_abort(reason="nichts_umzubenennen")
        if user_input is not None:
            if not user_input.get("bestaetigen"):
                return self.async_abort(reason="abgebrochen")
            ok, uebersprungen = umbenennung.umbenennen(self.hass, paare)
            return self.async_abort(
                reason="umbenannt",
                description_placeholders={
                    "anzahl": str(ok),
                    "uebersprungen": "\n".join(uebersprungen) or "keine",
                },
            )
        liste = "\n".join(f"{alt} → {neu}" for alt, neu in paare)
        return self.async_show_form(
            step_id="entitaets_ids",
            data_schema=vol.Schema({vol.Required("bestaetigen", default=False): bool}),
            description_placeholders={"anzahl": str(len(paare)), "liste": liste},
        )

    async def async_step_verbindung(self, user_input=None):
        cfg = self._cfg
        errors: dict[str, str] = {}
        if user_input is not None:
            neu = {**cfg, **user_input}
            geaendert = any(str(neu.get(k)) != str(cfg.get(k)) for k in ("host", "port", "unit_id"))
            # Nur eine geaenderte Verbindung wird geprueft: Ein neues Intervall
            # muss sich auch speichern lassen, wenn die Anlage gerade aus ist.
            fehler = await pruefe_verbindung(self.hass, neu) if geaendert else None
            if fehler is None:
                if geaendert:
                    # Die Kennung des Eintrags folgt der Verbindung, sonst
                    # liesse sich die neue Adresse ein zweites Mal anlegen.
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        unique_id=eindeutige_kennung(neu["host"], neu.get("port", 502), neu.get("unit_id", 2)),
                    )
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, **user_input}
                )
            errors["base"] = fehler
            cfg = neu
        schema = vol.Schema({
            vol.Optional("host", default=cfg.get("host", "")): str,
            vol.Optional("port", default=cfg.get("port", 502)): int,
            vol.Optional("unit_id", default=cfg.get("unit_id", 2)): int,
            vol.Optional("update_interval",
                         default=cfg.get("update_interval", STANDARD_INTERVALL)): _INTERVALL,
        })
        return self.async_show_form(step_id="verbindung", data_schema=schema, errors=errors)

    def _angebotene_gruppen(self, befund: erkennung.Befund | None = None) -> list[str]:
        """Basisgruppen plus Folgeinstanzen, die erkannt oder angehakt sind --
        aus dem frischen Befund, sonst aus dem gespeicherten."""
        cfg = self._cfg
        return [
            g for g in GRUPPEN
            if _angeboten(g, _zustand(befund, g) if befund is not None else _zustand_aus_entry(cfg, g), cfg.get(g))
        ]

    async def async_step_anlagenteile(self, user_input=None):
        cfg = self._cfg
        gruppen = self._angebotene_gruppen()
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **{g: bool(user_input.get(g, False)) for g in gruppen}},
            )
        return self.async_show_form(
            step_id="anlagenteile",
            data_schema=vol.Schema(_gruppen_schema(gruppen, lambda g: cfg.get(g, g in BASISGRUPPEN))),
        )

    async def async_step_neu_einlesen(self, user_input=None):
        """Anlage scannen und die Haken neu vorschlagen. Nichts ohne Bestätigung."""
        cfg = self._cfg
        if user_input is not None:
            gruppen = self._angebotene_gruppen(self._befund)
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    **{g: bool(user_input.get(g, False)) for g in gruppen},
                    "erkannt": erkannt_als_dict(self._befund),
                    "tote": user_input.get("tote", TOTE_DEAKTIVIERT),
                },
            )
        self._befund = await anlage_einlesen(self.hass, cfg)
        if self._befund is None:
            return self.async_show_form(
                step_id="neu_einlesen",
                data_schema=vol.Schema(_gruppen_schema(self._angebotene_gruppen(),
                                                       lambda g: cfg.get(g, g in BASISGRUPPEN))),
                errors={"base": "cannot_connect"},
                description_placeholders={"belege": belege_text(None), "tot": "keine"},
            )
        gruppen = self._angebotene_gruppen(self._befund)
        schema = _gruppen_schema(gruppen, lambda g: _vorbelegung(self._befund, g, cfg.get(g)))
        if self._befund.tot:
            schema[vol.Optional("tote", default=cfg.get("tote", TOTE_DEAKTIVIERT))] = _TOTE_AUSWAHL
        return self.async_show_form(
            step_id="neu_einlesen",
            data_schema=vol.Schema(schema),
            description_placeholders={"belege": belege_text(self._befund, bisher=cfg),
                                      "tot": tot_text(self._befund)},
        )
