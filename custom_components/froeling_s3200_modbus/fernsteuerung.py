"""Kesselfernsteuerung mit Heartbeat (Register 48001-48046).

Was die Anlage tut, laut B1200522 Kap. 2.6 und am Geraet am 09.09.2026
gemessen (Befund zur Parameteranalyse, Abschnitte 4, 4a und 7b):

* Ein einzelner FC06-Schreibzugriff auf 48001-48018 (HK-Vorlauf-Soll),
  48019-48026 (Boiler-Soll) oder 48029-48046 (HK-Freigabe) schaltet die
  Sollwertvorgabe **global fuer alle vorhandenen Heizkreise und Boiler** ein,
  mit dem aktuellen Inhalt aller uebrigen Register. Wirkung nach 1 s.
* Bleibt mehr als zwei Minuten jeder Schreibzugriff aus, faellt die Anlage in
  ihre eigene Regelung zurueck (gemessen: 54-129 s). Die Register lesen danach
  weiter den letzten angenommenen Wert -- Lesen sagt nichts ueber den Zustand.
* Ein Schaltwechsel (Freigabe 0<->1, Boiler-Soll 0<->>0) wird fruehestens zehn
  Minuten nach dem letzten angenommenen Wechsel uebernommen; sonst antwortet
  die Anlage mit Echo 0xFFFF. **Auch der verworfene Zugriff zaehlt als
  Schreibzugriff und haelt die Vorgabe am Leben** -- wer innerhalb der Sperre
  "aus" schreibt, schaltet den Heizkreis zwei weitere Minuten *ein*.
* FC16 kann die Anlage nicht (Exception 0x90/02): nur einzelne FC06.

Daraus folgt der Aufbau: Die Entitaeten auf den Fernsteuerregistern sind nur
noch **Vorgabewerte** und schreiben nichts selbst. Eine Instanz dieser Klasse
je Config-Entry haelt sie, und solange die Regelung bei Home Assistant liegt
(``master == "home_assistant"``), sendet sie alle 60 s den vollstaendigen Satz
aller vorhandenen Instanzen -- nie nur ein einzelnes Register, denn das
Protokoll kennt keinen Wert "dieser Kreis bleibt bei der Kesselregelung".
Zurueck zum Kessel heisst: aufhoeren zu schreiben und zwei Minuten warten.
Nie "Freigabe 0" nachschieben, das waere innerhalb der Sperre genau verkehrt.

Dieses Modul kennt keine HA-Entitaetsklassen -- nur hass, den Timer und den
Coordinator -- damit sich die Logik ohne Plattformen testen laesst.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from .modbus import VERWORFEN
from .registertabelle import TABELLE, Register

_LOGGER = logging.getLogger(__name__)

MASTER_KESSEL = "kessel"
MASTER_HA = "home_assistant"
MASTER_OPTIONEN = (MASTER_KESSEL, MASTER_HA)

#: Abstand der Heartbeats. 60 s fest: Ein Schreibzugriff kann hinter einem
#: laufenden Leseblock bis zu 9 s warten (timeout 3 s x retries 2), naeher an
#: die zwei Minuten heranzugehen ist deshalb kein Sicherheitsabstand.
HEARTBEAT = timedelta(seconds=60)
#: Danach faellt die Anlage ohne Schreibzugriff zurueck (Doku; gemessen 54-129 s).
FENSTER = timedelta(seconds=120)
#: Mindestschaltdauer der Anlage. Gemessen: "Freigabe 0" fuenf Minuten nach
#: "Freigabe 1" verworfen, nach 10 min 14 s angenommen.
SPERRE = timedelta(minutes=10)

#: Nummernkreise der drei Registerarten (B1200522 Kap. 3.5).
HK_SOLL = range(48001, 48019)
BOILER_SOLL = range(48019, 48027)
HK_FREIGABE = range(48029, 48047)

#: Neutraler Rohwert, wenn keine Vorgabe gesetzt ist: HK-Soll 0 heisst
#: "Heizkurve der Regelung, nur ohne Aussentemperatur-Heizgrenze",
#: Freigabe 1 heisst "Heizkreis laeuft". Der Boiler hat keinen festen
#: Neutralwert, siehe ``boilerwert``.
NEUTRAL_HK_SOLL = 0
NEUTRAL_HK_FREIGABE = 1


def gewuenschte_boilertemperatur(instanz: int) -> int:
    """Register "Gewuenschte Boilertemperatur" je Boiler: 41632 fuer Boiler 1,
    danach alle 30 Register. Boiler-Soll = dieser Wert ergibt Ladestart bei
    "Nachladen, wenn unter" und Stopp bei "Gewuenscht" -- also das, was die
    Anlage ohne Fernsteuerung ohnehin taete."""
    return 41632 + 30 * (instanz - 1)


def _art(register: int) -> int:
    """Sendereihenfolge: Boiler-Soll, HK-Soll, HK-Freigabe.

    Der erste Schreibzugriff aktiviert die Vorgabe mit den *alten* Inhalten
    der uebrigen Register. Die Freigabe kommt deshalb zuletzt: Bis dahin
    stehen die Sollwerte, die sie freigibt.
    """
    if register in BOILER_SOLL:
        return 0
    if register in HK_SOLL:
        return 1
    return 2


def ist_schaltwechsel(register: int, alt: int, neu: int) -> bool:
    """Freigabe 0<->1, Boiler-Soll 0<->>0. Ein HK-Soll 56 -> 58 ist keiner."""
    if register in HK_FREIGABE:
        return bool(alt) != bool(neu)
    if register in BOILER_SOLL:
        return (alt == 0) != (neu == 0)
    return False


def vorhandene_instanzen(konfiguration: dict[str, Any]) -> set[str]:
    """Instanzkennungen (hk01, boiler02, ...), fuer die die Vorgabe gilt.

    Vorhanden ist eine Instanz, wenn ihre Gruppe im Entry angehakt ist
    **oder** die Erkennung sie als ``vorhanden`` eingestuft hat. Letzteres
    bewusst zusaetzlich: Die Vorgabe gilt global, und fuer einen Heizkreis,
    den der Nutzer in HA nur ausgeblendet hat -- oder fuer HK 3 bis 18 und
    Boiler 2 bis 8, fuer die es gar keine Entitaeten gibt --, naehme die
    Anlage sonst den Registerinhalt 0 und schaltete ihn ab.

    Der Befund liegt im Entry unter ``erkannt["vorschlag"]`` (Instanz ->
    Zustand), so schreibt ihn der Config-Flow.
    """
    erkannt = konfiguration.get("erkannt") or {}
    vorschlag = erkannt.get("vorschlag") or {}
    instanzen = {k for k, v in vorschlag.items() if v == "vorhanden"}
    instanzen |= {k for k, v in konfiguration.items() if v is True and (k.startswith("hk") or k.startswith("boiler"))}
    return instanzen


def satz_zeilen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """Die Fernsteuerzeilen aller vorhandenen Instanzen, in Sendereihenfolge.

    Bewusst ohne ``freigegeben``-Filter: Freigegeben sind nur die fuenf
    Zeilen der 0.4.0 (HK 1/2, Boiler 1), und nur die werden Entitaeten. Fuer
    HK 3 bis 18 und Boiler 2 bis 8 gehen die neutralen Werte mit, sobald die
    Erkennung sie als vorhanden fuehrt.
    """
    instanzen = vorhandene_instanzen(konfiguration)
    zeilen = [
        z for z in TABELLE
        if z.kategorie == "fernsteuerung" and z.plattform and z.instanzkennung in instanzen
    ]
    return tuple(sorted(zeilen, key=lambda z: (_art(z.nummer), z.nummer)))


def boilerregister_zum_lesen(konfiguration: dict[str, Any]) -> tuple[Register, ...]:
    """"Gewuenschte Boilertemperatur" jedes Boilers im Satz -- muss gelesen
    werden, auch wenn die Boilergruppe nicht angehakt ist, sonst gibt es
    keinen neutralen Boiler-Sollwert. Wird keine Entitaet."""
    nummern = {
        gewuenschte_boilertemperatur(z.instanz)
        for z in satz_zeilen(konfiguration) if z.nummer in BOILER_SOLL and z.instanz
    }
    return tuple(z for z in TABELLE if z.typ == "holding" and z.nummer in nummern)


class Fernsteuerung:
    """Vorgaben, Heartbeat und Sperrenverwaltung einer Anlage."""

    def __init__(self, hass: HomeAssistant, coordinator, konfiguration: dict[str, Any]) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._zeilen = satz_zeilen(konfiguration)
        #: Ohne Erkennungsbefund zaehlt fuer "vorhanden" nur der Haken im
        #: Entry. Eine real vorhandene, aber abgewaehlte Instanz bekaeme dann
        #: bei Master HA den Registerinhalt 0 -- HK aus, Ladung aus. Wird beim
        #: Einschalten gemeldet.
        self._ohne_befund = "erkannt" not in konfiguration
        #: "kessel" (Vorgabe) oder "home_assistant". Nach jedem Start "kessel":
        #: Home Assistant darf die Vorgabe nach einem Neustart nicht
        #: kommentarlos wieder einschalten (Befund 7b, Punkte 6 und 7).
        self.master = MASTER_KESSEL
        #: Register -> Rohwert, vom Nutzer gesetzt (Faktor 2 bei Temperaturen,
        #: 0/1 bei der Freigabe). Fehlt ein Register, gilt der neutrale Wert.
        self.vorgaben: dict[int, int] = {}
        self.letzter_erfolg: datetime | None = None
        self.letzter_fehler: str | None = None
        #: Je Schaltregister der Zeitpunkt des letzten **angenommenen** Wechsels.
        self.letzter_wechsel: dict[int, datetime] = {}
        #: Zuletzt von der Anlage angenommener Wert je Register.
        self.gesendet: dict[int, int] = {}
        #: Wechsel, die auf das Ende der Zehn-Minuten-Sperre warten.
        self.ausstehend: dict[int, int] = {}
        #: Von der Anlage verworfene Schreibzugriffe seit dem Start.
        self.verworfen = 0
        #: Zwei Minuten ohne Erfolg bei Master HA: Die Anlage regelt wieder
        #: selbst, obwohl HA "Home Assistant" zeigt.
        self.fenster_ueberschritten = False
        #: Zuletzt gelesene "Gewuenschte Boilertemperatur" je Boilerinstanz.
        #: Faellt der Block einmal aus, gilt der letzte bekannte Wert weiter --
        #: nie 0, denn 0 hiesse "Ladung aus" und saesse danach zehn Minuten
        #: in der Sperre fest.
        self._boiler_gewuenscht: dict[int, int] = {}
        #: Nach dem Entladen: kein Satz mehr, auch nicht aus einem Timer, der
        #: gerade noch feuert, waehrend der Coordinator den Socket schliesst.
        self._beendet = False
        #: Leerer Satz schon gemeldet -- die Warnung kommt beim Uebergang,
        #: nicht bei jedem Heartbeat.
        self._leer_gemeldet = False
        self._timer_abmelden: Callable[[], None] | None = None
        self._ablauf_abmelden: Callable[[], None] | None = None
        self._zuhoerer: list[Callable[[], None]] = []
        #: Ein Vorgabewechsel sendet sofort, der Timer parallel dazu: Beide
        #: nacheinander, sonst verarbeiten sie ihre Ergebnisse durcheinander.
        self._sendung = asyncio.Lock()

    # ------------------------------------------------------------------ Satz

    @property
    def zeilen(self) -> tuple[Register, ...]:
        return self._zeilen

    @property
    def register(self) -> list[int]:
        return [z.nummer for z in self._zeilen]

    def _boiler_nachlesen(self) -> None:
        """Uebernimmt die aktuell gelesenen "Gewuenschte Boilertemperatur"-Werte."""
        for zeile in self._zeilen:
            if zeile.nummer in BOILER_SOLL and zeile.instanz:
                roh = self._coordinator.rohwert(gewuenschte_boilertemperatur(zeile.instanz))
                if roh is not None and roh not in (0, 0xFFFF):
                    self._boiler_gewuenscht[zeile.instanz] = roh

    def _registerinhalt(self, register: int) -> int | None:
        """Was die Anlage fuer dieses Fernsteuerregister zurueckliest (FC03,
        zuletzt angenommener Wert) -- falls der Coordinator es liest."""
        roh = self._coordinator.rohwert(register)
        return None if roh is None or roh == 0xFFFF else roh

    def boilerwert(self, register: int) -> int | None:
        """Neutraler Boiler-Sollwert: die zuletzt bekannte "Gewuenschte
        Boilertemperatur", sonst der zuletzt angenommene Wert, sonst der
        Registerinhalt (> 0), sonst None.

        None heisst: Das Register bleibt aus dem Satz -- die Anlage nutzt
        dann ihren Registerinhalt. Ein erfundener Wert 0 waere "Ladung aus",
        und die Rueckkehr zum echten Wert saesse danach zehn Minuten in der
        Sperre.
        """
        instanz = register - BOILER_SOLL.start + 1
        self._boiler_nachlesen()
        if instanz in self._boiler_gewuenscht:
            return self._boiler_gewuenscht[instanz]
        gesendet = self.gesendet.get(register)
        if gesendet is not None and gesendet != 0:
            return gesendet
        inhalt = self._registerinhalt(register)
        if inhalt is not None and inhalt > 0:
            return inhalt
        return None

    def neutralwert(self, register: int) -> int | None:
        """Rohwert, der die Anlage so regeln laesst, wie sie es ohne
        Fernsteuerung taete -- so gut das Protokoll das zulaesst."""
        if register in HK_FREIGABE:
            return NEUTRAL_HK_FREIGABE
        if register in BOILER_SOLL:
            return self.boilerwert(register)
        return NEUTRAL_HK_SOLL

    def wert(self, register: int) -> int | None:
        """Rohwert, der fuer dieses Register gesendet wird: Vorgabe oder
        neutral. None nur beim Boiler ohne lesbare Gewuenscht-Temperatur."""
        if register in self.vorgaben:
            return self.vorgaben[register]
        return self.neutralwert(register)

    def ist_neutral(self, register: int) -> bool:
        return register not in self.vorgaben

    def satz(self, jetzt: datetime | None = None) -> tuple[list[tuple[int, int]], list[str]]:
        """Die Paare (Register, Rohwert) fuer einen Heartbeat, dazu die
        Register, die ohne brauchbaren Wert aus dem Satz bleiben.

        Ein Schaltwechsel innerhalb der Sperre geht nicht mit: Die Anlage
        wuerde ihn verwerfen -- und bis dahin muss der *alte* Zustand weiter
        gesendet werden, damit die Vorgabe am Leben bleibt. Der neue Wert
        wartet in ``ausstehend``.
        """
        jetzt = jetzt or dt_util.utcnow()
        paare: list[tuple[int, int]] = []
        fehlend: list[str] = []
        for zeile in self._zeilen:
            nummer = zeile.nummer
            soll = self.wert(nummer)
            if soll is None:
                inhalt = self._registerinhalt(nummer)
                fehlend.append(
                    f"Boiler {zeile.instanz}: gewuenschte Boilertemperatur "
                    f"(Register {gewuenschte_boilertemperatur(zeile.instanz)}) nicht lesbar, "
                    f"Anlage nutzt den Registerinhalt {'unbekannt' if inhalt is None else inhalt}"
                )
                continue
            alt = self.gesendet.get(nummer)
            gesperrt_seit = self.letzter_wechsel.get(nummer)
            if (
                alt is not None and ist_schaltwechsel(nummer, alt, soll)
                and gesperrt_seit is not None and jetzt - gesperrt_seit < SPERRE
            ):
                self.ausstehend[nummer] = soll
                paare.append((nummer, alt))
                continue
            # Nicht gesperrt. Wartet hier noch ein anderer Wert, hat der Nutzer
            # ihn zurueckgenommen; wartet derselbe, ist das der erneute Versuch
            # nach einem verworfenen Zugriff -- _auswerten raeumt ihn bei
            # Erfolg weg.
            if self.ausstehend.get(nummer) != soll:
                self.ausstehend.pop(nummer, None)
            paare.append((nummer, soll))
        return paare, fehlend

    # ------------------------------------------------------------- Zustand

    def aktiv(self, jetzt: datetime | None = None) -> bool:
        """Wirkt die Vorgabe gerade -- nach dem, was HA weiss?

        Master HA und ein Erfolg innerhalb des Zwei-Minuten-Fensters. Was
        die Anlage wirklich tut, zeigen nur ihre Istwerte (31032/31062,
        Coils 1030/1060); HA sieht die zwei Minuten Latenz nicht.
        """
        if self.master != MASTER_HA or self.letzter_erfolg is None:
            return False
        jetzt = jetzt or dt_util.utcnow()
        return jetzt - self.letzter_erfolg < FENSTER

    def attribute(self) -> dict[str, Any]:
        """Diagnose fuer die Auswahlentitaet."""
        return {
            "letzter_erfolg": self.letzter_erfolg.isoformat() if self.letzter_erfolg else None,
            "letzter_fehler": self.letzter_fehler,
            "ausstehend": [f"{r}={w}" for r, w in sorted(self.ausstehend.items())],
            "verworfen": self.verworfen,
            "fenster_ueberschritten": self.fenster_ueberschritten,
            "register": self.register,
        }

    @callback
    def zuhoerer_hinzufuegen(self, funktion: Callable[[], None]) -> Callable[[], None]:
        """Entitaeten melden sich an, um nach jedem Satz ihren Zustand zu schreiben."""
        self._zuhoerer.append(funktion)

        def _entfernen() -> None:
            if funktion in self._zuhoerer:
                self._zuhoerer.remove(funktion)

        return _entfernen

    def _benachrichtigen(self) -> None:
        for funktion in list(self._zuhoerer):
            funktion()

    # ------------------------------------------------------------ Steuerung

    async def async_vorgabe_setzen(self, register: int, rohwert: int) -> None:
        """Eine Vorgabe merken. Bei Master HA sofort senden, nicht erst beim
        naechsten Heartbeat -- der Nutzer will die Wirkung jetzt sehen."""
        self.vorgaben[register] = rohwert
        if self.master == MASTER_HA:
            await self.async_senden()
        else:
            self._benachrichtigen()

    def vorgabe_wiederherstellen(self, register: int, rohwert: int) -> None:
        """Nach einem Neustart (RestoreEntity). Kein Schreibzugriff: Master ist
        nach dem Start immer Kessel."""
        self.vorgaben[register] = rohwert

    async def async_start(self) -> None:
        """Regelung an Home Assistant: sofort ein Satz, dann alle 60 s."""
        if self.master == MASTER_HA or self._beendet:
            return
        self.master = MASTER_HA
        self.fenster_ueberschritten = False
        _LOGGER.info(
            "Fernsteuerung: Regelung uebernimmt Home Assistant, Register %s werden alle %d s gesendet",
            self.register, int(HEARTBEAT.total_seconds()),
        )
        if self._ohne_befund:
            _LOGGER.warning(
                "Fernsteuerung: Anlage nie eingelesen -- der Satz umfasst nur die angehakten "
                "Anlagenteile (%s). Ein vorhandener, aber abgewaehlter Heizkreis oder Boiler "
                "bekaeme Registerinhalt 0 (aus). Bitte unter Optionen \"Anlage neu einlesen\".",
                ", ".join(sorted({z.instanzkennung for z in self._zeilen})),
            )
        self._timer_abmelden = async_track_time_interval(
            self._hass, self._heartbeat, HEARTBEAT, name="Froeling Fernsteuerung"
        )
        await self.async_senden()

    async def async_stop(self) -> None:
        """Regelung zurueck an den Kessel: Timer weg, nichts mehr schreiben.

        Bewusst kein "Freigabe 0" oder Boiler-Soll 0 zum Abschluss: Innerhalb
        der Zehn-Minuten-Sperre wuerde die Anlage das verwerfen und die Vorgabe
        trotzdem um zwei Minuten verlaengern (gemessen 09.09.2026 16:16). Der
        einzige sichere Weg zurueck ist, nicht mehr zu schreiben.
        """
        if self.master == MASTER_KESSEL:
            return
        self.master = MASTER_KESSEL
        self._timer_beenden()
        self.ausstehend.clear()
        self.fenster_ueberschritten = False
        _LOGGER.info(
            "Fernsteuerung: Regelung zurueck an den Kessel -- die Anlage faellt "
            "in zwei Minuten in ihre eigene Regelung zurueck"
        )
        self._benachrichtigen()

    @callback
    def _timer_beenden(self) -> None:
        if self._timer_abmelden is not None:
            self._timer_abmelden()
            self._timer_abmelden = None
        if self._ablauf_abmelden is not None:
            self._ablauf_abmelden()
            self._ablauf_abmelden = None

    @callback
    def abmelden(self) -> None:
        """Beim Entladen des Entry, **vor** dem Schliessen des Coordinators.

        Danach schreibt nichts mehr -- auch kein Satz, der gerade noch auf die
        Sperre wartet: Der wuerde sonst nach ``client.close()`` den Socket neu
        oeffnen und die Vorgabe reaktivieren. Die Anlage regelt nach zwei
        Minuten wieder selbst.
        """
        self._beendet = True
        self._timer_beenden()

    async def _heartbeat(self, _jetzt: datetime) -> None:
        await self.async_senden()

    def _laeuft(self) -> bool:
        return self.master == MASTER_HA and not self._beendet

    async def async_senden(self) -> None:
        """Einen vollstaendigen Satz schreiben und die Antworten auswerten."""
        if not self._laeuft():
            return
        async with self._sendung:
            if not self._laeuft():   # waehrend des Wartens umgeschaltet oder entladen
                return
            jetzt = dt_util.utcnow()
            paare, fehlend = self.satz(jetzt)
            if not paare:
                self.letzter_fehler = fehlend[0] if fehlend else "keine Fernsteuerregister im Satz"
                if not self._leer_gemeldet:
                    _LOGGER.warning("Fernsteuerung: nichts gesendet -- %s", self.letzter_fehler)
                    self._leer_gemeldet = True
                self._fenster_pruefen(jetzt)
                self._benachrichtigen()
                return
            self._leer_gemeldet = False
            ergebnis = await self._coordinator.schreibe_satz(paare)
            # Waehrend des Schreibens auf Kessel gestellt oder entladen: Was
            # die Anlage angenommen hat, bleibt Wissen (gesendet, Sperre) --
            # aber ausstehend und Fenster gehoeren zum beendeten Lauf und
            # wurden von async_stop gerade geleert.
            laeuft = self._laeuft()
            self._auswerten(paare, ergebnis, jetzt, laeuft, fehlend)
            if laeuft:
                self._fenster_pruefen(dt_util.utcnow())
            self._benachrichtigen()

    def _auswerten(self, paare: list[tuple[int, int]], ergebnis: dict[int, str | None],
                   jetzt: datetime, laeuft: bool, fehlend: list[str]) -> None:
        erfolg = False
        fehler: list[str] = list(fehlend)
        for nummer, wert in paare:
            err = ergebnis.get(nummer)
            if err is None:
                alt = self.gesendet.get(nummer)
                if alt is not None and ist_schaltwechsel(nummer, alt, wert):
                    self.letzter_wechsel[nummer] = jetzt
                self.gesendet[nummer] = wert
                if self.ausstehend.get(nummer) == wert:
                    # Der wartende Wechsel ist durch. Ging stattdessen der
                    # alte Wert raus (Sperre laeuft noch), wartet er weiter.
                    del self.ausstehend[nummer]
                erfolg = True
                continue
            if err == VERWORFEN:
                # Die Anlage hat den Wert nicht uebernommen, der Zugriff hielt
                # die Vorgabe aber am Leben (gemessen 09.09.2026 16:16:37) --
                # fuer das Fenster zaehlt er als Erfolg. Der alte Wert bleibt
                # "gesendet"; fehlt er (erster Satz nach dem Start), gilt das,
                # was die Anlage zurueckliest: FC03 liefert den zuletzt
                # angenommenen Wert.
                self.verworfen += 1
                erfolg = True
                if nummer not in self.gesendet:
                    roh = self._coordinator.rohwert(nummer)
                    if roh is not None:
                        self.gesendet[nummer] = roh
                if wert == self.gesendet.get(nummer):
                    # Derselbe Wert wie zuletzt angenommen -- nichts wartet.
                    _LOGGER.debug("Fernsteuerung: Register %s = %s verworfen, Wert unveraendert", nummer, wert)
                elif not laeuft:
                    _LOGGER.debug("Fernsteuerung: Register %s = %s verworfen, Lauf beendet", nummer, wert)
                elif self.ausstehend.get(nummer) != wert:
                    self.ausstehend[nummer] = wert
                    _LOGGER.warning(
                        "Fernsteuerung: Register %s = %s von der Anlage verworfen "
                        "(Mindestschaltdauer 10 min), wird beim naechsten Heartbeat "
                        "erneut versucht", nummer, wert,
                    )
                else:
                    _LOGGER.debug("Fernsteuerung: Register %s = %s weiterhin verworfen", nummer, wert)
                continue
            fehler.append(f"Register {nummer}: {err}")
        if erfolg:
            self.letzter_erfolg = jetzt
            if laeuft:
                self._ablauf_planen()
        if fehler:
            self.letzter_fehler = fehler[0] if len(fehler) == 1 else f"{fehler[0]} (und {len(fehler) - 1} weitere)"
            _LOGGER.debug("Fernsteuerung: %s", self.letzter_fehler)
        elif erfolg:
            self.letzter_fehler = None

    def _ablauf_planen(self) -> None:
        """Einmaliger Aufruf genau am Ende des Zwei-Minuten-Fensters, damit
        "Fernsteuerung aktiv" dann auf aus geht -- und nicht erst beim
        naechsten Heartbeat oder Lesedurchlauf bis zu 60 s spaeter."""
        if self._ablauf_abmelden is not None:
            self._ablauf_abmelden()
        self._ablauf_abmelden = async_call_later(
            self._hass, FENSTER.total_seconds(), self._fenster_abgelaufen
        )

    @callback
    def _fenster_abgelaufen(self, _jetzt: datetime) -> None:
        self._ablauf_abmelden = None
        self._benachrichtigen()

    def _fenster_pruefen(self, jetzt: datetime) -> None:
        """Warnt einmal, wenn die Anlage laenger als zwei Minuten nichts
        Gueltiges bekam -- sie regelt dann wieder selbst, waehrend HA
        "Home Assistant" zeigt. Zurueck beim naechsten Erfolg."""
        ueberschritten = self.letzter_erfolg is None or jetzt - self.letzter_erfolg >= FENSTER
        if ueberschritten and not self.fenster_ueberschritten:
            if self.letzter_erfolg is None:
                _LOGGER.warning(
                    "Fernsteuerung: noch kein erfolgreicher Satz seit dem Einschalten (%s) "
                    "-- die Anlage regelt weiter selbst, obwohl Home Assistant als "
                    "Regelung gewaehlt ist",
                    self.letzter_fehler or "unbekannter Fehler",
                )
            else:
                _LOGGER.warning(
                    "Fernsteuerung: seit mehr als zwei Minuten kein erfolgreicher Schreibzugriff "
                    "(%s) -- die Anlage regelt wieder selbst, obwohl Home Assistant als "
                    "Regelung gewaehlt ist",
                    self.letzter_fehler or "unbekannter Fehler",
                )
        elif not ueberschritten and self.fenster_ueberschritten:
            _LOGGER.info("Fernsteuerung: Schreibzugriffe erreichen die Anlage wieder")
        self.fenster_ueberschritten = ueberschritten
