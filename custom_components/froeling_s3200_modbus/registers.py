"""Registerlandkarte der Integration.

Die Listen enthalten jede Registernummer, die von irgendeiner Plattform gelesen
wird. Sie werden aus den Konstruktoraufrufen der Entitaeten abgeleitet;
tests/test_registers.py prueft, dass keine Adresse fehlt -- eine Luecke waere
sonst unsichtbar, die betroffene Entitaet bliebe schlicht leer. Daraus werden zusammenhaengende Bloecke gebildet, die der Coordinator mit
je einer Modbus-Anfrage liest.

Am Geraet gemessen (08.09.2026, Froeling SP Dual Compact):

    143 Einzelreads : 1645 ms
     18 Blockreads  :  348 ms

Zur Blockgroesse: Die Modbus-Dokumentation B1200522 nennt ausdruecklich
"maximal 122 Werte auf einmal", und Fehlercode 0x03 (Illegal Data Value) heisst
dort "Anzahl der auf einmal abgefragten Register ist zu hoch". Am Geraet
gemessen: FC=04 beantwortet 122 und lehnt 123 ab; FC=03 setzt die Grenze nicht
durch und liefert auch 125. MAX_BLOCK bleibt mit Abstand darunter.

Luecken innerhalb eines Blocks sind unproblematisch und ausdruecklich
vorgesehen: Laut Dokumentation liefert der Kessel fuer nicht gelistete Register
innerhalb des gueltigen Bereichs den Wert -1, statt die ganze Anfrage
abzulehnen.
"""

from __future__ import annotations

from .entitaeten import alle_zeilen

INPUT_BASE = 30001
HOLDING_BASE = 40001
DISCRETE_BASE = 10001

#: Groesste Registerzahl je Anfrage. Dokumentiertes Maximum ist 122.
MAX_BLOCK = 100

#: Groesste Luecke, die noch in denselben Block gezogen wird. Tauscht
#: ungenutzte Registerinhalte gegen weniger Anfragen.
MAX_LUECKE = 20

# Die Adressen kommen aus der Registertabelle: jede Zeile, die eine Entität
# werden kann. Vorher standen sie hier als handgepflegte Listen, abgeleitet
# aus den Konstruktoraufrufen der Plattformen.
INPUT_REGISTERS: tuple[int, ...] = tuple(sorted(z.nummer for z in alle_zeilen() if z.typ == "input"))
HOLDING_REGISTERS: tuple[int, ...] = tuple(sorted(z.nummer for z in alle_zeilen() if z.typ == "holding"))


def bloecke(register, max_luecke: int = MAX_LUECKE, max_block: int = MAX_BLOCK):
    """Fasst Registernummern zu (start, anzahl)-Paaren zusammen."""
    if not register:
        return ()
    reihe = sorted(register)
    ergebnis, start, vorher = [], reihe[0], reihe[0]
    for nummer in reihe[1:]:
        zu_weit = nummer - vorher > max_luecke
        zu_gross = nummer - start + 1 > max_block
        if zu_weit or zu_gross:
            ergebnis.append((start, vorher - start + 1))
            start = nummer
        vorher = nummer
    ergebnis.append((start, vorher - start + 1))
    return tuple(ergebnis)


INPUT_BLOCKS = bloecke(INPUT_REGISTERS)
HOLDING_BLOCKS = bloecke(HOLDING_REGISTERS)

#: Coils (FC=01) werden direkt adressiert, ohne Basisversatz.
COILS: tuple[int, ...] = tuple(sorted(z.nummer for z in alle_zeilen() if z.typ == "coil"))

#: Discrete Inputs (FC=02), echte 1xxxx-Nummern.
DISCRETE_INPUTS: tuple[int, ...] = tuple(sorted(z.nummer for z in alle_zeilen() if z.typ == "discrete"))

# Die Luecke zwischen 1030 und 1060 wird bewusst ueberbrueckt: ein Block von
# 31 Coils ist eine Anfrage statt zweier, und der Kessel beantwortet ihn.
COIL_BLOCKS = bloecke(COILS, max_luecke=40)

# Hier ist keine Toleranz noetig -- und keine erlaubt: Eine Anfrage ueber den
# vorhandenen Bereich hinaus laeuft beim Kessel in einen Timeout statt in eine
# saubere Exception. Am Geraet geprueft: count=4 antwortet, count=8 nicht.
DISCRETE_BLOCKS = bloecke(DISCRETE_INPUTS, max_luecke=1)
