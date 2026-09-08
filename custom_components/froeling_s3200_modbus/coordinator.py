"""Zentrales Abrufen aller Registerwerte.

Vorher hielt jede Entität ihren eigenen Timer und las genau ein Register pro
Zyklus, serialisiert über einen gemeinsamen Lock. Bei rund 175 Entitäten waren
das ebenso viele Timer und 143 einzelne Modbus-Anfragen je Durchlauf. Fiel die
Verbindung aus, lief jede dieser Anfragen in ihren Timeout, während der nächste
Zyklus bereits nachrückte -- die Warteschlange am Lock wuchs unbegrenzt.

Jetzt liest ein Coordinator alle Register in 19 Blöcken und verteilt die Werte
an die Entitäten. Überzieht ein Durchlauf das Intervall, überspringt Home
Assistant den nächsten, statt ihn aufzustauen.
"""

from __future__ import annotations

import logging
from datetime import timedelta

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

    async def _async_update_data(self) -> dict[int, int]:
        werte: dict[int, int] = {}
        for basis, bloecke, lese in (
            (INPUT_BASE, INPUT_BLOCKS, read_input_sync),
            (HOLDING_BASE, HOLDING_BLOCKS, read_holding_sync),
        ):
            for start, anzahl in bloecke:
                res, err = await self.hass.async_add_executor_job(
                    lese, self._client, self._unit_id, start - basis, anzahl
                )
                if err or res is None or not hasattr(res, "registers"):
                    raise UpdateFailed(
                        f"Block ab {start} ({anzahl} Register) nicht lesbar: {err}"
                    )
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
                    raise UpdateFailed(
                        f"Bitblock ab {start} ({anzahl} Bits) nicht lesbar: {err}"
                    )
                # bits ist auf ganze Bytes aufgefuellt, deshalb abschneiden.
                for versatz, bit in enumerate(res.bits[:anzahl]):
                    werte[start + versatz] = int(bit)

        _LOGGER.debug(
            "%d Werte in %d Anfragen gelesen",
            len(werte),
            len(INPUT_BLOCKS) + len(HOLDING_BLOCKS)
            + len(COIL_BLOCKS) + len(DISCRETE_BLOCKS),
        )
        return werte

    def rohwert(self, register: int) -> int | None:
        """Rohwert eines Registers, oder None wenn der Block fehlt."""
        if self.data is None:
            return None
        return self.data.get(register)

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
