# Froeling S3200 Modbus

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Eine **Home Assistant Custom Integration** für die Anbindung einer **Fröling Lambdatronic S3200** Steuerung über **Modbus TCP**.  
Damit lassen sich Zustände und Messwerte der Heizanlage (Kessel, Heizkreise, Puffer, Austragung etc.) direkt in Home Assistant einbinden.

---

## ✨ Funktionen

- Verbindung zur **Fröling S3200** über Modbus TCP  
- Auslesen von Sensorwerten (z. B. Temperaturen, Betriebszustände)  
- Steuerung von Schaltern (z. B. Pumpen, Heizkreise)  
- Erkennt beim Einrichten, welche Anlagenteile vorhanden sind, und legt nur
  dafür Entitäten an
- Unterstützung mehrerer Gerätebereiche:
  - Kessel
  - Heizkreis(e)
  - Puffer
  - Austragung
  - Warmwasser (DHW)
  - Zirkulationspumpe
  - E-Abscheider
- Sensor „Meldungen“ mit den anstehenden Störungstexten der Anlage
- Langzeitstatistik für alle Messwerte und Zähler

---

## ⚠️ Unterstützte Anlagen

Entwickelt und geprüft an einer **Fröling SP Dual Compact mit Lambdatronic
S3200**, angebunden über Modbus TCP an einem RS485-Gateway.

Die Registerkarte ist auf dieses Layout festgelegt. Andere Baureihen nutzen
andere Adressen — die P5 / Lambdatronic P3200 etwa mit einem Versatz von 1000,
die S3100 weicht ebenfalls ab. Eine solche Anlage verbindet sich zwar, die
Werte gehören dann aber zu den falschen Größen. Mehr als zwei Heizkreise und
Solarmodule sind ebenfalls nicht abgedeckt.

Wenn deine Anlage abweicht: bitte ein Issue mit der Typenbezeichnung öffnen,
statt den angezeigten Werten zu vertrauen.

Noch nicht abgedeckt: Heizkreise ab 03, Boiler ab 02 und Puffer ab 02 werden
zwar erkannt, aber noch nicht als Entitäten angelegt.

---

## 📦 Installation

### Variante 1: Über HACS (empfohlen)
1. Stelle sicher, dass [HACS](https://hacs.xyz/) installiert ist.  
2. Füge dieses Repository als **Custom Repository** hinzu:
   - HACS → Integrationen → Repositories → „+“ →  
     URL: `https://github.com/sbstn-0x2a/ha_froeling_modbus`  
     Kategorie: `Integration`  
3. Danach taucht die Integration in HACS auf und kann installiert werden.  

### Variante 2: Manuell
1. Lade die Dateien aus `custom_components/froeling_s3200_modbus` herunter.  
2. Kopiere den Ordner `froeling_s3200_modbus` nach:  
   ```
   config/custom_components/froeling_s3200_modbus
   ```
3. Home Assistant neu starten.  

---

## 🗑️ Deinstallation

1. Unter **Einstellungen → Geräte & Dienste** die Integration
   **Froeling S3200 Modbus** öffnen, am Eintrag das Drei-Punkte-Menü
   aufrufen und **Löschen** wählen. Damit verschwinden der Eintrag und alle
   zugehörigen Geräte und Entitäten.
2. Bei Installation über HACS zusätzlich: **HACS → Integrationen →
   Froeling S3200 Modbus → Drei-Punkte-Menü → Entfernen**.
3. Bei manueller Installation den Ordner
   `config/custom_components/froeling_s3200_modbus` löschen.
4. Home Assistant neu starten.

Aufgezeichnete Historie und Langzeitstatistik bleiben erhalten, bis der
Recorder sie regulär aufräumt. Auf die Heizung wird beim Deinstallieren
nichts geschrieben.

## ⚙️ Konfiguration

1. Gehe in Home Assistant auf:  
   **Einstellungen → Geräte & Dienste → Integration hinzufügen**  
2. Wähle **Froeling S3200 Modbus**.  
3. Gib die Verbindungseinstellungen ein:
   - Hostname / IP-Adresse der S3200
   - Port (Standard: 502)
   - Update-Intervall (Standard: 30 s, erlaubt 15–3600 s)  
   - Modbus UnitID (2)
4. Die Anlage wird einmal komplett gelesen (wenige Sekunden).
5. **Anlagenteile bestätigen:** Die Haken sind aus dem Scan vorbelegt, jeder
   mit Beleg (etwa „Heizkreis 02: 30,5 °C, Betriebsart Automatik“). Nicht
   erkannte Teile stehen unter „weitere Anlagenteile anzeigen“. Darunter die
   Auswahl, was mit Registern ohne brauchbaren Wert geschieht: deaktiviert
   anlegen (Vorgabe), gar nicht anlegen, normal anlegen.

Später über **Optionen**: Verbindung und Intervall ändern, Anlagenteile ein-
und ausblenden, oder die Anlage neu einlesen. Abwählen eines Anlagenteils
entfernt seine Entitäten samt Historie; das Neu-Einlesen schlägt deshalb nie
von selbst ein Abwählen vor.

---

## 🔄 Update von 0.3.x oder 0.4.0

Ein Update ändert am Bestand nichts: Alle bisherigen Entitäten behalten ihre
`entity_id`, Historie und Statistik. Zusätzlich entstehen für die schon
gewählten Anlagenteile die neuen Entitäten der Kundenebene und der Sensor
„Meldungen“, mit `entity_id` nach dem neuen Schema (`sensor.froeling_kessel_…`).
Beide Schemata stehen danach nebeneinander; eine Umbenennung des Bestands
nimmt die Integration bewusst nicht vor, weil Automationen, Skripte und
Dashboards nicht mitziehen würden. Wer umstellen möchte, benennt einzelne
Entitäten in Home Assistant um; Historie und Statistik folgen dabei
automatisch.

Der E-Abscheider und die Erkennung wertloser Register kommen erst mit
**Optionen → Anlage neu einlesen**. Ein Hinweis unter *Reparaturen* erinnert
daran. Dort wählst du auch, ob Register ohne brauchbaren Wert deaktiviert
(Historie bleibt), entfernt (Historie geht) oder belassen werden.

Das Neu-Einlesen lohnt sich später erneut: Es bewertet jedes Mal frisch.
Liefert ein vorher wertloses Register inzwischen Werte, etwa ein Zähler, der
zu zählen begonnen hat, wird seine Entität wieder aktiviert beziehungsweise
neu angelegt; umgekehrt wird ein neu als wertlos erkanntes Register
deaktiviert. Was du selbst deaktiviert hast, bleibt unberührt. Zähler gelten
erst ab 24 Betriebsstunden der Anlage als wertlos, damit eine frisch in
Betrieb genommene Anlage nicht vorschnell eingestuft wird.

---

## ⚙️ Modbus-Adresse / Unit-ID einstellen

Für eine funktionierende Kommunikation zwischen Home Assistant und der Fröling-Steuerung müssen die **Modbus-Adressen (Unit-IDs)** übereinstimmen.

Die **Unit-ID** wird direkt am Bedienfeld der Heizung eingestellt:

```
Anlage → Einstellen → Allg. Einstellungen → MODBUS Einstellungen → MODBUS Adresse
```

Hier kann ein Wert zwischen **1 und 247** vergeben werden.  
In der Integration wird derselbe Wert im Feld **„Unit ID“** bzw. **„Unit Number“** eingetragen.  
Nur wenn beide Werte identisch sind, können Daten korrekt gelesen und geschrieben werden.

> **Wichtig:**  
> Wenn die Adressen nicht übereinstimmen, werden keine Werte empfangen oder Befehle umgesetzt.  
> Jede Modbus-Steuerung im Netzwerk muss außerdem eine **eindeutige** Adresse besitzen, um Adresskonflikte zu vermeiden.

**Empfohlene Grundeinstellungen am Fröling-Gerät:**
- COM 2 als Modbus-Schnittstelle aktivieren → **JA**  
- MODBUS-Protokoll: **RTU (1)**  
- MODBUS-Protokoll 2014 verwenden → **JA**

> **Zum Schreiben wird das 2014er Protokoll gebraucht.**  
> Ohne die Einstellung beantwortet die Anlage weiterhin Lesezugriffe: Der
> Verbindungstest bei der Einrichtung geht durch, und alle Sensoren zeigen
> Werte. Nur das Schreiben scheitert, mit *Illegal Function* — Zahlen-,
> Schalter-, Auswahl- und Zeit-Entitäten bleiben stillschweigend auf ihrem
> alten Wert. Wenn Änderungen aus Home Assistant nie an der Heizung ankommen,
> zuerst hier nachsehen.

Diese Optionen befinden sich ebenfalls im Menü:  
`Anlage → Einstellen → Allg. Einst → MODBUS Einstellungen`.

---

## 🔁 Kesselfernsteuerung (Register 48001–48046)

Die Anlage kennt neben den normalen Parametern eine **Sollwertvorgabe von
außen**: Vorlauf-Solltemperatur und Freigabe je Heizkreis sowie die
Boiler-Solltemperatur (Register 48001–48046). Sie verhält sich anders als
alles andere in dieser Integration, deshalb sind die zugehörigen Entitäten
(„Freigabe (Fernsteuerung)“, „Vorlauf-Soll (Fernsteuerung)“, „Solltemperatur
(Fernsteuerung)“) **standardmäßig deaktiviert**.

Was am Gerät gemessen wurde (SP Dual Compact, 09.09.2026):

* **Ein einziger Schreibzugriff** auf eines dieser Register schaltet die
  Vorgabe **für alle vorhandenen Heizkreise und Boiler gleichzeitig** ein, mit
  dem aktuellen Inhalt der übrigen Register. Wer nur die Boiler-Solltemperatur
  schreibt, schaltet damit auch die Heizkreise auf ihre Fernsteuer-Werte.
* Bleibt danach **mehr als zwei Minuten** jeder weitere Schreibzugriff aus,
  regelt die Anlage wieder selbst. Die Entität in Home Assistant zeigt den
  geschriebenen Wert trotzdem weiter an.
* Ein Schaltwechsel **innerhalb von zehn Minuten** wird von der Anlage
  verworfen (die Integration meldet das seit dieser Version als Fehler), hält
  die Vorgabe aber trotzdem für weitere zwei Minuten am Leben.

Für die üblichen Wünsche (Heizkreis absenken, Boiler-Solltemperatur ändern)
sind die **Betriebsart** und die normalen Parameter das richtige Werkzeug;
sie wirken dauerhaft. Eine echte Umsetzung der Fernsteuerung mit zyklischem
Nachschreiben ist als optionale Funktion geplant.

## 📚 Herstellerdokumentation

Die Fröling-Handbücher und die Modbus-Registerliste liegen im Ordner
[`documentation/`](documentation/) dieses Repositorys.

Sie liegen bewusst **außerhalb** von `custom_components/`, damit HACS nicht rund
33 MB PDFs in jedes Home-Assistant-Konfigurationsverzeichnis kopiert. Die
Integration liest diese Dateien zur Laufzeit nicht — sie sind reines
Nachschlagematerial.

`documentation/Modbus_Register.txt` listet die von dieser Integration genutzten
Register samt Entitätstyp auf.

---

## 🖼️ Screenshots
<img width="2010" height="1344" alt="2025-10-03_14-57-08" src="https://github.com/user-attachments/assets/ebbb796a-b0e1-4b06-b8c6-bd18caea4a31" />

---

## 🤝 Mitwirken

Pull Requests, Issues und Verbesserungsvorschläge sind jederzeit willkommen!  

---