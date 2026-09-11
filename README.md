# Froeling S3200 Modbus

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A **Home Assistant custom integration** for connecting a **Fröling Lambdatronic S3200** controller via **Modbus TCP**.  
It allows you to read states and sensor values of your heating system (boiler, heating circuits, buffer tank, discharge unit, etc.) directly in Home Assistant.

---

## ✨ Features

- Connection to the **Fröling S3200** via Modbus TCP  
- Reading of sensor values (e.g., temperatures, operating states)  
- Control of switches (e.g., pumps, heating circuits)  
- Detects during setup which plant parts exist and creates entities only
  for those
- Support for multiple system sections:
  - Boiler  
  - Heating circuit(s)  
  - Buffer tank  
  - Discharge unit  
  - Domestic hot water (DHW)  
  - Circulation pump
  - Electrostatic precipitator
- "Messages" sensor with the controller's pending fault texts
- Long-term statistics for all measurements and counters

---

## ⚠️ Supported equipment

Developed and tested against a **Fröling SP Dual Compact with Lambdatronic
S3200**, connected over Modbus TCP through an RS485 gateway.

The register map is fixed to that layout. Other models use different
addresses — the P5 / Lambdatronic P3200 for instance shifts them by an offset
of 1000, and the S3100 differs as well. Such a device will connect, but the
values will belong to the wrong quantities. More than two heating circuits and
solar modules are not covered either.

If your plant differs, please open an issue with the model designation rather
than relying on the readings.

Not covered yet: heating circuits from 03, DHW tanks from 02 and buffers from
02 are detected but not created as entities.

---

## 📦 Installation

### Option 1 – via HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.  
2. Add this repository as a **Custom Repository**:  
   - HACS → Integrations → Repositories → “+” →  
     URL: `https://github.com/sbstn-0x2a/ha_froeling_modbus`  
     Category: `Integration`  
3. The integration will then appear in HACS and can be installed directly.

### Option 2 – Manual installation

1. Download the files from `custom_components/froeling_s3200_modbus`.  
2. Copy the folder `froeling_s3200_modbus` to:  
   ```
   config/custom_components/froeling_s3200_modbus
   ```
3. Restart Home Assistant.

---

## 🗑️ Removal

1. Go to **Settings → Devices & Services**, open **Froeling S3200 Modbus**,
   then use the three-dot menu on the entry and choose **Delete**.
   This removes the config entry together with all its devices and entities.
2. If the integration was installed through HACS: **HACS → Integrations →
   Froeling S3200 Modbus → three-dot menu → Remove**.
3. For a manual installation, delete the folder
   `config/custom_components/froeling_s3200_modbus`.
4. Restart Home Assistant.

Recorded history and long-term statistics are kept until the recorder purges
them. Nothing is written to the boiler during removal.

## ⚙️ Configuration

1. In Home Assistant go to:  
   **Settings → Devices & Services → Add Integration**  
2. Select **Froeling S3200 Modbus**.  
3. Enter the connection details:  
   - Hostname / IP address of the S3200  
   - Port (default: 502)  
   - Update interval (default: 30 s, allowed 15–3600 s)
   - Modbus UnitID (2)
4. The controller is read once completely (a few seconds).
5. **Confirm plant parts:** the boxes are pre-filled from the scan, each with
   its evidence (e.g. "Heating circuit 02: 30.5 °C, mode Automatic"). Parts
   that were not detected are under "show further parts". Below that you
   choose what happens to registers without a usable value: create disabled
   (default), do not create, create normally.

Later via **Options**: change connection and interval, show or hide plant
parts, or re-scan the plant. Deselecting a part removes its entities together
with their history; a re-scan therefore never proposes deselecting by itself.

---

## 🔄 Upgrading from 0.3.x or 0.4.0

An upgrade leaves existing entities alone: every entity keeps its
`entity_id`, history and statistics. In addition, the new customer-level
entities and the "Messages" sensor are created for the plant parts already
selected, with `entity_id`s following the new scheme
(`sensor.froeling_kessel_…`). Both schemes then coexist; the integration
deliberately does not rename existing entities because automations, scripts
and dashboards would not follow. If you want to migrate, rename entities in
Home Assistant; history and statistics follow automatically.

The electrostatic precipitator and the detection of registers without a
usable value only arrive with **Options → Re-scan the plant**. A notice under
*Repairs* reminds you. There you also choose whether such registers are
created disabled (history kept), removed (history lost) or left as they are.

Re-scanning pays off again later: it judges afresh every time. If a
previously useless register now delivers values, e.g. a counter that has
started counting, its entity is re-enabled or created again; conversely, a
register newly found useless is disabled. Entities you disabled yourself are
left alone. Counters only count as useless after 24 operating hours of the
plant, so a freshly commissioned plant is not judged prematurely.

**Plant name:** the name given during setup is part of every entity's
`unique_id` and therefore cannot be changed afterwards; a different name would
be a new plant without history to Home Assistant. To change the label, rename
the controller device under *Settings → Devices*; all entity display names
follow immediately, history and statistics are kept.

---

## ⚙️ Modbus Address / Unit ID Settings

For proper communication between Home Assistant and the Fröling controller, the **Modbus Unit ID** values must match.

The **Unit ID** is set directly on the heating controller:

```
System → Settings → General Settings → MODBUS Settings → MODBUS Address
```

You can choose any value between **1 and 247**.  
Use the same value in the integration’s **“Unit ID”** (or **“Unit Number”**) field.  
Both values must match for data to be read or written correctly.

> **Important:**  
> If the addresses do not match, no data will be received and no commands will be executed.  
> Each Modbus controller on the network must also have a **unique address** to avoid conflicts.

**Recommended default settings on the Fröling device:**
- Enable COM 2 as Modbus interface → **YES**  
- Modbus protocol: **RTU (1)**  
- Use Modbus Protocol 2014 → **YES**

> **Writing needs the 2014 protocol.**  
> Without it the boiler still answers read requests: the connection test
> during setup succeeds and all sensors show values. Only writing fails, with
> *Illegal Function* — number, switch, select and time entities silently stay
> at their old value. If changes made in Home Assistant never reach the
> boiler, check this setting first.

These options are also located in:  
`System → Settings → General Settings → MODBUS Settings`.

---

## 🔁 Boiler remote control (registers 48001–48046)

Besides the ordinary parameters the controller offers an **external setpoint
mode**: flow setpoint and enable flag per heating circuit plus the DHW
setpoint (registers 48001–48046). It behaves unlike anything else in this
integration, so the related entities ("Enable (remote control)", "Flow
setpoint (remote control)", "Setpoint (remote control)") are **disabled by
default**.

Measured on the device (SP Dual Compact, 2026-09-09):

* **A single write** to any of these registers activates the external
  setpoints **for all heating circuits and DHW tanks at once**, using whatever
  the other registers currently hold. Writing only the DHW setpoint also puts
  the heating circuits onto their remote values.
* If **more than two minutes** pass without another write, the controller
  falls back to its own regulation. The entity in Home Assistant keeps showing
  the written value anyway.
* Toggling again **within ten minutes** is rejected by the controller (the
  integration now reports that as an error) but still keeps the external mode
  alive for another two minutes.

For everyday needs (setback a circuit, change the DHW setpoint) the
**operating mode** and the ordinary parameters are the right tools; they act
permanently. A proper implementation with cyclic rewriting is planned as an
optional feature.

## 🌐 Translations

This integration includes full English translations for all configuration texts and entity names.  
You can find them in the `en.json` file under:

```
custom_components/froeling_s3200_modbus/translations/en.json
```

If your Home Assistant instance is set to English, all configuration dialogs and entities will automatically appear in English.

German translations are also available via `de.json`.

---

## 📚 Manufacturer documentation

The integration follows Fröling's Modbus description **B1200522** ("ModBus
Lambdatronic 3200", edition 05/2019). That document and the boiler manuals
(operating manual B1500624, installation manual M1821425, touch control unit
B1460922) are available for download from Fröling; they are not part of this
repository.

The attribute `register` of every entity shows which register it reads,
and `beschreibung` carries the name from the Modbus list.

---

## 🖼️ Screenshots

<img width="2010" height="1344" alt="2025-10-03_14-57-08" src="https://github.com/user-attachments/assets/ebbb796a-b0e1-4b06-b8c6-bd18caea4a31" />

---

## 🤝 Contributing

Pull requests, issues, and suggestions for improvement are always welcome!

---