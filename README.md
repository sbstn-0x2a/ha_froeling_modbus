# Froeling S3200 Modbus

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A **Home Assistant custom integration** for connecting a **Fröling Lambdatronic S3200** controller via **Modbus TCP**.  
It allows you to read states and sensor values of your heating system (boiler, heating circuits, buffer tank, discharge unit, etc.) directly in Home Assistant.

---

## ✨ Features

- Connection to the **Fröling S3200** via Modbus TCP  
- Reading of sensor values (e.g., temperatures, operating states)  
- Control of switches (e.g., pumps, heating circuits)  
- Support for multiple system sections:
  - Boiler  
  - Heating circuit(s)  
  - Buffer tank  
  - Discharge unit  
  - Domestic hot water (DHW)  
  - Circulation pump  

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

The Fröling manuals and the Modbus register list live in the
[`documentation/`](documentation/) folder of this repository.

They are deliberately kept **outside** `custom_components/`, so HACS does not
copy roughly 33 MB of PDFs into every Home Assistant configuration directory.
The integration does not read these files at runtime — they are reference
material only.

`documentation/Modbus_Register.txt` lists the registers used by this
integration together with their entity type.

---

## 🖼️ Screenshots

<img width="2010" height="1344" alt="2025-10-03_14-57-08" src="https://github.com/user-attachments/assets/ebbb796a-b0e1-4b06-b8c6-bd18caea4a31" />

---

## 🤝 Contributing

Pull requests, issues, and suggestions for improvement are always welcome!

---