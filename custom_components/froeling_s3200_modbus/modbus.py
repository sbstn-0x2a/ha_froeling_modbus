"""Modbus-Zugriffe der Integration.

Vorher über die Plattformmodule verteilt: _read_holding_sync sechsfach,
_write_register_sync vierfach, _read_input_sync und _ensure_connected je
dreifach. Danach lagen sie zwar hier zusammen, aber immer noch als fünf
nahezu gleiche Fassungen -- und alle fünf hatten dieselbe Lücke in der
Fehlerbehandlung. Jetzt führt ``_ausfuehren`` den Aufruf für alle durch.

Grundsatz: Jede Funktion gibt ``(Antwort, None)`` oder ``(None, Fehlertext)``
zurück und wirft nichts. Der Coordinator entscheidet daraus, ob ein Block
seine letzten Werte behält oder die Anlage als nicht erreichbar gilt. Eine
durchgereichte Ausnahme würde stattdessen im Protokoll von Home Assistant als
vollständiger Traceback landen.

Alle Funktionen sind blockierend und gehören in den Executor.
"""

from __future__ import annotations

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

#: Beide Aufrufarten wurden mit TypeError abgelehnt. Der Aufrufer darf dann
#: einen eigenen Rückfallpfad versuchen -- der Schreibhelfer tut das.
UNBEKANNTE_SIGNATUR = "unbekannte_signatur"


def _antwort(res, kennzeichen: str):
    """Eine Antwort der Gegenstelle -- die kann selbst einen Fehler melden."""
    if hasattr(res, "isError") and res.isError():
        # Etwa Illegal Data Address: Die Verbindung steht, das Register nicht.
        # Der Socket bleibt deshalb bewusst offen.
        return None, f"error({kennzeichen})"
    return res, None


def _verbindung_verloren(client, fehlertext: str):
    """Socket schliessen, damit der naechste Durchlauf neu verbindet."""
    try:
        client.close()
    except Exception:  # noqa: BLE001 - beim Aufräumen ist alles egal
        pass
    return None, fehlertext


def _ausfuehren(client, aufruf, unit_id: int, *args, **kwargs):
    """Ruft eine pymodbus-Methode auf und übersetzt jeden Fehler in Text.

    pymodbus meldet einen Verbindungsabbruch als ``ConnectionException``. Die
    erbt von ``ModbusException``, **nicht** von ``OSError`` -- ein
    ``except BrokenPipeError`` allein fängt sie also nicht. Genau daran lag es,
    dass ein Abbruch als Traceback im Fehlerprotokoll stand statt als Meldung.
    """
    if not client.connect():
        return None, "connect"
    try:
        return _antwort(aufruf(*args, device_id=unit_id, **kwargs), "device_id")
    except TypeError:
        pass  # ältere pymodbus-Fassungen kennen device_id nicht
    except (BrokenPipeError, ConnectionResetError):
        return _verbindung_verloren(client, "broken_pipe")
    except ModbusException as e:
        return _verbindung_verloren(client, f"modbus:{e}")
    except Exception as e:  # noqa: BLE001 - nichts darf den Executor verlassen
        return _verbindung_verloren(client, f"exc:{e}")

    try:
        return _antwort(aufruf(*args, unit=unit_id, **kwargs), "unit")
    except TypeError:
        return None, UNBEKANNTE_SIGNATUR
    except Exception as e:  # noqa: BLE001
        return _verbindung_verloren(client, f"exc:{e}")


def read_input_sync(client, unit_id: int, addr: int, count: int):
    """FC=04: Input-Register (3xxxx). addr ist 0-basiert."""
    return _ausfuehren(client, client.read_input_registers, unit_id, addr, count=count)


def read_holding_sync(client, unit_id: int, addr: int, count: int):
    """FC=03: Holding-Register (4xxxx). addr ist 0-basiert."""
    return _ausfuehren(client, client.read_holding_registers, unit_id, addr, count=count)


def read_coils_sync(client, unit_id: int, addr: int, count: int):
    """FC=01: Coils. addr wird so verwendet, wie übergeben (kein Offset-Abzug!)."""
    return _ausfuehren(client, client.read_coils, unit_id, addr, count=count)


def read_discrete_sync(client, unit_id: int, addr: int, count: int):
    """FC=02: Discrete Inputs (1xxxx). addr ist 0-basiert (10001 -> 0)."""
    return _ausfuehren(client, client.read_discrete_inputs, unit_id, addr, count=count)


def write_register_sync(client: ModbusTcpClient, unit_id: int, addr: int, value: int):
    """FC=06: Write Single Holding Register (4xxxx).

    Kennt einen dritten Rückfallpfad über ``client.unit_id``, den die
    Lesefunktionen nicht brauchen -- er stammt aus der Fassung in number.py.
    """
    res, err = _ausfuehren(client, client.write_register, unit_id, addr, value)
    if err != UNBEKANNTE_SIGNATUR:
        return res, err
    try:
        client.unit_id = unit_id
        return _antwort(client.write_register(addr, value), "client.unit_id")
    except Exception as e:  # noqa: BLE001
        return _verbindung_verloren(client, f"exc:{e}")
