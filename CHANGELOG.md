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
  auch Brennerstarts und Reinigungen Statistik, beide als
  `total_increasing`.
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
