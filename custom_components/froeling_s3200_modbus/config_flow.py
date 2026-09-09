"""Einrichtung über die Oberfläche.

Erstanlage und nachträgliche Konfiguration prüfen die Verbindung, bevor sie
speichern. Ohne diese Prüfung nimmt der Dialog jede Eingabe an -- ein
Zahlendreher im Port führt dann zu einer scheinbar sauber eingerichteten
Integration, deren Entitäten dauerhaft leer bleiben. Der Fehler steht dann nur
im Protokoll, und dort sucht ihn niemand.
"""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from pymodbus.client import ModbusTcpClient

from .const import DOMAIN, MAX_INTERVALL, MIN_INTERVALL, STANDARD_INTERVALL
from .modbus import read_input_sync
from .registers import INPUT_BASE, INPUT_REGISTERS

_LOGGER = logging.getLogger(__name__)

#: Zum Probelesen. Das erste bekannte Input-Register der Anlage.
PROBE_REGISTER = INPUT_REGISTERS[0]


#: Eingabepruefung fuer das Abfrageintervall.
_INTERVALL = vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVALL, max=MAX_INTERVALL))


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


async def pruefe_verbindung(hass: HomeAssistant, eingabe: dict) -> str | None:
    """Fehlerschluessel, oder None wenn die Anlage antwortet."""
    return await hass.async_add_executor_job(
        _probelesen,
        eingabe["host"],
        int(eingabe.get("port", 502)),
        int(eingabe.get("unit_id", 2)),
    )


def _gruppen_schema(vorgabe) -> dict:
    """Die sieben Anlagenteile, die ein- oder ausgeblendet werden können."""
    return {
        vol.Optional(name, default=vorgabe(name)): bool
        for name in ("kessel", "boiler01", "hk01", "hk02",
                     "austragung", "puffer01", "zirkulationspumpe")
    }


@config_entries.HANDLERS.register(DOMAIN)
class FroelingModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstanlage über die Oberfläche."""

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            fehler = await pruefe_verbindung(self.hass, user_input)
            if fehler is None:
                return self.async_create_entry(title=user_input["name"], data=user_input)
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
            **_gruppen_schema(lambda n: vorher.get(n, True)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FroelingOptionsFlow()


class FroelingOptionsFlow(config_entries.OptionsFlow):
    """Nachträgliche Konfiguration, ohne den Eintrag zu entfernen."""

    async def async_step_init(self, user_input=None):
        cfg = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            fehler = await pruefe_verbindung(self.hass, {**cfg, **user_input})
            if fehler is None:
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = fehler
            cfg = {**cfg, **user_input}

        schema = vol.Schema({
            vol.Optional("host", default=cfg.get("host", "")): str,
            vol.Optional("port", default=cfg.get("port", 502)): int,
            vol.Optional("unit_id", default=cfg.get("unit_id", 2)): int,
            vol.Optional("update_interval",
                         default=cfg.get("update_interval", STANDARD_INTERVALL)): _INTERVALL,
            **_gruppen_schema(lambda n: cfg.get(n, True)),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
