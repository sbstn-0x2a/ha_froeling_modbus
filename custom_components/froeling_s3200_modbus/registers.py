"""Registerlandkarte der Integration.

Die Listen enthalten jede Registernummer, die von irgendeiner Plattform gelesen
wird. Sie werden aus den Konstruktoraufrufen der Entitaeten abgeleitet;
tests/test_registers.py prueft, dass keine Adresse fehlt -- eine Luecke waere
sonst unsichtbar, die betroffene Entitaet bliebe schlicht leer. Daraus werden zusammenhaengende Bloecke gebildet, die der Coordinator mit
je einer Modbus-Anfrage liest.

Am Geraet gemessen (08.09.2026, Froeling SP Dual Compact):

    143 Einzelreads : 1645 ms
     18 Blockreads  :  348 ms

Zur Blockgroesse: Modbus erlaubt bis zu 125 Register je Anfrage, der Kessel
beantwortet ab 30001 aber nur 105 -- darueber kommt Exception 0x03 (Illegal
Data Value), weil der Registerbereich dort endet. MAX_BLOCK bleibt deshalb
darunter. Luecken innerhalb eines Blocks sind unproblematisch: Der Kessel
liefert auch Adressen mit, die die Integration nicht nutzt.
"""

from __future__ import annotations

INPUT_BASE = 30001
HOLDING_BASE = 40001
DISCRETE_BASE = 10001

#: Groesste Registerzahl je Anfrage.
MAX_BLOCK = 100

#: Groesste Luecke, die noch in denselben Block gezogen wird. Tauscht
#: ungenutzte Registerinhalte gegen weniger Anfragen.
MAX_LUECKE = 20

INPUT_REGISTERS: tuple[int, ...] = (
    30001, 30002, 30003, 30004, 30005, 30007, 30008, 30009,
    30010, 30011, 30012, 30013, 30014, 30015, 30016, 30017,
    30018, 30019, 30020, 30021, 30022, 30023, 30025, 30028,
    30037, 30040, 30041, 30043, 30045, 30046, 30047, 30048,
    30049, 30050, 30055, 30056, 30057, 30063, 30064, 30068,
    30075, 30077, 30082, 30083, 30084, 30085, 30086, 30087,
    30089, 30098, 30102, 30103, 30104, 30105, 30171, 30601,
    30711, 30712, 31001, 31031, 31032, 31061, 31062, 31631,
    31633, 32001, 32002, 32003, 32004, 32007, 34001, 34002,
)

HOLDING_REGISTERS: tuple[int, ...] = (
    40001, 40002, 40003, 40008, 40009, 40027, 40028, 40029,
    40043, 40045, 40046, 40047, 40048, 40049, 40050, 40051,
    40061, 40067, 40070, 40073, 40085, 40125, 40136, 40265,
    40319, 40320, 40336, 40601, 41032, 41033, 41034, 41035,
    41037, 41038, 41039, 41040, 41043, 41044, 41045, 41046,
    41047, 41048, 41062, 41063, 41064, 41065, 41067, 41068,
    41069, 41070, 41073, 41074, 41075, 41076, 41078, 41079,
    41632, 41633, 41634, 41635, 41636, 41637, 41638, 41639,
    41640, 41641, 41646, 42001, 42002, 42003, 42004, 42005,
    42006, 42012, 42014, 42015, 42018, 42020, 42021, 42022,
    42025, 42026, 42027, 42028, 42029, 42030, 42031, 43020,
    48001, 48002, 48019, 48029, 48030,
)


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
COILS: tuple[int, ...] = (1030, 1060)

#: Discrete Inputs (FC=02), echte 1xxxx-Nummern.
DISCRETE_INPUTS: tuple[int, ...] = (10001, 10002, 10003, 10004)

# Die Luecke zwischen 1030 und 1060 wird bewusst ueberbrueckt: ein Block von
# 31 Coils ist eine Anfrage statt zweier, und der Kessel beantwortet ihn.
COIL_BLOCKS = bloecke(COILS, max_luecke=40)

# Hier ist keine Toleranz noetig -- und keine erlaubt: Eine Anfrage ueber den
# vorhandenen Bereich hinaus laeuft beim Kessel in einen Timeout statt in eine
# saubere Exception. Am Geraet geprueft: count=4 antwortet, count=8 nicht.
DISCRETE_BLOCKS = bloecke(DISCRETE_INPUTS, max_luecke=1)
