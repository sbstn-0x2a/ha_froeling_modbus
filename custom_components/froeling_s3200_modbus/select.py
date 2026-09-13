"""Auswahlentitäten aus der Registertabelle (Holding-Register mit Werteliste)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .device import tr_key as _tr_key
from .entitaeten import zeilen_der_plattform
from .entity import FroelingEntity, FroelingRegisterEntity
from .fernsteuerung import MASTER_HA, MASTER_KESSEL, MASTER_OPTIONEN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# ------------------------ Option-Definitionen (Codes → Keys) ----------------
# Die Übersetzungsschlüssel je Werteliste. Die Anzeigetexte stehen in
# translations/*.json unter entity.select.<entity>.state.<key>; die
# deutschen Texte der Doku dienen als Rückfall.
HK_MODE_CODE_TO_KEY = {0: "off", 1: "auto", 2: "extra", 3: "eco", 4: "eco_permanent", 5: "party"}
FUEL_CODE_TO_KEY = {0: "softwood", 1: "hardwood"}

DEFAULT_LABELS = {
    "hk_mode": {
        "off": "Aus",
        "auto": "Automatik",
        "extra": "Extraheizen",
        "eco": "Absenken",
        "eco_permanent": "Dauerabsenken",
        "party": "Partybetrieb",
    },
    # Laut Bedienungsanleitung B1460922 (SP 3200): 0 = Scheitholz trocken
    # (Wassergehalt < 15 %), 1 = Scheitholz feucht. Am Geraet gegengeprueft:
    # Register 0, Display "Scheitholz trocken"; die Kundenebene bietet am
    # Display genau diese zwei Optionen (Nutzer, 13.09.2026). Die Schluessel bleiben, damit
    # bestehende Automationen weiterlaufen.
    "fuel": {
        "softwood": "Scheitholz trocken",
        "hardwood": "Scheitholz feucht",
    },
}

#: Werteliste der Registertabelle -> (Übersetzungsgruppe, Code -> Key)
OPTIONEN = {
    "betriebsart": ("hk_mode", HK_MODE_CODE_TO_KEY),
    "brennstoffauswahl": ("fuel", FUEL_CODE_TO_KEY),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    laufzeit = config_entry.runtime_data
    coordinator = laufzeit.coordinator
    data = laufzeit.konfiguration

    # Übersetzungen: nur der erlaubte "entity"-Namespace
    translations = await async_get_translations(hass, hass.config.language, "entity")

    entities = [
        RegisterSelect(coordinator, translations, data, zeile)
        for zeile in zeilen_der_plattform(data, "select")
        if zeile.werteliste in OPTIONEN
    ]
    if laufzeit.fernsteuerung is not None and laufzeit.fernsteuerung.zeilen:
        # Ohne Fernsteuerzeile im Satz (kein Heizkreis, kein Boiler) gaebe es
        # nichts zu senden -- dann auch keine Auswahl.
        entities.append(FernsteuerRegelungSelect(coordinator, data, laufzeit.fernsteuerung))
    async_add_entities(entities)


class RegisterSelect(FroelingRegisterEntity, SelectEntity):
    """Auswahl auf einem Holding-Register.

    Optionen und aktuelle Auswahl werden aus dem Rohwert abgeleitet. Ein Wert,
    der in der Tabelle fehlt, erscheint als dynamische Option "Wert <n>" --
    sonst liesse sich der Zustand der Anlage nicht anzeigen.
    """

    _plattform = "select"

    def __init__(self, coordinator, translations, data, zeile) -> None:
        super().__init__(coordinator, data, zeile)
        self._translations = translations
        self._group_key, code_to_key = OPTIONEN[zeile.werteliste]
        self._code_to_key = dict(code_to_key)
        self._key_to_code = {v: k for k, v in code_to_key.items()}
        self._option_keys = list(self._key_to_code.keys())
        # Gilt nach einer Auswahl, bis der Coordinator neu gelesen hat.
        self._optimistisch: int | None = None

    def _label_for_key(self, opt_key: str) -> str:
        entity_key = _tr_key(self._entity_id)
        return self._translations.get(
            f"component.{DOMAIN}.entity.select.{entity_key}.state.{opt_key}",
            DEFAULT_LABELS.get(self._group_key, {}).get(opt_key, opt_key),
        )

    @property
    def _rohwert(self) -> int | None:
        if self._optimistisch is not None:
            return self._optimistisch
        return self.coordinator.rohwert(self._register)

    @property
    def options(self) -> list[str]:
        bekannt = [self._label_for_key(k) for k in self._option_keys]
        roh = self._rohwert
        if roh is not None and roh not in self._code_to_key:
            bekannt.append(f"Wert {roh}")
        return bekannt

    @property
    def current_option(self) -> str | None:
        roh = self._rohwert
        if roh is None:
            return None
        schluessel = self._code_to_key.get(roh)
        return self._label_for_key(schluessel) if schluessel else f"Wert {roh}"

    def _handle_coordinator_update(self) -> None:
        if self._frisch_gelesen():
            self._optimistisch = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str):
        code = None
        for k in self._option_keys:
            if self._label_for_key(k) == option:
                code = int(self._key_to_code[k])
                break
        if code is None and option.startswith("Wert "):
            try:
                code = int(option.split(" ", 1)[1])
            except ValueError:
                code = None
        if code is None:
            _LOGGER.error("Unbekannte Option %r für %s", option, self._entity_id)
            return
        await self._schreiben(code)
        self._optimistisch = code
        self.async_write_ha_state()


class FernsteuerRegelungSelect(FroelingEntity, SelectEntity, RestoreEntity):
    """Wer regelt Heizkreise und Boiler: der Kessel oder Home Assistant.

    Haengt am Geraet "Fernsteuerung" unter dem Regler, zusammen mit dem
    Binaersensor und den Vorgabe-Entitaeten aller Instanzen.

    "Home Assistant" startet den Heartbeat der Kesselfernsteuerung (alle 60 s
    der vollstaendige Satz 48001-48046 der vorhandenen Instanzen), "Kessel"
    beendet ihn -- die Anlage faellt dann von selbst nach zwei Minuten in
    ihre eigene Regelung zurueck. Eine Auswahl statt eines Schalters, weil
    "Fernsteuerung an/aus" in der Oberflaeche nicht sagt, wer dann regelt.

    RestoreEntity nur zur Diagnose: Nach einem Neustart steht die Auswahl
    immer auf "Kessel". Waehrend des Neustarts hat die Anlage laengst
    uebernommen, und Home Assistant soll die Vorgabe nicht kommentarlos
    reaktivieren (Befund vom 09.09.2026, Auflage 7b Punkte 6, 7 und 11).
    """

    _plattform = "select"
    _attr_options = list(MASTER_OPTIONEN)

    def __init__(self, coordinator, data, fernsteuerung) -> None:
        super().__init__(coordinator, data, "fernsteuerung_regelung", "fernsteuerung")
        self._fernsteuerung = fernsteuerung

    @property
    def available(self) -> bool:
        # Immer bedienbar: Gerade ohne Verbindung muss man auf "Kessel"
        # zurueckstellen koennen, damit HA nach Rueckkehr des Netzes nicht
        # weiter sendet.
        return True

    @property
    def current_option(self) -> str:
        return self._fernsteuerung.master

    @property
    def extra_state_attributes(self):
        return self._fernsteuerung.attribute()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        letzter = await self.async_get_last_state()
        if letzter is not None and letzter.state == MASTER_HA:
            _LOGGER.warning(
                "Fernsteuerung: vor dem Neustart oder Neuladen regelte Home Assistant; "
                "jetzt steht die Auswahl auf \"Kessel\", die Anlage regelt selbst. Bei "
                "Bedarf erneut auf \"Home Assistant\" stellen."
            )
        self.async_on_remove(self._fernsteuerung.zuhoerer_hinzufuegen(self.async_write_ha_state))

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option == MASTER_HA:
            await self._fernsteuerung.async_start()
        elif option == MASTER_KESSEL:
            await self._fernsteuerung.async_stop()
        else:
            _LOGGER.error("Unbekannte Option %r für %s", option, self._entity_id)
            return
        self.async_write_ha_state()
