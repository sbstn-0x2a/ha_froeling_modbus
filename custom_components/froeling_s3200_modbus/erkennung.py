"""Erkennung der Anlagenteile aus einem Vollscan.

Reine Funktionen ohne Home-Assistant-Abhängigkeit: ``scan`` liest alle
Register der Tabelle blockweise (nur FC01-FC04), ``auswerten`` leitet daraus
ab, welche Instanzen (Heizkreis 2, Boiler 1, Puffer 1, ...) die Anlage hat und
welche Register keinen brauchbaren Wert liefern.

Die Regeln stammen aus dem Befund vom 09.09.2026 (Abschnitt 7). Es gibt kein
Register, das das Anlagenart-Menü des Bediengeräts abbildet; alles hier ist
Ableitung aus Istwerten und Parametern. Deshalb liefert die Auswertung
Vorschläge mit Beleg, und der Nutzer bestätigt sie im Config-Flow.

Was am Gerät gemessen wurde:
* Nicht konfigurierte Instanzen lesen Istwert 0 und tragen den Werksvorgabe-
  Parametersatz. Sie antworten **nicht** mit -1.
* Ein nicht belegter Fühlereingang liest 127,0 °C (Roh 254) oder -49 °C
  (Roh -98) bei Faktor 2.
* -1 (0xFFFF) liefern nur Register, die die Firmware nicht kennt.
* Zähler nicht vorhandener oder nicht angebundener Teile bleiben bei 0,
  während die Betriebsstunden (30021) längst dreistellig sind.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .modbus import read_coils_sync, read_discrete_sync, read_holding_sync, read_input_sync
from .registers import bloecke
from .registertabelle import TABELLE, WERTELISTEN, Register

VORHANDEN = "vorhanden"
NICHT_VORHANDEN = "nicht_vorhanden"
UNSICHER = "unsicher"

#: Rohwerte, die bei Faktor 2 einen nicht belegten Fühlereingang bedeuten.
FEHLERWERTE = {254, -98}
#: Ab so vielen Betriebsstunden gilt ein Zähler mit 0 als nicht belegt. Ein
#: Tag reicht: Danach haben Saugturbine, Rüttler und WOS sicher gelaufen.
#: Zu früh eingestuft ist harmlos, das nächste Einlesen holt den Zähler
#: zurück, sobald er zählt.
MINDEST_BETRIEBSSTUNDEN = 24
#: Fühler- und Pumpenzuordnungen ab dieser Nummer zeigen auf ein
#: Erweiterungsmodul, das es nicht gibt (Kernmodul: 1-16).
IO_PLATZHALTER_AB = 17

#: Instanzen, die es an jeder Anlage gibt.
IMMER = ("controller", "kessel", "austragung")


@dataclass(slots=True)
class Instanzbefund:
    zustand: str
    beleg: str


@dataclass(slots=True)
class Befund:
    """Ergebnis der Auswertung -- serialisierbar für den Config-Entry."""

    instanzen: dict[str, Instanzbefund] = field(default_factory=dict)
    #: Registernummer -> Grund, warum es keinen brauchbaren Wert liefert.
    tot: dict[int, str] = field(default_factory=dict)
    fehlende_bloecke: list[str] = field(default_factory=list)

    def vorschlag(self) -> dict[str, str]:
        return {k: v.zustand for k, v in self.instanzen.items()}

    def belege(self) -> dict[str, str]:
        return {k: v.beleg for k, v in self.instanzen.items()}


def vorzeichen(roh: int) -> int:
    return roh - 65536 if roh > 32767 else roh


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------

def scan(client, unit_id: int, pause: float = 0.02) -> tuple[dict[int, int], list[str]]:
    """Liest alle Register der Tabelle blockweise. Schreibt nichts.

    Blockierend, gehört in den Executor. Rückgabe: Werte je Registernummer
    (Coils unter ihrer Adresse, Discrete Inputs unter der 1xxxx-Nummer) und
    die Liste der Blöcke, die nicht antworteten.
    """
    werte: dict[int, int] = {}
    fehler: list[str] = []
    nummern = defaultdict(list)
    for z in TABELLE:
        nummern[z.typ].append(z.nummer)
    # Lücken bis 100 Register werden mitgelesen: Für nicht gelistete Adressen
    # liefert der Kessel -1 statt einer Ablehnung, und ein Block kostet
    # dieselbe Zeit wie zwei halbe. Am Gerät: ~60 Anfragen, rund 6 s.
    laeufe = (
        ("input", read_input_sync, 30001, 100, 100),
        ("holding", read_holding_sync, 40001, 100, 100),
        ("coil", read_coils_sync, 0, 100, 100),
        # Discrete: keine Lücke erlaubt, count > 4 läuft am Gerät in einen Timeout.
        ("discrete", read_discrete_sync, 10001, 1, 4),
    )
    for typ, lese, basis, luecke, block in laeufe:
        for start, anzahl in bloecke(nummern[typ], max_luecke=luecke, max_block=block):
            res, err = lese(client, unit_id, start - basis, anzahl)
            if err or res is None:
                fehler.append(f"{typ} {start}+{anzahl}: {err}")
                continue
            if typ in ("coil", "discrete"):
                for i, bit in enumerate(res.bits[:anzahl]):
                    werte[start + i] = int(bit)
            else:
                for i, roh in enumerate(res.registers):
                    werte[start + i] = roh
            time.sleep(pause)
    return werte, fehler


# --------------------------------------------------------------------------
# Auswerten
# --------------------------------------------------------------------------

def _wert(werte: dict[int, int], nummer: int) -> int | None:
    roh = werte.get(nummer)
    return None if roh is None else vorzeichen(roh)


def _temperatur(werte, zeile: Register) -> str:
    v = _wert(werte, zeile.nummer)
    if v is None:
        return "?"
    return f"{v / zeile.faktor:.1f} °C".replace(".", ",")


def _ist_temperatur(zeile: Register) -> bool:
    return zeile.typ == "input" and zeile.einheit == "°C" and zeile.faktor == 2


def _istwerte(zeilen) -> list[Register]:
    return [z for z in zeilen if _ist_temperatur(z)]


def _parametersatz(werte, zeilen) -> dict[str, int]:
    return {
        z.schluessel: werte[z.nummer]
        for z in zeilen
        if z.typ == "holding" and z.nummer in werte and not (48001 <= z.nummer <= 48064)
    }


def _io_platzhalter(werte, zeilen) -> bool | None:
    """True, wenn alle Fühler-/Pumpenzuordnungen auf ein fehlendes Modul zeigen."""
    zuordnungen = [
        _wert(werte, z.nummer) for z in zeilen
        if z.typ == "holding" and ("fuehlereingang" in z.schluessel or "pumpenausgang" in z.schluessel)
    ]
    zuordnungen = [v for v in zuordnungen if v is not None]
    if not zuordnungen:
        return None
    return all(v >= IO_PLATZHALTER_AB for v in zuordnungen)


def _instanzen_mit_nummer(werte, familie: str, befund: Befund) -> None:
    """R1, R2, R8 für Heizkreise, Boiler und Puffer."""
    je_instanz: dict[int, list[Register]] = defaultdict(list)
    for z in TABELLE:
        if z.familie == familie and z.instanz is not None:
            je_instanz[z.instanz].append(z)

    leer: list[dict[str, int]] = []      # Parametersätze von Instanzen ohne Istwert
    zustand: dict[int, tuple[str, str]] = {}
    for inst, zeilen in sorted(je_instanz.items()):
        temperaturen = _istwerte(zeilen)
        werte_ist = [_wert(werte, z.nummer) for z in temperaturen]
        bekannt = [v for v in werte_ist if v is not None]
        if not bekannt:
            zustand[inst] = (UNSICHER, "Istwerte nicht gelesen")
            continue
        echte = [v for v in bekannt if v != 0 and v not in FEHLERWERTE]
        if not echte:
            leer.append(_parametersatz(werte, zeilen))
            grund = "Istwerte 0" if all(v == 0 for v in bekannt) else "Fühler nicht belegt"
            zustand[inst] = (NICHT_VORHANDEN, grund)
            continue
        beleg = ", ".join(f"{z.name_de} {_temperatur(werte, z)}" for z in temperaturen[:3]
                          if _wert(werte, z.nummer) not in FEHLERWERTE and _wert(werte, z.nummer) != 0)
        zustand[inst] = (VORHANDEN, beleg)

    # R2: Werksvorgabe als Gegenprobe. Der häufigste Parametersatz der leeren
    # Instanzen ist die Werksvorgabe; trägt ihn auch eine "vorhandene"
    # Instanz, ist sie nur unsicher (HK1-Fall: Istwert vorhanden, aber im
    # Anlagenart-Menü nicht angehakt).
    if leer:
        schluessel = set.intersection(*(set(s) for s in leer)) if len(leer) > 1 else set(leer[0])
        vektoren = Counter(tuple(sorted((k, s[k]) for k in schluessel)) for s in leer)
        werksvorgabe = dict(vektoren.most_common(1)[0][0]) if vektoren else {}
    else:
        werksvorgabe = {}

    for inst, zeilen in sorted(je_instanz.items()):
        z, beleg = zustand[inst]
        if z == VORHANDEN and werksvorgabe:
            eigener = _parametersatz(werte, zeilen)
            if all(eigener.get(k) == v for k, v in werksvorgabe.items()):
                z, beleg = UNSICHER, beleg + "; Parameter auf Werksvorgabe"
        if z == VORHANDEN and _io_platzhalter(werte, zeilen):
            z, beleg = UNSICHER, beleg + "; Fühler/Pumpen ohne Modul"
        if familie == "hk" and z == VORHANDEN:
            art = _wert(werte, 48047 + inst - 1)
            if art is not None:
                beleg += f", Betriebsart {WERTELISTEN['betriebsart'].get(art, art)}"
        befund.instanzen[f"{familie}{inst:02d}"] = Instanzbefund(z, beleg)


def _flags(werte, befund: Befund) -> None:
    """R7 und R8 für Anlagenteile ohne Nummer."""
    def w(n):
        return _wert(werte, n)

    # E-Abscheider: Funktion freigegeben und Stundenzähler.
    if w(40389) == 1:
        std = w(30104)
        befund.instanzen["efilter"] = Instanzbefund(VORHANDEN, f"Funktion freigegeben, {std} h" if std else "Funktion freigegeben")
    elif w(40389) == 0:
        befund.instanzen["efilter"] = Instanzbefund(NICHT_VORHANDEN, "Funktion nicht freigegeben")

    # Zirkulationspumpe: Rücklauffühler vorhanden oder Pumpenausgang am Kernmodul.
    rl, pumpe = w(40603), w(40605)
    if rl == 1:
        befund.instanzen["zirkulation"] = Instanzbefund(VORHANDEN, "Rücklauffühler vorhanden")
    elif pumpe is not None and pumpe < IO_PLATZHALTER_AB:
        befund.instanzen["zirkulation"] = Instanzbefund(UNSICHER, f"Pumpenausgang {pumpe}, kein Rücklauffühler")
    elif pumpe is not None:
        befund.instanzen["zirkulation"] = Instanzbefund(NICHT_VORHANDEN, f"kein Rücklauffühler, Pumpenausgang {pumpe} = Platzhalter")

    # Solar: Kollektorfühler am Kernmodul?
    kollektor = w(42606)
    if kollektor is not None:
        if kollektor < IO_PLATZHALTER_AB:
            befund.instanzen["solar"] = Instanzbefund(UNSICHER, f"Kollektorfühler auf Eingang {kollektor}")
        else:
            befund.instanzen["solar"] = Instanzbefund(NICHT_VORHANDEN, f"Kollektorfühler auf Platzhalter {kollektor}")

    # Zweitkessel
    zk = w(40501)
    if zk is not None:
        befund.instanzen["zweitkessel"] = Instanzbefund(
            VORHANDEN if zk > 0 else NICHT_VORHANDEN, f"Welcher zweite Kessel = {zk}")

    for kennung in IMMER:
        beleg = ""
        if kennung == "kessel" and w(30021) is not None:
            beleg = f"{w(30021)} h Betriebsstunden"
        if kennung == "austragung" and w(30022) is not None:
            beleg = f"Füllstand {w(30022) / 207:.0f} %"
        befund.instanzen[kennung] = Instanzbefund(VORHANDEN, beleg)


def _tote_register(werte, befund: Befund) -> None:
    """R3, R4, R5, R6 -- nur für Zeilen, die eine Entität werden können."""
    betriebsstunden = _wert(werte, 30021) or 0
    zaehler_pruefbar = betriebsstunden > MINDEST_BETRIEBSSTUNDEN
    waermemenge = [_wert(werte, n) for n in (30085, 30086, 30171)]
    for z in TABELLE:
        if not z.freigegeben or z.plattform is None:
            continue
        v = _wert(werte, z.nummer)
        if v is None:
            continue
        if v == -1 and z.typ in ("input", "holding") and z.familie != "fehlerpuffer":
            befund.tot[z.nummer] = "Firmware kennt das Register nicht (−1)"
        elif _ist_temperatur(z) and v in FEHLERWERTE:
            befund.tot[z.nummer] = f"Fühler nicht belegt ({v / 2:.0f} °C)"
        elif zaehler_pruefbar and z.typ == "input" and v == 0 and (
            z.einheit == "h" or "betriebsstunden" in z.schluessel
            or "anzahl" in z.schluessel or "zaehler" in z.schluessel
        ) and z.nummer != 30021:
            befund.tot[z.nummer] = f"Zähler steht bei 0 nach {betriebsstunden} h"
        elif zaehler_pruefbar and z.nummer in (30085, 30086, 30171) and all(x == 0 for x in waermemenge):
            befund.tot[z.nummer] = "kein Wärmemengenzähler"
    # Tote Register nicht vorhandener Instanzen sind kein eigener Befund.
    nicht_da = {k for k, v in befund.instanzen.items() if v.zustand == NICHT_VORHANDEN}
    for z in TABELLE:
        if z.instanzkennung in nicht_da:
            befund.tot.pop(z.nummer, None)


def auswerten(werte: dict[int, int], fehlende_bloecke: list[str] | None = None) -> Befund:
    """Leitet aus den Rohwerten den Anlagenbefund ab."""
    befund = Befund(fehlende_bloecke=list(fehlende_bloecke or []))
    for familie in ("hk", "boiler", "puffer"):
        _instanzen_mit_nummer(werte, familie, befund)
    _flags(werte, befund)
    _tote_register(werte, befund)
    return befund
