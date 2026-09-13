# Froeling S3200 Modbus

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

🇬🇧 English | 🇩🇪 [Deutsch](README_de.md)

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

The register map is fixed to that layout. Other models use different addresses — the P5 / Lambdatronic P3200 for instance shifts them by an offset of 1000, and the S3100 differs as well. Such a device will connect, but the values will belong to the wrong quantities. Solar modules are not covered.

If your plant differs, please open an issue with the model designation rather than relying on the readings.

Heating circuits 03 to 18, DHW tanks 02 to 08 and buffers 02 to 04 get the same entities as heating circuit 02, DHW tank 01 and buffer 01. They are only offered in the dialog when the plant scan reports them as present (or they are already ticked), so a plant with two heating circuits does not see thirty tick boxes.

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

1. Go to **Settings → Devices & Services**, open **Froeling S3200 Modbus**, then use the three-dot menu on the entry and choose **Delete**.
   This removes the config entry together with all its devices and entities.
2. If the integration was installed through HACS: **HACS → Integrations → Froeling S3200 Modbus → three-dot menu → Remove**.
3. For a manual installation, delete the folder
   `config/custom_components/froeling_s3200_modbus`.
4. Restart Home Assistant.

Recorded history and long-term statistics are kept until the recorder purges them. Nothing is written to the boiler during removal.

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
5. **Confirm plant parts:** the boxes are pre-filled from the scan, each with its evidence (e.g. "Heating circuit 02: 30.5 °C, mode Automatic"). Parts that were not detected are under "show further parts". Below that you choose what happens to registers without a usable value: create disabled (default), do not create, create normally.
6. **Remote control:** a checkbox, off by default. Switched on, it creates the device "Remote control" with the select "Control" and the setpoints of all heating circuits and DHW tanks, see the section on boiler remote control.

Later via **Options**: change connection and interval, show or hide plant parts, switch remote control on or off, remove individual entities or create them despite detection, align entity IDs with the scheme, or re-scan the plant. Deselecting a part removes its entities together with their history; a re-scan therefore never proposes deselecting by itself.

---

## 🔄 Upgrading from 0.3.x or 0.4.0

An upgrade leaves existing entities alone: every entity keeps its `entity_id`, history and statistics. In addition, the new customer-level entities and the "Messages" sensor are created for the plant parts already selected, with `entity_id`s following the new scheme (`sensor.froeling_kessel_…`). Both schemes then coexist; the integration deliberately does not rename existing entities because automations, scripts and dashboards would not follow. If you want to migrate, rename entities in Home Assistant; history and statistics follow automatically.

The electrostatic precipitator and the detection of registers without a usable value only arrive with **Options → Re-scan the plant**. A notice under *Repairs* reminds you. There you also choose whether such registers are created disabled (history kept), removed (history lost) or left as they are.

Re-scanning pays off again later: it judges afresh every time. If a previously useless register now delivers values, e.g. a counter that has started counting, its entity is re-enabled or created again; conversely, a register newly found useless is disabled. Entities you disabled yourself are left alone, and a useless-rated entity you enabled by hand stays enabled on the next re-scan (it is kept automatically; see the option "Create despite detection"). Counters only count as useless after 24 operating hours of the plant, so a freshly commissioned plant is not judged prematurely.

**Plant name:** the name given during setup is part of every entity's `unique_id` and therefore cannot be changed afterwards; a different name would be a new plant without history to Home Assistant. To change the label, rename the controller device under *Settings → Devices*; all entity display names follow immediately, history and statistics are kept.

---

## ⚙️ Modbus Address / Unit ID Settings

For proper communication between Home Assistant and the Fröling controller, the **Modbus Unit ID** values must match.

The **Unit ID** is set directly on the heating controller:

```
System → Settings → General Settings → MODBUS Settings → MODBUS Address
```

You can choose any value between **1 and 247**. Use the same value in the integration’s **“Unit ID”** (or **“Unit Number”**) field. Both values must match for data to be read or written correctly.

> **Important:**  
> If the addresses do not match, no data will be received and no commands will be executed.  
> Each Modbus controller on the network must also have a **unique address** to avoid conflicts.

**Recommended default settings on the Fröling device:**
- Enable COM 2 as Modbus interface → **YES**  
- Modbus protocol: **RTU (1)**  
- Use Modbus Protocol 2014 → **YES**

> **Writing needs the 2014 protocol.**  
> Without it the boiler still answers read requests: the connection test during setup succeeds and all sensors show values. Only writing fails, with *Illegal Function* — number, switch, select and time entities silently stay at their old value. If changes made in Home Assistant never reach the boiler, check this setting first.

These options are also located in:  
`System → Settings → General Settings → MODBUS Settings`.

---

## 🔁 Boiler remote control (registers 48001–48046)

Besides the ordinary parameters the controller offers an **external setpoint mode** (manual B1200522 chapter 2.6): flow setpoint and enable flag per heating circuit, setpoint per DHW tank. Since 0.6.0 the integration implements it, including the heartbeat it requires, as a separate plant part "Remote control", off by default.

It is meant for a supervisory controller: DHW charging on demand instead of by schedule, or a room thermostat in Home Assistant that sets the flow temperature to the degree. If you only want to set back a circuit or change the DHW temperature permanently, stay with the **operating mode** and the ordinary parameters; they act permanently and need no heartbeat.

### What the controller does

Measured on the device (SP Dual Compact, 2026-09-09):

| Controller behaviour | Consequence |
|---|---|
| A single write to any of these registers activates the external setpoints **for all existing heating circuits and DHW tanks**, effective after one second. | There is no "DHW only": the other registers take effect with whatever they hold. |
| Without another write the controller falls back to its own regulation after **two minutes** (measured 54 to 129 s). | Keeping the setpoints alive means writing cyclically. The integration does so every 60 s. |
| A **switching change** (enable on/off, DHW setpoint 0 ↔ above 0) is accepted at the earliest **ten minutes** after the previous one. Otherwise the controller answers 0xFFFF, discards the value and still keeps the external mode alive. | There is no switching off within the lock. Plain value changes (56 → 58 °C) are accepted at any time. |
| Enable 1 with setpoint 0: the controller's heating curve, but **without the outdoor temperature heating limit**. Setpoint above 0: used directly as flow setpoint. Enable 0: circuit off, frost protection and safety pump run remain. | With setpoint 0 a circuit heats by its curve even in summer. |
| DHW setpoint 0: charging off. Above 0: charging up to this value, starting at `setpoint − (Desired temperature − Recharge when temperature below)`. | A DHW setpoint above the current tank temperature starts a charge, like the cloud's "extra charge". |
| The operating mode (48047 ff.) is independent of all this and permanent. | The "Operating mode" select stays as it is. |

### How to use it

1. **Switch it on:** tick "Remote control" in the step of the same name during setup, or later under **Options → Remote control**. This creates the device **"Remote control"** below the controller, which holds everything on this topic: the select "Control", the binary sensor "Remote control active" and, per existing heating circuit, "Heating circuit 0n flow setpoint" and "Heating circuit 0n enable", per DHW tank "DHW 0n setpoint". Without a scan of the plant only the ticked plant parts count as existing.
2. Set the select **"Control"** to **"Home Assistant"**. The integration writes a complete set immediately and then every 60 s. At **"Boiler controller"** (default) it writes nothing.
3. Set the **setpoint entities** in the device "Remote control". With control at Home Assistant every change is sent immediately, switching changes subject to the ten-minute rule. With control at the boiler it is only stored and sent when you switch on.
4. The binary sensor **"Remote control active"** shows whether the setpoints are in effect: on when control is at Home Assistant and the last successful set is younger than two minutes. If success stays away it turns off and the log warns.
5. Back to **"Boiler controller"**: the integration stops writing and the controller takes over within two minutes. "Enable 0" is never pushed afterwards.

**With control at Home Assistant, Home Assistant takes over the setpoints of all heating circuits and DHW tanks**, not only the ones you set. Every instance without a setpoint gets a neutral value: heating circuit enable on and setpoint 0 (heating curve without heating limit), DHW tank the value of "Desired temperature" (41632). The attribute `neutral` on the entity shows that no setpoint is set, `register_wert` the value the controller last accepted.

**Switched off** there are no remote control entities, no heartbeat, and registers 48001–48046 are not read. The operating mode of the heating circuits is untouched. The five entities from 0.4.0/0.5.0 ("… (remote control)" under heating circuit 01/02 and DHW 01) now live in the device "Remote control" under new names; `unique_id`, `entity_id` and history remain.

### Constraints

* **Ten minutes** between two switching changes. Until then the integration keeps sending the old state and lists the new one in the select's attribute `ausstehend`; a write that is discarded anyway counts in `verworfen`.
* **Two minutes** without a successful set and the controller regulates on its own. Home Assistant notices this on the binary sensor and on the attribute `fenster_ueberschritten`.
* **After a restart** of Home Assistant the control is always at the boiler. The setpoints are kept; an automation has to switch control back on itself.
* **The operating mode stays independent.** Whether a circuit with operating mode "Off" and enable 1 runs has not been tested on the device, nor whether a DHW setpoint starts the boiler in system state "domestic hot water".

### Example: DHW charging on demand

Charges the tank to 65 °C as soon as the top temperature drops below 47 °C and hands control back to the boiler once 65 °C is reached. Charging starts as soon as the tank temperature is below `65 − (Desired temperature − Recharge when temperature below)`; with factory values that is well above 47 °C.

The `entity_id`s follow the scheme of new installations with the plant name `froeling`; new remote control entities are named `number.froeling_fernsteuerung_<key>`. The five entities from 0.4.0/0.5.0 keep their previous ID, in an existing installation for example `number.froeling_boiler01_solltemperatur_modbus` or, from 0.3.x, `number.boiler_1_solltemperatur_modbus`.

```yaml
automation:
  - alias: "Charge DHW when cold"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.froeling_boiler01_temperatur_oben
        below: 47
    actions:
      - action: number.set_value
        target:
          entity_id: number.froeling_boiler01_solltemperatur_modbus
        data:
          value: 65
      - action: select.select_option
        target:
          entity_id: select.froeling_fernsteuerung_regelung
        data:
          option: home_assistant

  - alias: "DHW charged, control back to the boiler"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.froeling_boiler01_temperatur_oben
        above: 64.5
    conditions:
      - condition: state
        entity_id: select.froeling_fernsteuerung_regelung
        state: home_assistant
    actions:
      - action: select.select_option
        target:
          entity_id: select.froeling_fernsteuerung_regelung
        data:
          option: kessel
```

As long as control is at Home Assistant the heating circuits run with their setpoint entities, i.e. without a setpoint by heating curve without heating limit. If you do not want that in summer, switch "Heating circuit 0n enable" off beforehand.

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

The Fröling manuals and the Modbus register list live in the [`documentation/`](documentation/) folder of this repository. They are deliberately kept **outside** `custom_components/`, so HACS does not copy roughly 33 MB of PDFs into every Home Assistant configuration directory. The integration does not read these files at runtime — they are reference material only.
`documentation/Modbus_Register.txt` lists the registers used by this integration together with their entity type.

---

## 🖼️ Screenshots

<img width="500" height="618" alt="image" src="https://github.com/user-attachments/assets/6ffe643d-9679-4c69-90a0-10cdbadef477" />

---

## 🤝 Contributing

Pull requests, issues, and suggestions for improvement are always welcome!

---
