"""Zentrales Abrufen aller Registerwerte.

Vorher hielt jede Entität ihren eigenen Timer und las genau ein Register pro
Zyklus, serialisiert über einen gemeinsamen Lock. Bei rund 175 Entitäten waren
das ebenso viele Timer und 143 einzelne Modbus-Anfragen je Durchlauf. Fiel die
Verbindung aus, lief jede dieser Anfragen in ihren Timeout, während der nächste
Zyklus bereits nachrückte -- die Warteschlange am Lock wuchs unbegrenzt.

Jetzt liest ein Coordinator alle Register in Blöcken und verteilt die Werte an
die Entitäten. Überzieht ein Durchlauf das Intervall, überspringt Home
Assistant den nächsten, statt ihn aufzustauen.

Ein einzelner fehlgeschlagener Block macht dabei nicht die ganze Anlage
unverfügbar. Vorher las jede Entität ihr Register selbst: Ein Aussetzer am
Gateway setzte genau diesen einen Wert auf ``unknown``, alle anderen liefen
weiter. Würde der Coordinator beim ersten Fehler abbrechen, gingen
stattdessen alle 177 Entitäten gleichzeitig auf ``unavailable`` -- und
Automationen, die auf einen Zustandswechsel lauschen, feuerten bei jedem
Netzwerkhusten. Deshalb behält ein fehlgeschlagener Block seine zuletzt
gelesenen Werte; erst nach ``MAX_BLOCKFEHLER`` Durchläufen in Folge gibt der
Coordinator ihn auf. Nur wenn kein einziger Block antwortet, ist die
Verbindung wirklich weg.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import ModbusTcpClient

from .const import DOMAIN
from .modbus import (
    read_coils_sync,
    read_discrete_sync,
    read_holding_sync,
    read_input_sync,
    write_register_sync,
)
from .registers import (
    COIL_BLOCKS,
    DISCRETE_BASE,
    DISCRETE_BLOCKS,
    HOLDING_BASE,
    HOLDING_BLOCKS,
    INPUT_BASE,
    INPUT_BLOCKS,
)

_LOGGER = logging.getLogger(__name__)

#: So oft darf ein Block hintereinander ausfallen, bevor seine Werte
#: verworfen werden und die betroffenen Entitäten "unknown" melden.
#: Drei Durchläufe sind bei 30 s Intervall anderthalb Minuten -- lang genug
#: für einen Aussetzer, kurz genug, um keine veralteten Werte zu zeigen.
MAX_BLOCKFEHLER = 3


@dataclass(slots=True)
class FroelingRuntimeData:
    """Was die Plattformen zur Laufzeit brauchen.

    Haengt am Config-Entry (``entry.runtime_data``) statt an Stringschluesseln
    in ``hass.data`` -- die waren fehleranfaellig und beim Entladen leicht zu
    uebersehen.
    """

    coordinator: "FroelingCoordinator"
    konfiguration: dict[str, Any]


class FroelingCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Liest alle genutzten Register blockweise.

    ``data`` ist eine Zuordnung Registernummer -> Rohwert. Input- (3xxxx) und
    Holding-Register (4xxxx) überschneiden sich zahlenmäßig nicht, deshalb
    genügt eine gemeinsame Tabelle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ModbusTcpClient,
        unit_id: int,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self._client = client
        self._unit_id = unit_id
        #: Fehlversuche in Folge je Block, Schlüssel ist die Startadresse.
        self._blockfehler: dict[int, int] = {}

    async def _async_update_data(self) -> dict[int, int]:
        vorher = self.data or {}
        werte: dict[int, int] = {}
        erfolge = 0
        gescheitert: list[str] = []

        def uebernehmen(start: int, anzahl: int, fehler: str) -> None:
            """Behält die zuletzt gelesenen Werte eines Blocks -- oder gibt ihn auf."""
            gescheitert.append(fehler)
            zaehler = self._blockfehler.get(start, 0) + 1
            self._blockfehler[start] = zaehler
            if zaehler > MAX_BLOCKFEHLER:
                return          # Werte verwerfen: Entitäten melden "unknown"
            for nummer in range(start, start + anzahl):
                if nummer in vorher:
                    werte[nummer] = vorher[nummer]

        for basis, bloecke, lese in (
            (INPUT_BASE, INPUT_BLOCKS, read_input_sync),
            (HOLDING_BASE, HOLDING_BLOCKS, read_holding_sync),
        ):
            for start, anzahl in bloecke:
                res, err = await self.hass.async_add_executor_job(
                    lese, self._client, self._unit_id, start - basis, anzahl
                )
                if err or res is None or not hasattr(res, "registers"):
                    uebernehmen(start, anzahl,
                                f"Block ab {start} ({anzahl} Register): {err}")
                    continue
                erfolge += 1
                self._blockfehler.pop(start, None)
                for versatz, rohwert in enumerate(res.registers):
                    werte[start + versatz] = rohwert

        # Coils (FC=01) werden direkt adressiert, Discrete Inputs (FC=02)
        # ueber ihre 1xxxx-Nummer. Beide liefern Bits statt Register.
        for basis, bloecke, lese in (
            (0, COIL_BLOCKS, read_coils_sync),
            (DISCRETE_BASE, DISCRETE_BLOCKS, read_discrete_sync),
        ):
            for start, anzahl in bloecke:
                res, err = await self.hass.async_add_executor_job(
                    lese, self._client, self._unit_id, start - basis, anzahl
                )
                if err or res is None or not hasattr(res, "bits"):
                    uebernehmen(start, anzahl,
                                f"Bitblock ab {start} ({anzahl} Bits): {err}")
                    continue
                erfolge += 1
                self._blockfehler.pop(start, None)
                # bits ist auf ganze Bytes aufgefuellt, deshalb abschneiden.
                for versatz, bit in enumerate(res.bits[:anzahl]):
                    werte[start + versatz] = int(bit)

        if erfolge == 0:
            # Kein einziger Block hat geantwortet -- die Verbindung ist weg.
            # Erst hier gehen die Entitaeten auf "unavailable".
            raise UpdateFailed("; ".join(gescheitert) or "keine Antwort von der Anlage")

        if gescheitert:
            _LOGGER.warning(
                "%d von %d Bloecken nicht lesbar, letzte Werte bleiben stehen: %s",
                len(gescheitert), erfolge + len(gescheitert), "; ".join(gescheitert),
            )
        else:
            _LOGGER.debug("%d Werte in %d Anfragen gelesen", len(werte), erfolge)
        return werte

    def rohwert(self, register: int) -> int | None:
        """Rohwert eines Registers, oder None wenn der Block fehlt."""
        if self.data is None:
            return None
        return self.data.get(register)

    def client_schliessen(self) -> None:
        """Schliesst die Modbus-Verbindung. Wird beim Entladen aufgerufen."""
        self._client.close()

    async def schreibe(self, register: int, rohwert: int) -> str | None:
        """Schreibt ein Holding-Register (FC=06).

        Bei Erfolg wird eine Aktualisierung angestossen, damit der neue Wert
        nicht bis zum naechsten regulaeren Durchlauf alt aussieht. Rueckgabe
        ist die Fehlermeldung oder None.
        """
        _, err = await self.hass.async_add_executor_job(
            write_register_sync,
            self._client,
            self._unit_id,
            register - HOLDING_BASE,
            rohwert,
        )
        if err:
            _LOGGER.error("Register %s nicht beschreibbar: %s", register, err)
            return err
        await self.async_request_refresh()
        return None
