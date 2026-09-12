from __future__ import annotations

import logging
import pymodbus
from pymodbus.client import ModbusTcpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import STANDARD_INTERVALL, eindeutige_kennung
from .coordinator import FroelingCoordinator, FroelingRuntimeData
from .device import device_info_for
from .entitaeten import (
    TOTE_DEAKTIVIERT,
    fernsteuerung_aktiv,
    tote_register,
    tote_umgang,
    zeilen_fuer,
    zeilen_zum_lesen,
)
from .fernsteuerung import Fernsteuerung, satz_zeilen
from .registertabelle import TABELLE

for name in ("pymodbus", "pymodbus.client", "pymodbus.transaction", "pymodbus.framer", "pymodbus.logging"):
    logging.getLogger(name).setLevel(logging.WARNING)

DOMAIN = "froeling_s3200_modbus"
_LOGGER = logging.getLogger(__name__)

#: Die Anlagenteile, die sich ein- und ausblenden lassen.
GRUPPEN = (
    "kessel",
    "boiler01",
    "hk01",
    "hk02",
    "austragung",
    "puffer01",
    "zirkulationspumpe",
    "efilter",
)


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


def _verwaiste_entfernen(hass: HomeAssistant, entry: ConfigEntry, data: dict) -> int:
    """Registry-Eintraege dieses Entry, fuer die keine Entitaet mehr entsteht.

    Entstehen z. B., wenn Register nach dem Neu-Einlesen auf "gar nicht
    anlegen" stehen oder sich eine Kennung beim Update geaendert hat. Ohne
    Aufraeumen bleiben sie dauerhaft als "nicht verfuegbar" stehen -- der
    Nutzer sah in der Testinstanz 254 statt 242 Entitaeten.
    """
    erwartet = {f"{data['name']}_{z.entitaetsschluessel}" for z in zeilen_fuer(data)}
    erwartet.add(f"{data['name']}_meldungen")
    if fernsteuerung_aktiv(data) and satz_zeilen(data):
        # Die beiden Entitaeten der Kesselfernsteuerung haben keine Zeile in
        # der Registertabelle; sie entstehen, sobald es einen Satz gibt. Ist
        # die Fernsteuerung aus, verschwinden sie und die Vorgabe-Entitaeten
        # hier -- gewollt, wie ein abgewaehltes Anlagenteil.
        erwartet.add(f"{data['name']}_fernsteuerung_regelung")
        erwartet.add(f"{data['name']}_fernsteuerung_aktiv")
    ent_reg = er.async_get(hass)
    weg = [e for e in ent_reg.entities.values()
           if e.config_entry_id == entry.entry_id and e.unique_id not in erwartet]
    for e in weg:
        ent_reg.async_remove(e.entity_id)
    if weg:
        _LOGGER.info("%d verwaiste Entitaet(en) entfernt: %s", len(weg),
                     ", ".join(e.entity_id for e in weg[:5]))
    # Geraete abgewaehlter Anlagenteile: alles, woran keine Entitaet mehr
    # haengt, ausser dem Regler. Vorher lief das ueber das Geraet der Gruppe
    # und riss Entitaeten anderer Gruppen mit, die dort bewusst einsortiert
    # sind (40601 und die Zirkulationspumpe unter Boiler 01) -- bei jedem
    # Neustart, samt Nutzeranpassungen.
    dev_reg = dr.async_get(hass)
    for geraet in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if (DOMAIN, f"{data['name']}:controller") in geraet.identifiers:
            continue
        if not er.async_entries_for_device(ent_reg, geraet.id, include_disabled_entities=True):
            dev_reg.async_remove_device(geraet.id)
    return len(weg)


def _tote_anwenden(hass: HomeAssistant, entry: ConfigEntry, data: dict) -> None:
    erkannt = data.get("erkannt") or {}
    zeit = erkannt.get("zeit")
    if not zeit or tote_umgang(data) != TOTE_DEAKTIVIERT or data.get("tot_angewendet") == zeit:
        return
    ent_reg = er.async_get(hass)
    vorhanden = {e.unique_id: e for e in ent_reg.entities.values()
                 if e.config_entry_id == entry.entry_id}
    tot = tote_register(data)
    aus = an = 0
    for zeile in zeilen_fuer(data):
        eintrag = vorhanden.get(f"{data['name']}_{zeile.entitaetsschluessel}")
        if eintrag is None or zeile.kategorie == "fernsteuerung":
            # Fernsteuerregister sind Vorgabewerte in HA, keine Messwerte der
            # Anlage -- ein Befund "wertlos" sagt ueber sie nichts aus.
            continue
        if zeile.nummer in tot and eintrag.disabled_by is None:
            ent_reg.async_update_entity(
                eintrag.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )
            aus += 1
        elif zeile.nummer not in tot and eintrag.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            # Frueher wertlos, jetzt nicht mehr (ein Zaehler hat begonnen zu
            # zaehlen): wieder einschalten. Vom Nutzer Deaktiviertes bleibt aus.
            ent_reg.async_update_entity(eintrag.entity_id, disabled_by=None)
            an += 1
    if aus or an:
        _LOGGER.info("Befund angewendet: %d Entitaet(en) deaktiviert, %d wieder aktiviert", aus, an)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "tot_angewendet": zeit})


async def _neu_laden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


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
        kennung = eindeutige_kennung(data["host"], data.get("port", 502), data["unit_id"])
        andere = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, kennung)
        if andere is None:
            hass.config_entries.async_update_entry(entry, unique_id=kennung)
        else:
            # Zwei Alt-Eintraege fuer dieselbe Anlage: Vor 0.4.0 war das
            # moeglich. Der zweite bleibt ohne Kennung, statt eine doppelte
            # zu bekommen -- HA lehnt das ab.
            _LOGGER.warning(
                "Eintrag %s nutzt dieselbe Anlage wie %s (%s); bitte einen der beiden entfernen",
                entry.title, andere.title, kennung,
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
    # Kein client.connect() hier: Das waere ein blockierender Socket-Aufbau im
    # Event-Loop. Die Lesefunktionen verbinden im Executor bei Bedarf selbst.

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
        hass, entry, client, data["unit_id"], data.get("update_interval", STANDARD_INTERVALL),
        zeilen=zeilen_zum_lesen(data),
    )
    await coordinator.async_refresh()
    # Das Reglergeraet zuerst anlegen: Untergeraete haengen sich seit
    # HA 2026.9 ueber dessen Registry-id darunter, und die gibt es nur, wenn
    # das Geraet schon existiert. Vorher entstand es beiläufig mit der ersten
    # Entitaet -- die Reihenfolge war damit dem Zufall ueberlassen.
    regler = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **device_info_for("controller", data["name"], DOMAIN),
    )
    coordinator.regler_id = regler.id

    # Kesselfernsteuerung, nur wenn eingeschaltet: haelt die Vorgaben und den
    # Heartbeat. Beim Entladen endet der Timer -- danach schreibt nichts mehr,
    # und die Anlage regelt nach zwei Minuten wieder selbst (B1200522
    # Kap. 2.6, gemessen 09.09.2026). Abgemeldet wird sie in
    # async_unload_entry als Erstes -- nicht ueber entry.async_on_unload, das
    # erst nach dem Schliessen des Clients laeuft.
    fernsteuerung = Fernsteuerung(hass, coordinator, data) if fernsteuerung_aktiv(data) else None

    entry.runtime_data = FroelingRuntimeData(coordinator, data, fernsteuerung)

    # Bestandsinstallationen wurden nie eingelesen: Hinweis in "Reparaturen",
    # der in den Options-Flow fuehrt. Es wird nichts automatisch abgewaehlt.
    kennung = f"anlage_einlesen_{entry.entry_id}"
    if "erkannt" in data:
        ir.async_delete_issue(hass, DOMAIN, kennung)
    else:
        ir.async_create_issue(
            hass, DOMAIN, kennung,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="anlage_einlesen",
            translation_placeholders={"name": data["name"]},
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register ohne brauchbaren Wert einmal deaktivieren. Bei einer frischen
    # Einrichtung entstehen sie ohnehin deaktiviert; Home Assistant stellt
    # aber geloeschte Registry-Eintraege samt altem Zustand wieder her, und
    # beim Neu-Einlesen existieren sie laengst. Deshalb hier, genau einmal je
    # Befund (Zeitstempel), und vor dem Update-Listener -- sonst loest das
    # Schreiben in entry.data einen Reload aus.
    _tote_anwenden(hass, entry, data)
    _verwaiste_entfernen(hass, entry, data)

    # Optionen geaendert -> neu laden. Das Aufraeumen abgewaehlter Teile
    # erledigt das Setup selbst (_verwaiste_entfernen).
    entry.async_on_unload(entry.add_update_listener(_neu_laden))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and close the client."""
    laufzeit: FroelingRuntimeData | None = getattr(entry, "runtime_data", None)
    # Zuerst den Heartbeat der Fernsteuerung beenden. Liefe er weiter, bis
    # entry.async_on_unload dran ist, laege das *nach* async_schliessen():
    # Ein Timer in diesem Fenster oeffnete den Socket neu und schriebe die
    # Vorgabe noch einmal -- zwei Minuten Fernsteuerung nach dem Entladen.
    if laufzeit is not None and laufzeit.fernsteuerung is not None:
        laufzeit.fernsteuerung.abmelden()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if laufzeit is not None:
        try:
            await laufzeit.coordinator.async_schliessen()
        except Exception:  # noqa: BLE001 - beim Entladen nie hart scheitern
            _LOGGER.debug("Modbus-Verbindung liess sich nicht schliessen", exc_info=True)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
