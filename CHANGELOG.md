# Changelog

## 0.6.0 – unveröffentlicht

### ⚠️ Was sich sichtbar ändert

**Die Kesselfernsteuerung (Register 48001–48046) ist jetzt umgesetzt**, mit
dem Heartbeat, den die Anlage dafür verlangt. Sie wird bei der Einrichtung
in einem eigenen Schritt **„Fernsteuerung“** abgefragt: ein Haken, Vorgabe
aus, auch für bestehende Installationen. Später lässt sie sich über
**Optionen → Fernsteuerung** ein- oder ausschalten.

**Eingeschaltet entsteht ein eigenes Gerät „Fernsteuerung“** unter dem
Regler, in dem alles zu diesem Thema liegt: das Select **„Regelung“**
(Kessel / Home Assistant), der Binärsensor **„Fernsteuerung aktiv“**, je
vorhandenem Heizkreis „Heizkreis 0n Vorlauf-Soll“ und „Heizkreis 0n
Freigabe“, je Boiler „Boiler 0n Solltemperatur“. Die fünf bisherigen
Fernsteuer-Entitäten („… (Fernsteuerung)“ unter Heizkreis 01/02 und
Boiler 01) wandern in dieses Gerät und bekommen die neuen Namen;
`unique_id`, `entity_id` und Historie bleiben. Neue Instanzen bekommen
`entity_id`s nach dem Schema `number.<anlage>_fernsteuerung_<schlüssel>`.

**Ausgeschaltet gibt es keine Fernsteuer-Entitäten**, auch die fünf alten
nicht, keinen Heartbeat, und die Register 48001–48046 werden nicht gelesen.
Die Betriebsart der Heizkreise bleibt davon unberührt.

Das Select „Regelung“ entscheidet, wer die Sollwerte der Heizkreise und
Boiler bestimmt. Bei **Kessel** (Vorgabe) schreibt die Integration nichts an
diese Register. Bei **Home Assistant** schreibt sie sofort und danach alle
60 s einen kompletten Satz: Boiler-Solltemperatur, Vorlauf-Soll und
Freigabe für **alle** vorhandenen Heizkreise und Boiler. Die Entitäten im
Gerät „Fernsteuerung“ sind **Vorgabewerte** für diesen Satz. Sie schreiben
nicht selbst: Bei Regelung Home Assistant geht eine Änderung sofort raus,
bei Regelung Kessel wird sie nur gemerkt. Ohne Einlesen der Anlage zählen
nur die angehakten Anlagenteile als vorhanden.

Was die Anlage dabei tut (am Gerät gemessen 09.09.2026, Doku B1200522
Kap. 2.6):

* Der erste Schreibzugriff schaltet die Sollwertvorgabe global ein, wirksam
  nach einer Sekunde. Ohne weiteren Schreibzugriff fällt die Anlage nach
  **zwei Minuten** in ihre eigene Regelung zurück; der Heartbeat hält sie am
  Leben.
* Einen **Schaltwechsel** (Freigabe an/aus, Boiler-Soll 0 ↔ größer 0) nimmt
  die Anlage frühestens **zehn Minuten** nach dem letzten an. Die Integration
  sendet bis dahin den alten Zustand weiter und führt den neuen im Attribut
  `ausstehend`. Reine Wertänderungen (56 → 58 °C) gehen jederzeit.
* Zurück auf Kessel heißt: aufhören zu schreiben. Die Anlage übernimmt nach
  spätestens zwei Minuten wieder selbst. Ein „Freigabe 0“ wird nie
  nachgeschoben, weil auch ein verworfener Schreibzugriff die Vorgabe
  verlängert.
* Nach einem **Neustart** von Home Assistant steht die Regelung immer auf
  Kessel; die Vorgabewerte bleiben erhalten. War vorher Home Assistant
  Regelung, steht ein Hinweis im Protokoll.

**Nicht gesetzte Vorgaben bekommen neutrale Werte.** Heizkreis: Freigabe an
und Soll 0, das ist die Heizkurve der Anlage, aber **ohne
Außentemperatur-Heizgrenze**. Boiler: der Wert von „Gewünschte
Boilertemperatur“ (41632). Wer bei Regelung Home Assistant nur den Boiler
führen will, muss wissen, dass die Heizkreise dann auch im Sommer nach
Heizkurve laufen.

**Boiler-Soll als Ersatz für das „Extraladen“ der Cloud.** Ein Boiler-Soll
über der aktuellen Boilertemperatur startet eine Ladung. Laut Doku beginnt
sie bei `Boiler-Soll − (Gewünschte Boilertemperatur − Nachladen, wenn
Boilertemperatur unter)` und endet beim Boiler-Soll; 0 schaltet die Ladung
aus. Beispielautomation im README.

### Update von 0.5.0

* Nach dem Update ist die Fernsteuerung **aus**. Die fünf bisher
  deaktivierten Fernsteuer-Entitäten verschwinden aus der Registry; alles
  andere bleibt.
* Einschalten über **Optionen → Fernsteuerung**. Dann entsteht das Gerät
  „Fernsteuerung“ mit dem Select „Regelung“, dem Binärsensor und den
  Vorgabe-Entitäten aller vorhandenen Heizkreise und Boiler. Die fünf
  bisherigen Entitäten kommen mit ihrer `unique_id` und ihrer bisherigen
  `entity_id` zurück: Home Assistant merkt sich gelöschte Registry-Einträge
  und stellt sie wieder her, in der Testinstanz samt gesetzter Vorgabe geprüft.
* Solange die Regelung auf Kessel steht, schreibt die Integration nichts;
  erst Regelung Home Assistant startet den Heartbeat.

### Neu

* **Optionen → „Entitäts-IDs an das Schema angleichen“.** Zeigt alle
  Entitäten, deren ID vom Schema „Anlage, Gerät, Größe“ abweicht (etwa der
  Bestand aus 0.3.x), als Liste alt → neu und benennt sie nach Bestätigung
  über die Registry um. Historie und Langzeitstatistik ziehen mit;
  Automationen, Skripte, Dashboards und Vorlagen sind Handarbeit. Belegte
  Ziel-IDs werden übersprungen und genannt.

* **Zwei neue Erkennungsregeln.** Bei einem Hygienespeicher (Parameter
  „Wird ein Hygiene Speicher verwendet“ = JA) und einer Boilerpumpen-Ansteuerung
  von 0 % gelten die fünf Boilerpumpen-Register (Ansteuerung, Nachlauf,
  Min-/Maxdrehzahl, Puffer/Boiler-Differenz) als wertlos: Der „Boiler“ ist
  dann die Trinkwasserzone im Puffer, eine Pumpe gibt es nicht. Steht der
  Betriebsstundenzähler WOS nach 24 Betriebsstunden auf 0, gelten Zeitfenster,
  Laufzeit, Intervall, Zustand und Rückmeldung des WOS als wertlos (kein
  automatischer Antrieb). Beides wirkt erst nach „Anlage neu einlesen“ und
  folgt der dort gewählten Behandlung; läuft die Pumpe oder der Antrieb doch,
  bringt das nächste Einlesen die Entitäten zurück.

* Schritt **„Fernsteuerung“** in der Einrichtung und in den Optionen.
* Gerät **„Fernsteuerung“** unter dem Regler mit dem Select **„Regelung“**
  (`kessel` / `home_assistant`; Attribute `letzter_erfolg`,
  `letzter_fehler`, `ausstehend`, `verworfen`, `fenster_ueberschritten` und
  `register` mit den Registern des gesendeten Satzes) und dem Binärsensor
  **„Fernsteuerung aktiv“**: an, wenn Home Assistant Regelung ist und der
  letzte erfolgreiche Satz jünger als zwei Minuten. Bleibt der Erfolg zwei
  Minuten aus, geht er aus und das Protokoll warnt einmal.
* Vorgabe-Entitäten für **jeden** vorhandenen Heizkreis und Boiler, nicht
  mehr nur Heizkreis 01/02 und Boiler 01. Sie tragen `register_wert` (der
  zuletzt von der Anlage angenommene Wert) und `neutral` (keine Vorgabe
  gesetzt); der `hinweis` sagt, dass sie nur bei Regelung Home Assistant
  wirken.
* Ein Satz geht als geschlossene Folge einzelner FC06-Schreibzugriffe raus
  (FC16 kennt die Anlage nicht, Exception 0x90/02), Reihenfolge Boiler-Soll,
  HK-Soll, HK-Freigabe, mit einem Refresh am Ende statt einem je Register.
* Ein von der Anlage verworfener Schaltwechsel (Echo 0xFFFF) zählt in
  `verworfen` und wird beim nächsten Heartbeat erneut versucht.
* **Instanzen jenseits der acht Anlagenteile:** Heizkreis 03–18, Boiler
  02–08 und Puffer 02–04 sind jetzt wählbare Anlagenteile mit denselben
  Entitäten wie Heizkreis 02, Boiler 01 und Puffer 01 (gleiche Namen, eigenes
  Gerät „Heizkreis 03“ …). Der Haken erscheint in der Einrichtung, in den
  Optionen und beim Neu-Einlesen nur, wenn die Erkennung die Instanz als
  vorhanden meldet oder sie schon angehakt ist -- eine Anlage mit zwei
  Heizkreisen sieht keine 30 Haken. Gelesen wird eine Instanz nur, wenn sie
  angehakt ist.

### Bekannte Lücken

* **Gerätetests stehen aus:** ob ein Boiler-Soll (48019) im Anlagenzustand
  „Brauchwasser“ den Kessel tatsächlich startet, die Rangfolge von
  Betriebsart (48047 ff.) und Freigabe (Betriebsart „Aus“ mit Freigabe 1),
  und ob die Fernsteuerregister einen Neustart der Anlage überstehen.

## 0.5.0 – 2026-09-11

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

Ein späteres Neu-Einlesen wirkt in beide Richtungen: Liefert ein vorher
wertloses Register inzwischen Werte (ein Zähler hat begonnen zu zählen),
wird seine Entität wieder aktiviert bzw. bei „gar nicht anlegen“ neu
angelegt. Vom Nutzer selbst deaktivierte Entitäten bleiben aus. Zähler gelten erst ab 24
Betriebsstunden als wertlos.

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
* Ein von der Anlage abgewiesener Schreibzugriff (Wert außerhalb des
  Bereichs, Protokoll 2014 aus, Mindestschaltdauer) erscheint in Home
  Assistant als Fehler des Dienstaufrufs mit Klartext, statt nur im Protokoll.
* Der Coordinator liest nur noch die Register der gewählten Anlagenteile.

### Behoben

* Schrittweite der Zahlen-Entitäten war bei Faktor 2 fälschlich 0.0; jetzt
  folgt sie den Dezimalstellen der Doku (Temperaturen ganzzahlig wie am
  Bediengerät, Pelletlager in 0,1 t).
* Skalierung dreier Register gegen das Display korrigiert (41001, 40066,
  43070).
* Negative Sollwerte (Außentemperatur-Schwellen unter 0 °C) ließen sich nicht
  schreiben: Der Rohwert ging ohne Zweierkomplement an pymodbus, der
  Schreibzugriff schlug fehl und riss die Verbindung mit.
* Einstellbereiche der Heizkreis- und Pufferparameter am Gerät nachgemessen:
  Frostschutz −10 bis 20 °C, Außentemperatur-Schwellen −20 bis 50 °C,
  Puffer-Temperaturdifferenz 2 bis 80 °C. Die Doku führt diese Grenzen als
  Realwerte, verliert aber die Minuszeichen; die alten Bereiche −30 und 0 bis
  120 waren zu weit.
* Zähler über 32767 (Betriebsstunden, kWh) wurden negativ angezeigt, mit
  Rückfall in der Langzeitstatistik.
* War Boiler 01 abgewählt, löschte jeder Start die Zirkulationssensoren und
  40601 mit, die an dessen Gerät hängen, und legte sie neu an; Umbenennungen
  und Bereiche gingen dabei verloren.
* Die Brennstoffauswahl hieß „weiches Holz / hartes Holz“; laut Handbuch und
  Bediengerät sind es „Scheitholz trocken / Scheitholz feucht“ (Wassergehalt
  unter/über 15 %). Die internen Schlüssel bleiben, Automationen laufen weiter.
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
