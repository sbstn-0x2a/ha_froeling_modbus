# Froeling S3200 Modbus

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

🇬🇧 [English](README.md) | 🇩🇪 Deutsch

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
6. **Fernsteuerung:** Haken, Vorgabe aus. Eingeschaltet entsteht das Gerät
   „Fernsteuerung“ mit dem Select „Regelung“ und den Vorgabewerten aller
   Heizkreise und Boiler, siehe Abschnitt Kesselfernsteuerung.

Später über **Optionen**: Verbindung und Intervall ändern, Anlagenteile ein-
und ausblenden, Fernsteuerung ein- oder ausschalten, Entitäts-IDs an das Schema angleichen, oder die Anlage neu
einlesen. Abwählen eines Anlagenteils entfernt seine Entitäten samt
Historie; das Neu-Einlesen schlägt deshalb nie von selbst ein Abwählen vor.

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

**Anlagenname:** Der bei der Einrichtung vergebene Name steckt in der
`unique_id` jeder Entität und lässt sich deshalb nachträglich nicht ändern;
ein anderer Name wäre für Home Assistant eine neue Anlage ohne Historie. Wer
eine andere Beschriftung will, benennt das Reglergerät unter *Einstellungen →
Geräte* um; die Anzeigenamen aller Entitäten folgen sofort, Historie und
Statistik bleiben.

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
außen** (Doku B1200522 Kap. 2.6): Vorlauf-Solltemperatur und Freigabe je
Heizkreis, Solltemperatur je Boiler. Seit 0.6.0 setzt die Integration sie
samt dem nötigen Heartbeat um, als eigener Anlagenteil „Fernsteuerung“,
Vorgabe aus.

Sie ist für eine übergeordnete Regelung gedacht: Boilerladung nach Bedarf
statt nach Uhr, ein Raumthermostat in Home Assistant, das den Vorlauf
gradgenau vorgibt. Wer nur einen Heizkreis absenken oder die
Boilertemperatur dauerhaft ändern will, bleibt bei der **Betriebsart** und
den normalen Parametern; die wirken dauerhaft und ohne Heartbeat.

### Was die Anlage tut

Am Gerät gemessen (SP Dual Compact, 09.09.2026):

| Verhalten der Anlage | Folge |
|---|---|
| Ein einziger Schreibzugriff auf eines der Register schaltet die Vorgabe **für alle vorhandenen Heizkreise und Boiler** ein, wirksam nach einer Sekunde. | Es gibt kein „nur den Boiler“: Die übrigen Register wirken mit ihrem Inhalt mit. |
| Ohne weiteren Schreibzugriff fällt die Anlage nach **zwei Minuten** in ihre eigene Regelung zurück (gemessen 54 bis 129 s). | Wer die Vorgabe halten will, muss zyklisch schreiben. Die Integration tut das alle 60 s. |
| Einen **Schaltwechsel** (Freigabe an/aus, Boiler-Soll 0 ↔ größer 0) nimmt die Anlage frühestens **zehn Minuten** nach dem letzten an. Sonst antwortet sie mit 0xFFFF, verwirft den Wert und hält die Vorgabe trotzdem am Leben. | Ein Ausschalten innerhalb der Sperre gibt es nicht. Reine Wertänderungen (56 → 58 °C) gehen jederzeit. |
| Freigabe 1 mit Soll 0: Heizkurve der Anlage, aber **ohne Außentemperatur-Heizgrenze**. Soll größer 0: direkt die Vorlauf-Solltemperatur. Freigabe 0: Heizkreis aus, Frostschutz und Sicherheitspumpenlauf bleiben. | Mit Soll 0 heizt ein Heizkreis auch im Sommer nach Heizkurve. |
| Boiler-Soll 0: Ladung aus. Größer 0: Ladung bis zu diesem Wert, Start bei `Boiler-Soll − (Gewünschte Boilertemperatur − Nachladen, wenn Boilertemperatur unter)`. | Ein Boiler-Soll über der aktuellen Boilertemperatur startet eine Ladung, wie das „Extraladen“ der Cloud. |
| Die Betriebsart (48047 ff.) ist davon unabhängig und dauerhaft. | Das Select „Betriebsart“ bleibt wie bisher. |

### So wird sie benutzt

1. **Einschalten:** Haken „Fernsteuerung“ im gleichnamigen Schritt der
   Einrichtung oder später unter **Optionen → Fernsteuerung**. Damit
   entsteht unter dem Regler das Gerät **„Fernsteuerung“**, in dem alles zu
   diesem Thema liegt: das Select „Regelung“, der Binärsensor „Fernsteuerung
   aktiv“ und je vorhandenem Heizkreis „Heizkreis 0n Vorlauf-Soll“ und
   „Heizkreis 0n Freigabe“, je Boiler „Boiler 0n Solltemperatur“. Ohne
   Einlesen der Anlage zählen nur die angehakten Anlagenteile als
   vorhanden.
2. Select **„Regelung“** auf **„Home Assistant“** stellen. Die Integration
   schreibt sofort einen kompletten Satz und danach alle 60 s. Bei
   **„Kessel“** (Vorgabe) schreibt sie nichts.
3. **Vorgabewerte** im Gerät „Fernsteuerung“ setzen. Bei Regelung Home
   Assistant geht jede Änderung sofort raus, Schaltwechsel nach der
   Zehn-Minuten-Regel. Bei Regelung Kessel wird sie nur gemerkt und mit dem
   nächsten Einschalten gesendet.
4. Der Binärsensor **„Fernsteuerung aktiv“** zeigt, ob die Vorgabe wirkt:
   an, wenn Regelung Home Assistant ist und der letzte erfolgreiche Satz
   jünger als zwei Minuten war. Bleibt der Erfolg aus, geht er aus und das
   Protokoll warnt.
5. Zurück auf **„Kessel“**: Die Integration hört auf zu schreiben, die Anlage
   übernimmt nach spätestens zwei Minuten selbst. Es wird nie „Freigabe 0“
   nachgeschoben.

**Bei Regelung Home Assistant übernimmt Home Assistant die Sollwerte aller
Heizkreise und Boiler**, nicht nur die, die du gesetzt hast. Für jede
Instanz ohne Vorgabe geht ein neutraler Wert mit: Heizkreis Freigabe an und
Soll 0 (Heizkurve ohne Heizgrenze), Boiler der Wert von „Gewünschte
Boilertemperatur“ (41632). Das Attribut `neutral` an der Entität zeigt, dass
keine Vorgabe gesetzt ist, `register_wert` den zuletzt von der Anlage
angenommenen Wert.

**Ausgeschaltet** gibt es keine Fernsteuer-Entitäten, keinen Heartbeat, und
die Register 48001–48046 werden nicht gelesen. Die Betriebsart der
Heizkreise bleibt unberührt. Die fünf Entitäten aus 0.4.0/0.5.0 („…
(Fernsteuerung)“ unter Heizkreis 01/02 und Boiler 01) liegen jetzt im Gerät
„Fernsteuerung“ mit neuem Namen; `unique_id`, `entity_id` und Historie
bleiben.

### Auflagen

* **Zehn Minuten** zwischen zwei Schaltwechseln. Bis dahin sendet die
  Integration den alten Zustand und führt den neuen im Attribut
  `ausstehend` des Selects; ein trotzdem verworfener Zugriff zählt in
  `verworfen`.
* **Zwei Minuten** ohne erfolgreichen Satz, und die Anlage regelt selbst.
  Home Assistant merkt das am Binärsensor und am Attribut
  `fenster_ueberschritten`.
* **Nach einem Neustart** von Home Assistant steht die Regelung immer auf
  Kessel. Die Vorgabewerte bleiben erhalten; eine Automation muss die
  Regelung selbst wieder einschalten.
* **Die Betriebsart bleibt unabhängig.** Ob ein Heizkreis mit Betriebsart
  „Aus“ und Freigabe 1 läuft, ist am Gerät nicht getestet, ebenso wenig, ob
  ein Boiler-Soll im Anlagenzustand „Brauchwasser“ den Kessel startet.

### Beispiel: Brauchwasserladung nach Bedarf

Lädt den Boiler auf 65 °C, sobald die Temperatur oben unter 47 °C fällt,
und gibt die Regelung an den Kessel zurück, wenn 65 °C erreicht sind. Die
Ladung startet, sobald die Boilertemperatur unter `65 − (Gewünschte
Boilertemperatur − Nachladen, wenn Boilertemperatur unter)` liegt; bei den
Werkswerten ist das deutlich über 47 °C.

Die `entity_id`s folgen dem Schema neuer Installationen mit dem Anlagennamen
`froeling`; neue Fernsteuer-Entitäten heißen
`number.froeling_fernsteuerung_<schlüssel>`. Die fünf Entitäten aus
0.4.0/0.5.0 behalten ihre bisherige ID, in einer Bestandsinstallation also
etwa `number.froeling_boiler01_solltemperatur_modbus` oder, aus 0.3.x,
`number.boiler_1_solltemperatur_modbus`.

```yaml
automation:
  - alias: "Boiler laden, wenn kalt"
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

  - alias: "Boiler geladen, Regelung zurück an den Kessel"
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

Solange die Regelung auf Home Assistant steht, laufen die Heizkreise mit
ihren Vorgabewerten, ohne gesetzte Vorgabe also nach Heizkurve ohne
Heizgrenze. Wer das im Sommer nicht will, setzt „Heizkreis 0n Freigabe“
vorher aus.

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

<img width="500" height="618" alt="image" src="https://github.com/user-attachments/assets/6ffe643d-9679-4c69-90a0-10cdbadef477" />

---

## 🤝 Mitwirken

Pull Requests, Issues und Verbesserungsvorschläge sind jederzeit willkommen!  

---
