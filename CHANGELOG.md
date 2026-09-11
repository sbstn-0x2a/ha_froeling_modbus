# Changelog

## 0.5.0 – 2026-09-10

### ⚠️ Was sich sichtbar ändert

**Die Einrichtung liest die Anlage einmal komplett.** Nach der
Verbindungsprüfung fragt die Integration alle Register ab (rund 60 Anfragen,
wenige Sekunden) und schlägt vor, welche Anlagenteile es gibt: Heizkreise,
Boiler, Puffer, E-Abscheider, Zirkulationspumpe. Jeder Vorschlag trägt einen
Beleg (etwa „Heizkreis 02: 30,5 °C, Betriebsart Automatik“), du bestätigst.
Nicht erkannte Teile stehen unter „weitere Anlagenteile“. Es gibt kein
Modbus-Register für das Anlagenart-Menü des Bediengeräts; die Erkennung bleibt
ein Vorschlag.

**Register ohne brauchbaren Wert** (Fühler nicht belegt, Zähler bei 0 nach
Hunderten Betriebsstunden, fehlender Wärmemengenzähler) werden erkannt. Bei
der Einrichtung wählst du: deaktiviert anlegen (Vorgabe, später einschaltbar),
gar nicht anlegen, oder normal anlegen. Der Grund steht als Attribut
`hinweis_erkennung` an der Entität.

**Bestehende Installationen ändern sich nicht von selbst.** Ein Hinweis unter
Reparaturen führt in die Optionen; erst „Anlage neu einlesen“ macht einen
Vorschlag, und nichts wird ohne Bestätigung abgewählt. Aktive Teile bleiben
angehakt, auch wenn die Erkennung sie nicht findet – Abwählen löscht Entitäten
samt Historie.

**Zahlen-Entitäten sind Eingabefelder**, keine Schieberegler mehr: Am Regler
war der aktuelle Wert nicht zu sehen.

### Update von 0.3.x oder 0.4.0

Beim Update passiert automatisch:

* Alle bisherigen Entitäten bleiben mit **unveränderter `unique_id` und
  `entity_id`**; Historie, Statistik und Dashboards laufen weiter (Test
  `test_update_von_0_3_6_behaelt_alle_entitaeten`).
* Kommt von 0.3.x: Die Anzeigenamen bekommen den Gerätenamen vorangestellt
  („Kessel Kesseltemperatur“), siehe 0.4.0.
* Für die bereits gewählten Anlagenteile entstehen die neuen Entitäten der
  Kundenebene **zusätzlich**, mit `entity_id` nach dem neuen Schema
  (`sensor.froeling_kessel_…`). Bestand und Neues tragen also zwei Schemata
  nebeneinander; eine Umstellung des Bestands gibt es bewusst nicht, weil
  Automationen und Dashboards nicht mitziehen würden.
* Der Sensor „Meldungen“ kommt dazu. Der E-Abscheider entsteht noch nicht,
  weil der alte Eintrag den Haken nicht kennt.
* Nichts wird deaktiviert oder entfernt: Es liegt noch kein Befund vor.
* Unter *Reparaturen* erscheint „Anlage noch nicht eingelesen“.

Erst **Optionen → Anlage neu einlesen** bringt den Rest: E-Abscheider als
Vorschlag, und die Register ohne brauchbaren Wert nach deiner Auswahl
deaktiviert (Historie bleibt), entfernt (Historie geht) oder belassen. Aktive
Anlagenteile bleiben angehakt, auch wenn die Erkennung sie nicht findet; das
Abwählen ist dein Klick und löscht die Entitäten samt Historie.

Die fünf Fernsteuer-Entitäten bleiben beim Update aktiv, weil ihre Einträge
schon existieren; nur Neuinstallationen bekommen sie deaktiviert.

### Neu

* **Registertabelle aus der Modbus-Doku.** Alle 1718 Einträge der B1200522
  liegen als Daten in `registertabelle.py`, generiert aus
  `documentation/registerliste_b1200522.json`. Die 177 Entitäten der 0.4.0
  behalten `unique_id`, `entity_id` und Gerät; ein Test friert das ein.
* **99 weitere Entitäten der Kundenebene**, an der Anlage gegen das
  Bediengerät geprüft: Abgas-, Luft- und Lambdawerte, Zündung, WOS,
  Raumaustragung, Breitbandsonde, Feuerraum-Unterdruck, Zustandslaufzeit,
  E-Abscheider. Nur-lesbare Parameter erscheinen als Sensoren.
* **Gerät „E-Abscheider“** als eigener Anlagenteil.
* **Sensor „Meldungen“**: Anzahl anstehender Meldungen aus dem Fehlerpuffer
  33001–33020, die Klartexte aus der Doku als Attribut. Grundlage für eine
  Störmeldung ohne Cloud.
* **Options-Menü**: Verbindung und Intervall, Anlagenteile ein-/ausblenden,
  Anlage neu einlesen.
* Jede Entität trägt die Attribute `register` und `beschreibung` (Doku-Name).
* Der Coordinator liest nur noch die Register der gewählten Anlagenteile.

### Behoben

* Schrittweite der Zahlen-Entitäten war bei Faktor 2 fälschlich 0.0.
* Skalierung dreier Register gegen das Display korrigiert (41001, 40066,
  43070).
* Negative Sollwerte (Frostschutz −5 °C) ließen sich nicht schreiben: Der
  Rohwert ging ohne Zweierkomplement an pymodbus, der Schreibzugriff schlug
  fehl und riss die Verbindung mit.
* Zähler über 32767 (Betriebsstunden, kWh) wurden negativ angezeigt, mit
  Rückfall in der Langzeitstatistik.
* War Boiler 01 abgewählt, löschte jeder Start die Zirkulationssensoren und
  40601 mit, die an dessen Gerät hängen, und legte sie neu an; Umbenennungen
  und Bereiche gingen dabei verloren.
* Ein Register, das die Anlage nicht führt (0xFFFF), zeigte an Zahlen-
  Entitäten −0,5 °C statt keinen Wert.
* Nach einem Schreibvorgang konnte ein einmal ausgesetzter Leseblock den
  neuen Wert mit dem alten überschreiben.
* Der Verbindungsaufbau beim Start lief blockierend in der Ereignisschleife.
* Bei nicht erreichbarer Anlage lief jeder Block einzeln in den
  Verbindungs-Timeout (24 × 3 s); jetzt bricht der Durchlauf nach dem ersten
  ab.
* Ein geänderter Host in den Optionen aktualisiert die Kennung des Eintrags;
  Intervall und Anlagenteile lassen sich auch ohne erreichbare Anlage
  speichern.
* Beim Entladen wartet die Integration, bis der laufende Lesedurchlauf
  fertig ist, bevor sie die Verbindung schließt; vorher konnte eine Sitzung
  am Gateway offen bleiben.
* Zwei Alt-Einträge derselben Anlage bekommen beim Update keine doppelte
  Kennung mehr; der zweite bleibt ohne und wird im Protokoll gemeldet.

### Bekannte Lücken

* **Instanzen jenseits der acht Anlagenteile** (Heizkreis 03 ff., Boiler 02
  ff., Puffer 02 ff.) erkennt die Integration, legt sie aber noch nicht an.
  Die Tabelle kennt sie; es fehlt die Auswahl im Dialog.
* **Einzelne unerwünschte Entitäten** (die weder wertlos noch Teil eines
  abgewählten Anlagenteils sind) entfernt man über die Entitätenliste von
  Home Assistant; der Options-Flow bietet dafür keine Auswahl je Register.

## 0.4.0 – 2026-09-09

### ⚠️ Was sich sichtbar ändert

**Anzeigenamen bekommen den Gerätenamen vorangestellt.** Aus
„Kesseltemperatur" wird „Kessel Kesseltemperatur", aus „Außentemperatur"
„<Anlagenname> Außentemperatur". Das betrifft **auch bestehende
Installationen**. Die `entity_id` ändert sich dabei nicht, Automationen und
Dashboards funktionieren weiter — nur die angezeigte Beschriftung ist neu.
Wer die alte Beschriftung behalten will, kann die Entität in Home Assistant
umbenennen; eine gesetzte Bezeichnung gewinnt und bekommt kein Präfix.

Bei einem langen Anlagennamen wird das schnell unhandlich — aus
„Anlagenzustand" wird dann etwa „Froeling SP Dual compact Anlagenzustand".
In dem Fall lohnt es sich, das Gerät in den Geräteeinstellungen kürzer zu
benennen; der Anzeigename der Entitäten folgt dem sofort.

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
* **Das Aufräumen sucht nur noch im eigenen Config-Entry.** Bisher lief die
  Gerätesuche über `async_get_device`, das alle Einträge durchsucht — und
  Geräte-Identifier sind seit HA 2026.9 nicht mehr eindeutig. Bei
  Mehrdeutigkeit rät die Registry. Da an dieser Stelle gelöscht wird, hätte
  ein falscher Treffer die Entitäten einer fremden Anlage mitgenommen. Der
  Aufruf ist zudem als veraltet markiert und verschwindet in HA 2027.8.
* **Reste abgewählter Anlagenteile verschwinden beim Start.** Bisher räumte
  die Integration nur auf, wenn eine Gruppe gerade abgewählt wurde. Wer sie
  vorher abgewählt hatte, behielt ihre Entitäten dauerhaft als `unavailable`
  in der Registry — bei der Zirkulationspumpe drei Stück, weil sie kein
  eigenes Gerät hat und unter Boiler 01 hängt.
* **Untergeräte hängen sich über die Geräte-id am Regler ein.** Home
  Assistant 2026.9 erwartet `via_device_id` statt der bisherigen
  `via_device`-Identifier; der alte Weg warnt bei jedem Start und verschwindet
  in 2027.8. Die Integration erkennt selbst, welchen Weg die installierte
  Fassung kennt, und bleibt damit zu älteren Versionen verträglich. Das
  Reglergerät wird jetzt beim Einrichten ausdrücklich angelegt — vorher
  entstand es beiläufig mit der ersten Entität, die Reihenfolge war dem Zufall
  überlassen.
* Deinstallationsanleitung in beiden READMEs, dazu ein Abschnitt zu den
  unterstützten Anlagen: Die Registerkarte gilt für die SP Dual Compact mit
  Lambdatronic S3200. Andere Baureihen verbinden sich zwar, liefern die Werte
  dann aber zu den falschen Größen.
* Die Testsuite liegt im Repository (83 Tests, ohne Anlage und ohne
  Home-Assistant-Installation lauffähig).

### Kesselfernsteuerung

* Die fünf Entitäten auf den Fernsteuerregistern (48001, 48002, 48019, 48029,
  48030) sind **standardmäßig deaktiviert** und heißen jetzt „… (Fernsteuerung)“.
  Am Gerät gemessen: Ein einzelner Schreibzugriff schaltet die Sollwertvorgabe
  für alle Heizkreise und Boiler gleichzeitig ein, und nach zwei Minuten ohne
  weiteren Schreibzugriff fällt die Anlage zurück, während Home Assistant den
  Wert weiter anzeigt. Bestehende Registry-Einträge bleiben, wie sie sind.
  Einzelheiten im README-Abschnitt „Kesselfernsteuerung“.
* Das FC06-Echo wird geprüft. Antwortet die Anlage mit 0xFFFF (Wert innerhalb
  der Mindestschaltdauer verworfen), meldet die Integration das als Fehler,
  statt den nie übernommenen Wert anzuzeigen. Abweichende Echo-Adresse oder
  ein abweichender Echo-Wert gelten ebenfalls als Fehler.
* Die Attribute `modbus_override_active`, `min_switch_interval_min` und
  `override_timeout_min` an allen Zahlen-Entitäten sind entfernt. Sie
  stammten aus einem früheren Ansatz, standen auch an der
  Kessel-Solltemperatur und sagten nichts Wahres.

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
