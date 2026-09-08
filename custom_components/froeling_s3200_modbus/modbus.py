"""Modbus-Zugriffe der Integration.

Vorher über die Plattformmodule verteilt: _read_holding_sync sechsfach,
_write_register_sync vierfach, _read_input_sync und _ensure_connected je
dreifach. Übernommen wurde jeweils die vollständigste Fassung -- beim
Schreibhelfer die aus number.py, die einen zusätzlichen Rückfallpfad über
client.unit_id kennt.

Alle Funktionen sind blockierend und gehören in den Executor.
"""

from __future__ import annotations

from pymodbus.client import ModbusTcpClient


def read_input_sync(client, unit_id: int, addr: int, count: int):
    if not client.connect():
        return None, "connect"
    # 1) Bevorzugt: device_id
    try:
        res = client.read_input_registers(addr, count=count, device_id=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(device_id)"
        return res, None
    except TypeError:
        pass
    except (BrokenPipeError, ConnectionResetError):
        try:
            client.close()
        except Exception:
            pass
        return None, "broken_pipe"
    # 2) Fallback: unit
    try:
        res = client.read_input_registers(addr, count=count, unit=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(unit)"
        return res, None
    except Exception as e:
        return None, f"exc:{e}"

def read_holding_sync(client, unit_id: int, addr: int, count: int):
    if not client.connect():
        return None, "connect"
    try:
        res = client.read_holding_registers(addr, count=count, device_id=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(device_id)"
        return res, None
    except TypeError:
        pass
    except (BrokenPipeError, ConnectionResetError):
        try:
            client.close()
        except Exception:
            pass
        return None, "broken_pipe"
    try:
        res = client.read_holding_registers(addr, count=count, unit=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(unit)"
        return res, None
    except Exception as e:
        return None, f"exc:{e}"

def read_coils_sync(client, unit_id: int, addr: int, count: int):
    """FC=01: Coils. addr wird so verwendet, wie übergeben (kein Offset-Abzug!)."""
    if not client.connect():
        return None, "connect"
    # 1) bevorzugt: device_id
    try:
        res = client.read_coils(addr, count=count, device_id=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(device_id)"
        return res, None
    except TypeError:
        pass
    except (BrokenPipeError, ConnectionResetError):
        try:
            client.close()
        except Exception:
            pass
        return None, "broken_pipe"
    # 2) fallback: unit
    try:
        res = client.read_coils(addr, count=count, unit=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(unit)"
        return res, None
    except Exception as e:
        return None, f"exc:{e}"

def read_discrete_sync(client, unit_id: int, addr: int, count: int):
    """FC=02: Discrete Inputs (1xxxx). addr ist 0-basiert (10001 -> 0)."""
    if not client.connect():
        return None, "connect"
    # 1) bevorzugt: device_id
    try:
        res = client.read_discrete_inputs(addr, count=count, device_id=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(device_id)"
        return res, None
    except TypeError:
        pass
    except (BrokenPipeError, ConnectionResetError):
        try:
            client.close()
        except Exception:
            pass
        return None, "broken_pipe"
    # 2) fallback: unit
    try:
        res = client.read_discrete_inputs(addr, count=count, unit=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(unit)"
        return res, None
    except Exception as e:
        return None, f"exc:{e}"

def write_register_sync(client: ModbusTcpClient, unit_id: int, addr: int, value: int):
    """FC=06: Write Single Holding Register (4xxxx)."""
    if not client.connect():
        return None, "connect"
    try:
        res = client.write_register(addr, value, device_id=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(device_id)"
        return res, None
    except TypeError:
        pass
    except (BrokenPipeError, ConnectionResetError):
        try:
            client.close()
        except Exception:
            pass
        return None, "broken_pipe"
    try:
        res = client.write_register(addr, value, unit=unit_id)
        if hasattr(res, "isError") and res.isError():
            return None, "error(unit)"
        return res, None
    except TypeError:
        pass
    try:
        client.unit_id = unit_id
        res = client.write_register(addr, value)
        if hasattr(res, "isError") and res.isError():
            return None, "error(client.unit_id)"
        return res, None
    except Exception as e:
        return None, f"exc:{e}"