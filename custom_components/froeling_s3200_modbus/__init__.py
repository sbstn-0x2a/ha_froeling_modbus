from __future__ import annotations

import logging
import pymodbus
from pymodbus.client import ModbusTcpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import STANDARD_INTERVALL, eindeutige_kennung
from .coordinator import FroelingCoordinator, FroelingRuntimeData

for name in ("pymodbus", "pymodbus.client", "pymodbus.transaction", "pymodbus.framer", "pymodbus.logging"):
    logging.getLogger(name).setLevel(logging.WARNING)

DOMAIN = "froeling_s3200_modbus"
_LOGGER = logging.getLogger(__name__)

#: Gruppen, deren Entitaeten unter einem fremden Geraet haengen.
#:
#: Das Aufraeumen beim Abwaehlen einer Gruppe laeuft ueber deren Geraet: alle
#: Entitaeten daran werden entfernt. Die Zirkulationspumpe hat aber bewusst
#: kein eigenes Geraet, ihre Sensoren sitzen unter Boiler 01. Ohne diese Liste
#: bleiben sie beim Abwaehlen als unavailable in der Registry stehen.
GRUPPEN_OHNE_EIGENES_GERAET: dict[str, tuple[tuple[str, str], ...]] = {
    "zirkulationspumpe": (
        # Kein eigenes Geraet, die drei sitzen unter Boiler 01.
        ("sensor", "ruecklauftemperatur_an_der_zirkulations_leitung"),
        ("sensor", "stoemungsschalter_an_der_brauchwasser_leitung"),
        ("sensor", "drehzahl_der_zirkulations_pumpe"),
    ),
    "kessel": (
        # Inhaltlich bewusst woanders einsortiert: die Nachlegeberechnung
        # gehoert zum Puffer, die Ruecklauftemperatur der Zirkulationsleitung
        # zum Boiler.
        ("binary_sensor", "nachlegeberechnung_aktiv"),
        ("number", "bei_welcher_rl_temperatur_an_der_zirkulationsleitung_soll_die_pumpe_ausschalten"),
    ),
}


PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TIME,
]

async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the integration from a config entry."""
    # entry.data ist immutable → kopieren und Optionen überlagern
    data = dict(entry.data)
    if entry.options:
        data.update(entry.options)
    data.setdefault("unit_id", 2)

    # Eintraege aus aelteren Fassungen haben keine Kennung. Ohne sie greift die
    # Dublettenpruefung im Config-Flow nicht. Bewusst hier oben, bevor der
    # Update-Listener haengt -- sonst loeste die Aenderung einen Reload aus.
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=eindeutige_kennung(data["host"], data.get("port", 502), data["unit_id"]),
        )

    # Ein Client je Config-Entry, einmalig verbunden. Serialisiert wird im
    # Coordinator (siehe FroelingCoordinator._modbus) -- pymodbus ist nicht
    # threadsicher, und alle Zugriffe laufen ueber den Executor.
    client = ModbusTcpClient(
        data["host"],
        port=data.get("port", 502),
        timeout=3,
        retries=2,
    )
    try:
        client.connect()
    except Exception:
        pass

    _LOGGER.debug(
        "Froeling Modbus initialisiert (pymodbus=%s, host=%s, port=%s, unit_id=%s)",
        pymodbus.__version__,
        data["host"],
        data.get("port", 502),
        data["unit_id"],
    )

    # Ein Coordinator fuer alle Entitaeten. Bewusst async_refresh statt
    # async_config_entry_first_refresh: Letzteres wuerde das Setup abbrechen,
    # wenn die Anlage beim Start nicht erreichbar ist, und die Entitaeten
    # gaebe es dann gar nicht -- Automationen wuerden ins Leere greifen. So
    # entstehen sie immer und melden sich bei Lesefehlern als unavailable.
    coordinator = FroelingCoordinator(
        hass, entry, client, data["unit_id"], data.get("update_interval", STANDARD_INTERVALL)
    )
    await coordinator.async_refresh()
    entry.runtime_data = FroelingRuntimeData(coordinator, data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- Options-Update: deaktivierte Gruppen aufräumen und reloaden ----
    async def _cleanup_disabled_groups_and_reload(
        hass: HomeAssistant, updated_entry: ConfigEntry
    ):
        laufzeit = getattr(updated_entry, "runtime_data", None)
        old_cfg = laufzeit.konfiguration if laufzeit else {}
        new_cfg = {**updated_entry.data, **updated_entry.options}

        name = new_cfg.get("name", old_cfg.get("name", "Froeling"))
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)

        groups = [
            "kessel",
            "boiler01",
            "hk01",
            "hk02",
            "austragung",
            "puffer01",
            "zirkulationspumpe",
        ]

        to_remove = [g for g in groups if old_cfg.get(g, False) and not new_cfg.get(g, False)]

        for g in to_remove:
            # Zuerst die Ausnahmen: Entitaeten ohne eigenes Gruppengeraet.
            for entity_domain, schluessel in GRUPPEN_OHNE_EIGENES_GERAET.get(g, ()):
                eindeutig = f"{name}_{schluessel}"
                entity_id = ent_reg.async_get_entity_id(entity_domain, DOMAIN, eindeutig)
                if entity_id:
                    ent_reg.async_remove(entity_id)

            ident = (DOMAIN, f"{name}:{g}")
            device = dev_reg.async_get_device({ident})
            if not device:
                continue

            for ent in list(ent_reg.entities.values()):
                if ent.config_entry_id == updated_entry.entry_id and ent.device_id == device.id:
                    ent_reg.async_remove(ent.entity_id)

            try:
                dev_reg.async_remove_device(device.id)
            except Exception:
                _LOGGER.debug("Device %s konnte nicht entfernt werden", device.id)

        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_cleanup_disabled_groups_and_reload))
    # --------------------------------------------------------------------

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and close the client."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    laufzeit: FroelingRuntimeData | None = getattr(entry, "runtime_data", None)
    if laufzeit is not None:
        try:
            laufzeit.coordinator.client_schliessen()
        except Exception:  # noqa: BLE001 - beim Entladen nie hart scheitern
            _LOGGER.debug("Modbus-Verbindung liess sich nicht schliessen", exc_info=True)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
