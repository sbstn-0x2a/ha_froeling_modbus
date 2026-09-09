# Changelog

## 0.4.0 – noch nicht veröffentlicht

### ⚠️ Was sich sichtbar ändert

**Anzeigenamen bekommen den Gerätenamen vorangestellt.** Aus
„Kesseltemperatur" wird „Kessel Kesseltemperatur", aus „Außentemperatur"
„<Anlagenname> Außentemperatur". Das betrifft **auch bestehende
Installationen**. Die `entity_id` ändert sich dabei nicht, Automationen und
Dashboards funktionieren weiter — nur die angezeigte Beschriftung ist neu.
Wer die alte Beschriftung behalten will, kann die Entität in Home Assistant
umbenennen; eine gesetzte Bezeichnung gewinnt.

**Neue Installationen bekommen andere `entity_id`.** Sie sind jetzt nach
Anlage, Gerät und Größe gegliedert:

    sensor.froeling_kessel_kesseltemperatur
    sensor.froeling_aussentemperatur          (Regler)
    select.froeling_hk01_betriebsart

Vorher hing die Kennung am übersetzten Anzeigenamen und trug weder den
Anlagennamen noch das Gerät. Zwei Anlagen in derselben Installation
kollidierten dadurch und wurden mit `_2` unterschieden.

**Bestehende Installationen behalten ihre `entity_id` unverändert.** Home
Assistant übernimmt den neuen Vorschlag nur beim Neuanlegen einer Entität.
Wer umstellen möchte, benennt die Entitäten über
**Einstellungen → Geräte & Dienste → Entitäten** um. Dabei gilt:

* Langzeitstatistik und Zustandshistorie zieht der Recorder automatisch mit.
* Automationen, Skripte, Dashboards und Vorlagen zieht er **nicht** mit —
  die müssen von Hand nachgezogen werden.

### Neu

* Ein gemeinsamer Coordinator liest alle Register in Blöcken statt einzeln.
  Statt 177 Einzelabfragen genügen 25 Blockabfragen. An der Anlage gemessen
  (damals 143 Register in 18 Blöcken): 348 ms statt 1645 ms.
* Der Verbindungstest läuft jetzt schon bei der Einrichtung. Ein falscher
  Port oder eine falsche Unit-ID fällt sofort auf, statt in einer scheinbar
  eingerichteten Integration mit dauerhaft leeren Entitäten zu enden. Beide
  Fehler werden unterschieden.
* Dieselbe Anlage lässt sich nicht mehr zweimal einrichten. Bisher entstand
  bei gleichen Verbindungsdaten ein zweiter Satz Geräte und Entitäten.
* Das Abfrageintervall ist auf 15–3600 s begrenzt, Vorgabe ist jetzt 30 s
  statt 60 s. An der Anlage gemessen ändern sich Werte im 2-Sekunden-Takt,
  und ein Schneckenlauf von 11 s fiel bei 60 s regelmäßig zwischen zwei
  Abfragen.
* **Ein gestörter Registerblock legt nicht mehr die ganze Anlage lahm.**
  Vorher las jede Entität ihr Register selbst; ein Aussetzer am Gateway setzte
  genau diesen einen Wert auf `unknown`. Mit dem Coordinator hätte ein
  einzelner Fehler alle 177 Entitäten gleichzeitig auf `unavailable` gesetzt —
  Automationen mit Zustandstriggern wären bei jedem Netzwerkhusten
  losgelaufen. Jetzt behält ein fehlgeschlagener Block seine letzten Werte;
  erst nach drei Fehlversuchen in Folge melden die betroffenen Entitäten
  `unknown`. Nur wenn kein einziger Block antwortet, gilt die Anlage als
  nicht erreichbar.
* **Verbindungsfehler stehen als Meldung im Protokoll, nicht als Traceback.**
  `pymodbus` meldet einen Abbruch als `ConnectionException`, und die erbt von
  `ModbusException`, nicht von `OSError` — das vorhandene
  `except BrokenPipeError` fing sie deshalb nicht. Die Ausnahme verliess den
  Executor, und Home Assistant protokollierte sie als unerwarteten Fehler mit
  vollem Traceback. Die Lücke steckte in allen fünf Zugriffsfunktionen; sie
  laufen jetzt über eine gemeinsame Fassung.
* **Schreibvorgänge kollidieren nicht mehr mit dem Lesedurchlauf.**
  `ModbusTcpClient` ist nicht threadsicher, und alle Zugriffe laufen über den
  Executor. Wurde während eines Abrufs ein Wert gesetzt, gingen zwei Anfragen
  gleichzeitig auf denselben Socket und die Antworten kamen vermischt zurück —
  ein Wert konnte am falschen Register landen. Der Coordinator serialisiert
  die Zugriffe jetzt je Vorgang.
* Deinstallationsanleitung in beiden READMEs.
* Die Testsuite liegt im Repository (83 Tests, ohne Anlage und ohne
  Home-Assistant-Installation lauffähig).

### Behoben

* **Der Regler trug den falschen Namen.** Am Hauptgerät stand fest
  „SP Dual Compact" statt des bei der Einrichtung vergebenen Anlagennamens.
* **Fehlende Register.** 26 Adressen in den Bereichen 42xxx, 43xxx und 48xxx
  fehlten in der Registerlandkarte.
* **Langzeitstatistik für Sensoren ohne Einheit.** In 0.3.6 bekamen nur
  Sensoren *mit* Einheit eine `state_class`. Die Bedingung war falsch — der
  Recorder braucht keine Einheit, nur eine `state_class`. Damit führen jetzt
  auch Brennerstarts und Reinigungen Statistik.
* **Zähler als `total_increasing`.** 24 Sensoren waren als `measurement`
  eingetragen, obwohl sie nur aufwärts laufen: sämtliche
  `betriebsstunden_*`, die Stundenzähler für Pellets-, Heiz-, Teillast- und
  Scheitholzbetrieb, die Stunden seit der letzten Wartung, der
  Pelletverbrauch, die beiden rücksetzbaren Mengenzähler sowie Tages- und
  Gesamtertrag und die vom Kessel erzeugte Wärmemenge. Als `measurement`
  bildete die Statistik daraus Mittelwerte statt Zuwächse — für
  Verbrauchsauswertungen brauchte man Hilfsentitäten.

  Dass einige davon zurückgesetzt werden (Wartung, die `resetierbar*`-Zähler,
  der Tagesertrag), spricht nicht dagegen: Genau dafür gibt es
  `total_increasing` neben `total` — der Recorder erkennt den Rücksprung als
  Reset und zählt den Zuwachs korrekt weiter.

  `measurement` bleiben nur die beiden Abwärtszähler
  (`zeit_bis_zur_naechsten_reinigung`,
  `kessel_verbleibende_heizstunden_bis_asche_entleeren`) und neun
  Einstellwerte auf Holding-Registern, die trotz Minuten-Einheit keine
  Laufzeiten sind.

  Beim Wechsel der `state_class` beginnt der Recorder für die betroffenen
  Sensoren eine neue Statistikreihe. Die bisher gesammelten Mittelwerte
  bleiben liegen und werden nicht in Summen umgerechnet.
* **Energie-Dashboard.** Tagesertrag, Gesamtertrag und die vom Kessel
  erzeugte Wärmemenge tragen jetzt `device_class: energy`. Zusammen mit der
  Total-`state_class` erfüllen sie damit die Bedingungen des
  Energie-Dashboards und lassen sich dort direkt auswählen — vorher ging das
  nur über eine Hilfsentität. Ob die Anlage die Register füllt, hängt vom
  angeschlossenen Wärmemengenzähler ab.
* **Karteileichen.** Wird ein Anlagenteil in den Optionen abgewählt,
  verschwinden seine Entitäten jetzt auch aus der Registry.


## 0.3.6

* **Pelletsbefüllungs-Zeiten.** Die Register 40062 und 40095 zählen Minuten
  seit Mitternacht, gelesen wurden sie als „HHMM". Eingestellte Zeiten
  wichen dadurch ab.
* `state_class` für die Langzeitstatistik ergänzt.
* Register 40067 und 40070 der Rücklaufanhebung aufgenommen.
* Die Herstellerhandbücher liegen nicht mehr im Auslieferungspfad — sie
  wurden bei jeder Installation mitkopiert.

Ältere Fassungen: siehe die
[Releases auf GitHub](https://github.com/sbstn-0x2a/ha_froeling_modbus/releases).
