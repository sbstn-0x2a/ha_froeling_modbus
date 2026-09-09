"""Einrichtung über die Oberfläche.

Drei Schritte: Verbindung prüfen, Anlage einlesen, Anlagenteile bestätigen.

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
from pymodbus.client import ModbusTcpClient

from . import erkennung
from .const import (
    DOMAIN,
    MAX_INTERVALL,
    MIN_INTERVALL,
    STANDARD_INTERVALL,
    eindeutige_kennung,
)
from .device import DEVICE_NAME
from .modbus import read_input_sync
from .registers import INPUT_BASE, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)

#: Zum Probelesen. Das erste bekannte Input-Register der Anlage.
PROBE_REGISTER = INPUT_REGISTERS[0]

#: Die Anlagenteile, für die es Entitäten gibt -- Schlüssel im Config-Entry.
GRUPPEN = ("kessel", "boiler01", "hk01", "hk02", "austragung", "puffer01", "zirkulationspumpe")

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


def _vorbelegung(befund: erkennung.Befund | None, gruppe: str, bisher: bool | None = None) -> bool:
    """Haken aus der Erkennung: vorhanden -> an, nicht vorhanden -> aus,
    unsicher oder unbekannt -> wie bisher, sonst aus. Kessel immer an."""
    if gruppe == "kessel":
        return True
    zustand = _zustand(befund, gruppe)
    if zustand == erkennung.VORHANDEN:
        return True
    if zustand == erkennung.NICHT_VORHANDEN:
        return False
    return bool(bisher) if bisher is not None else befund is None


def _sichtbar(befund: erkennung.Befund | None, gruppe: str, bisher: bool | None = None) -> bool:
    """Im ersten Formular stehen nur erkannte oder bereits gewählte Teile."""
    if befund is None or gruppe == "kessel" or bisher:
        return True
    return _zustand(befund, gruppe) in (erkennung.VORHANDEN, erkennung.UNSICHER)


def belege_text(befund: erkennung.Befund | None, gruppen=GRUPPEN) -> str:
    """Eine Zeile je Anlagenteil, für die Beschreibung des Formulars."""
    if befund is None:
        return "Die Anlage konnte nicht gelesen werden; alle Teile sind vorbelegt."
    zeilen = []
    for gruppe in gruppen:
        instanz = GRUPPE_ZU_INSTANZ.get(gruppe, gruppe)
        eintrag = befund.instanzen.get(instanz)
        if eintrag is None:
            continue
        name = DEVICE_NAME.get(gruppe, gruppe)
        marke = {erkennung.VORHANDEN: "✔", erkennung.NICHT_VORHANDEN: "✘", erkennung.UNSICHER: "?"}[eintrag.zustand]
        zeilen.append(f"{marke} {name}: {eintrag.beleg}" if eintrag.beleg else f"{marke} {name}")
    if befund.fehlende_bloecke:
        zeilen.append(f"⚠ {len(befund.fehlende_bloecke)} Registerblock/-blöcke ohne Antwort")
    return "\n".join(zeilen)


def _gruppen_schema(gruppen, vorgabe) -> dict:
    return {vol.Optional(name, default=bool(vorgabe(name))): bool for name in gruppen}


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
        sichtbar = [g for g in GRUPPEN if _sichtbar(self._befund, g)]
        if user_input is not None:
            self._gewaehlt = {g: bool(user_input.get(g, False)) for g in sichtbar}
            uebrige = [g for g in GRUPPEN if g not in sichtbar]
            if user_input.get("weitere") and uebrige:
                return await self.async_step_weitere()
            return self._anlegen()

        schema = {**_gruppen_schema(sichtbar, lambda g: _vorbelegung(self._befund, g))}
        if len(sichtbar) < len(GRUPPEN):
            schema[vol.Optional("weitere", default=False)] = bool
        return self.async_show_form(
            step_id="anlagenteile",
            data_schema=vol.Schema(schema),
            description_placeholders={"belege": belege_text(self._befund)},
        )

    async def async_step_weitere(self, user_input=None):
        """Anlagenteile, die die Erkennung nicht gefunden hat."""
        uebrige = [g for g in GRUPPEN if g not in self._gewaehlt]
        if user_input is not None:
            self._gewaehlt.update({g: bool(user_input.get(g, False)) for g in uebrige})
            return self._anlegen()
        return self.async_show_form(
            step_id="weitere",
            data_schema=vol.Schema(_gruppen_schema(uebrige, lambda g: False)),
            description_placeholders={"belege": belege_text(self._befund, uebrige)},
        )

    def _anlegen(self):
        data = {
            **self._verbindung,
            **{g: self._gewaehlt.get(g, False) for g in GRUPPEN},
            "erkannt": erkannt_als_dict(self._befund),
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
    """Nachträgliche Konfiguration: Verbindung, Anlagenteile, neu einlesen."""

    def __init__(self) -> None:
        self._befund: erkennung.Befund | None = None

    @property
    def _cfg(self) -> dict:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["verbindung", "anlagenteile", "neu_einlesen"]
        )

    async def async_step_verbindung(self, user_input=None):
        cfg = self._cfg
        errors: dict[str, str] = {}
        if user_input is not None:
            fehler = await pruefe_verbindung(self.hass, {**cfg, **user_input})
            if fehler is None:
                return self.async_create_entry(
                    title="", data={**self.config_entry.options, **user_input}
                )
            errors["base"] = fehler
            cfg = {**cfg, **user_input}
        schema = vol.Schema({
            vol.Optional("host", default=cfg.get("host", "")): str,
            vol.Optional("port", default=cfg.get("port", 502)): int,
            vol.Optional("unit_id", default=cfg.get("unit_id", 2)): int,
            vol.Optional("update_interval",
                         default=cfg.get("update_interval", STANDARD_INTERVALL)): _INTERVALL,
        })
        return self.async_show_form(step_id="verbindung", data_schema=schema, errors=errors)

    async def async_step_anlagenteile(self, user_input=None):
        cfg = self._cfg
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **{g: bool(user_input.get(g, False)) for g in GRUPPEN}},
            )
        return self.async_show_form(
            step_id="anlagenteile",
            data_schema=vol.Schema(_gruppen_schema(GRUPPEN, lambda g: cfg.get(g, True))),
        )

    async def async_step_neu_einlesen(self, user_input=None):
        """Anlage scannen und die Haken neu vorschlagen. Nichts ohne Bestätigung."""
        cfg = self._cfg
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    **{g: bool(user_input.get(g, False)) for g in GRUPPEN},
                    "erkannt": erkannt_als_dict(self._befund),
                },
            )
        self._befund = await anlage_einlesen(self.hass, cfg)
        if self._befund is None:
            return self.async_show_form(
                step_id="neu_einlesen",
                data_schema=vol.Schema(_gruppen_schema(GRUPPEN, lambda g: cfg.get(g, True))),
                errors={"base": "cannot_connect"},
                description_placeholders={"belege": belege_text(None)},
            )
        return self.async_show_form(
            step_id="neu_einlesen",
            data_schema=vol.Schema(
                _gruppen_schema(GRUPPEN, lambda g: _vorbelegung(self._befund, g, cfg.get(g)))
            ),
            description_placeholders={"belege": belege_text(self._befund)},
        )
