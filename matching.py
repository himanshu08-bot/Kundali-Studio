"""
matching.py
===========
Moon-based compatibility (a subset of Ashtakoota Guna Milan).

Honesty note: full 36-point Ashtakoota has genuine cross-tradition
disagreements (especially Vashya and Yoni matrices and Nadi exceptions).
This module implements the four kootas that are widely agreed and simple to
verify from the Moon's rashi + nakshatra:

    Graha Maitri (5)  +  Gana (6)  +  Bhakoot (7)  +  Nadi (8)   = 26 of 36

Bhakoot and Nadi are the two most-emphasised "dealbreaker" kootas, so this
core is the most decision-relevant part. Extend with Varna/Vashya/Tara/Yoni
for the full score when you want it.

Everything here needs only the Moon's sidereal longitude of each person.
"""

from __future__ import annotations
from vedic_engine import SIGNS, NAKSHATRAS

# nakshatra index -> Gana
_DEVA = {0, 4, 6, 7, 12, 14, 16, 21, 26}
_MANUSHYA = {1, 3, 5, 10, 11, 19, 20, 24, 25}
_RAKSHASA = {2, 8, 9, 13, 15, 17, 18, 22, 23}

# nakshatra index -> Nadi (0=Aadi,1=Madhya,2=Antya)
_NADI = {}
for _i in range(27):
    # standard repeating pattern Aadi,Madhya,Antya with the classical grouping
    pass
_AADI = {0, 5, 6, 11, 12, 17, 18, 23, 24}
_MADHYA = {1, 4, 7, 10, 13, 16, 19, 22, 25}
_ANTYA = {2, 3, 8, 9, 14, 15, 20, 21, 26}

# Sign lord (graha) per rashi index
_SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]

# Natural (naisargika) friendship: friend / neutral / enemy
_FRIEND = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
_ENEMY = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
}

def _relation(a: str, b: str) -> str:
    if a == b:
        return "friend"
    if b in _FRIEND.get(a, set()):
        return "friend"
    if b in _ENEMY.get(a, set()):
        return "enemy"
    return "neutral"

def _gana(n): return "Deva" if n in _DEVA else "Manushya" if n in _MANUSHYA else "Rakshasa"
def _nadi(n): return "Aadi" if n in _AADI else "Madhya" if n in _MADHYA else "Antya"


def graha_maitri(rashi_a: int, rashi_b: int):
    la, lb = _SIGN_LORD[rashi_a], _SIGN_LORD[rashi_b]
    ra, rb = _relation(la, lb), _relation(lb, la)
    pair = {ra, rb}
    if pair == {"friend"}:
        s = 5
    elif pair == {"friend", "neutral"}:
        s = 4
    elif pair == {"neutral"}:
        s = 3
    elif pair == {"friend", "enemy"}:
        s = 1
    elif pair == {"neutral", "enemy"}:
        s = 1
    else:  # both enemy
        s = 0
    return s, 5, f"lords {la}/{lb} ({ra}/{rb})"


def gana_koota(nak_a: int, nak_b: int):
    ga, gb = _gana(nak_a), _gana(nak_b)
    table = {
        ("Deva", "Deva"): 6, ("Manushya", "Manushya"): 6, ("Rakshasa", "Rakshasa"): 6,
        ("Deva", "Manushya"): 5, ("Manushya", "Deva"): 6,
        ("Deva", "Rakshasa"): 1, ("Rakshasa", "Deva"): 0,
        ("Manushya", "Rakshasa"): 0, ("Rakshasa", "Manushya"): 3,
    }
    return table[(ga, gb)], 6, f"{ga} / {gb}"


def bhakoot_koota(rashi_a: int, rashi_b: int):
    d1 = ((rashi_b - rashi_a) % 12) + 1
    d2 = ((rashi_a - rashi_b) % 12) + 1
    bad = {(6, 8), (8, 6), (5, 9), (9, 5), (2, 12), (12, 2)}
    s = 0 if (d1, d2) in bad else 7
    note = f"counts {d1}/{d2}" + (" \u2014 Bhakoot dosha" if s == 0 else "")
    return s, 7, note


def nadi_koota(nak_a: int, nak_b: int):
    na, nb = _nadi(nak_a), _nadi(nak_b)
    s = 0 if na == nb else 8
    note = f"{na} / {nb}" + (" \u2014 Nadi dosha" if s == 0 else "")
    return s, 8, note


def compatibility(lon_a: float, lon_b: float, name_a="A", name_b="B"):
    ri_a, ri_b = int(lon_a / 30) % 12, int(lon_b / 30) % 12
    ni_a = int(lon_a / (360 / 27)) % 27
    ni_b = int(lon_b / (360 / 27)) % 27

    rows = [
        ("Graha Maitri", *graha_maitri(ri_a, ri_b)),
        ("Gana", *gana_koota(ni_a, ni_b)),
        ("Bhakoot", *bhakoot_koota(ri_a, ri_b)),
        ("Nadi", *nadi_koota(ni_a, ni_b)),
    ]
    got = sum(r[1] for r in rows)
    mx = sum(r[2] for r in rows)
    return {
        "a": {"name": name_a, "rashi": SIGNS[ri_a], "nak": NAKSHATRAS[ni_a],
              "gana": _gana(ni_a), "nadi": _nadi(ni_a)},
        "b": {"name": name_b, "rashi": SIGNS[ri_b], "nak": NAKSHATRAS[ni_b],
              "gana": _gana(ni_b), "nadi": _nadi(ni_b)},
        "rows": rows, "score": got, "max": mx,
    }
