"""
vedic_engine.py
================
A precise Vedic (Jyotish) astrology calculation engine.

Astronomy is exact and computable; the *interpretation* layered on top is the
Jyotish tradition's own symbolic framework, offered as a lens for reflection,
not empirically validated prediction. This module does the exact part.

Backend: Swiss Ephemeris (pyswisseph) with the Moshier semi-analytic ephemeris,
so NO external data files are required. Sidereal zodiac, Lahiri ayanamsa.

    pip install pyswisseph

Author: built with Himanshu.
"""

from __future__ import annotations
import swisseph as swe
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# Static Jyotish reference data
# --------------------------------------------------------------------------

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

SIGN_SANSKRIT = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
                 "Tula", "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"]

NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
              "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
              "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
              "Uttara Bhadrapada", "Revati"]

# Vimshottari dasha: lord of each nakshatra (cycles every 9) and years each rules
DASHA_SEQUENCE = ["Ketu", "Venus", "Sun", "Moon", "Mars",
                  "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}

# Exaltation sign index for each graha (debilitation is the opposite sign, +6)
EXALTATION = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5,
              "Jupiter": 3, "Venus": 11, "Saturn": 6}
# Own signs
OWN_SIGNS = {"Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
             "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]}

PLANETS = [("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS),
           ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER),
           ("Venus", swe.VENUS), ("Saturn", swe.SATURN),
           ("Rahu", swe.MEAN_NODE)]  # Ketu derived as Rahu + 180

# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class Position:
    name: str
    lon: float                # sidereal longitude 0-360
    sign_index: int
    deg_in_sign: float
    nakshatra: str
    pada: int
    nakshatra_lord: str
    retrograde: bool
    house: int = 0
    dignity: str = ""

    @property
    def sign(self) -> str:
        return SIGNS[self.sign_index]

    @property
    def sign_sanskrit(self) -> str:
        return SIGN_SANSKRIT[self.sign_index]

    def fmt_deg(self) -> str:
        d = int(self.deg_in_sign)
        m = int((self.deg_in_sign - d) * 60)
        return f"{d:02d}\u00b0{m:02d}'"


@dataclass
class Chart:
    name: str
    dt_local: datetime
    utc_offset_hours: float
    lat: float
    lon: float
    jd_ut: float
    ayanamsa: float
    ascendant: Position
    planets: list = field(default_factory=list)

    def by_name(self, n: str) -> Position | None:
        if n.lower() in ("asc", "ascendant", "lagna"):
            return self.ascendant
        for p in self.planets:
            if p.name == n:
                return p
        return None


# --------------------------------------------------------------------------
# Core helpers
# --------------------------------------------------------------------------

def _nakshatra_of(lon: float):
    span = 360.0 / 27.0            # 13°20'
    idx = int(lon / span) % 27
    within = lon - idx * span
    pada = int(within / (span / 4)) + 1
    lord = DASHA_SEQUENCE[idx % 9]
    return NAKSHATRAS[idx], pada, lord


def _dignity(name: str, sign_index: int) -> str:
    if name in ("Rahu", "Ketu"):
        return "-"
    if name in EXALTATION and sign_index == EXALTATION[name]:
        return "Exalted"
    if name in EXALTATION and sign_index == (EXALTATION[name] + 6) % 12:
        return "Debilitated"
    if name in OWN_SIGNS and sign_index in OWN_SIGNS[name]:
        return "Own sign"
    return "Neutral"


def _make_position(name: str, lon: float, retro: bool) -> Position:
    lon %= 360.0
    si = int(lon / 30) % 12
    nak, pada, lord = _nakshatra_of(lon)
    return Position(name=name, lon=lon, sign_index=si,
                    deg_in_sign=lon - si * 30,
                    nakshatra=nak, pada=pada, nakshatra_lord=lord,
                    retrograde=retro, dignity=_dignity(name, si))


# --------------------------------------------------------------------------
# Chart construction
# --------------------------------------------------------------------------

def build_chart(name, year, month, day, hour, minute,
                utc_offset_hours, lat, lon) -> Chart:
    """utc_offset_hours e.g. 5.5 for IST. Time given in LOCAL clock time."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ut_hour = hour + minute / 60.0 - utc_offset_hours
    jd = swe.julday(year, month, day, ut_hour, swe.GREG_CAL)
    flags = swe.FLG_SIDEREAL | swe.FLG_MOSEPH | swe.FLG_SPEED

    positions = []
    for pname, pid in PLANETS:
        xx, _ = swe.calc_ut(jd, pid, flags)
        positions.append(_make_position(pname, xx[0], retro=xx[3] < 0))
    # Ketu = Rahu + 180 (node retrograde by convention)
    rahu = next(p for p in positions if p.name == "Rahu")
    positions.append(_make_position("Ketu", rahu.lon + 180.0, retro=True))

    # Ascendant (sidereal, whole-sign house frame)
    _, ascmc = swe.houses_ex(jd, lat, lon, b'W', swe.FLG_SIDEREAL)
    asc = _make_position("Ascendant", ascmc[0], retro=False)

    # Whole-sign houses counted from the Lagna sign
    asc_sign = asc.sign_index
    for p in positions:
        p.house = ((p.sign_index - asc_sign) % 12) + 1
    asc.house = 1

    dt_local = datetime(year, month, day, hour, minute)
    return Chart(name=name, dt_local=dt_local, utc_offset_hours=utc_offset_hours,
                 lat=lat, lon=lon, jd_ut=jd,
                 ayanamsa=swe.get_ayanamsa_ut(jd),
                 ascendant=asc, planets=positions)


# --------------------------------------------------------------------------
# Divisional charts (vargas): return sign index for a given longitude
# --------------------------------------------------------------------------

def navamsa_sign(lon: float) -> int:
    """D9. 108 navamsas of 3°20' across the zodiac."""
    return int(lon / (30.0 / 9.0)) % 12


def dashamsa_sign(lon: float) -> int:
    """D10. Odd signs start from same sign, even signs from the 9th."""
    si = int(lon / 30) % 12
    within = lon - si * 30
    d = int(within / 3.0)             # 0..9
    if (si + 1) % 2 == 1:             # odd sign (1-indexed)
        start = si
    else:                             # even sign -> 9th from it
        start = (si + 8) % 12
    return (start + d) % 12


def divisional_chart(chart: Chart, fn) -> dict:
    """Apply a varga function to the ascendant + all grahas."""
    out = {"Ascendant": fn(chart.ascendant.lon)}
    for p in chart.planets:
        out[p.name] = fn(p.lon)
    return out


# --------------------------------------------------------------------------
# Vimshottari Dasha
# --------------------------------------------------------------------------

def _add_years(dt: datetime, years: float) -> datetime:
    return dt + timedelta(days=years * 365.2425)

def vimshottari(chart: Chart, levels: int = 2):
    """Return the mahadasha timeline (optionally with antardashas)."""
    moon = chart.by_name("Moon")
    span = 360.0 / 27.0
    nak_idx = int(moon.lon / span) % 27
    within = moon.lon - nak_idx * span
    frac_remaining = 1.0 - within / span

    start_lord = DASHA_SEQUENCE[nak_idx % 9]
    start_i = DASHA_SEQUENCE.index(start_lord)

    # Birth falls partway through the first mahadasha
    first_full = DASHA_YEARS[start_lord]
    balance = first_full * frac_remaining
    # so the first dasha "began" balance-minus-full years before birth
    cursor = _add_years(chart.dt_local, -(first_full - balance))

    timeline = []
    for k in range(9):
        lord = DASHA_SEQUENCE[(start_i + k) % 9]
        yrs = DASHA_YEARS[lord]
        md_start = cursor
        md_end = _add_years(cursor, yrs)
        entry = {"lord": lord, "start": md_start, "end": md_end, "sub": []}
        if levels >= 2:
            sub_cursor = md_start
            for j in range(9):
                sub_lord = DASHA_SEQUENCE[(DASHA_SEQUENCE.index(lord) + j) % 9]
                sub_yrs = yrs * DASHA_YEARS[sub_lord] / 120.0
                s0 = sub_cursor
                s1 = _add_years(sub_cursor, sub_yrs)
                entry["sub"].append({"lord": sub_lord, "start": s0, "end": s1})
                sub_cursor = s1
        timeline.append(entry)
        cursor = md_end
    return timeline


def current_dasha(chart: Chart, when: datetime | None = None):
    when = when or datetime.now()
    tl = vimshottari(chart, levels=2)
    md = next((e for e in tl if e["start"] <= when < e["end"]), None)
    if not md:
        return None, None
    ad = next((s for s in md["sub"] if s["start"] <= when < s["end"]), None)
    return md, ad


# --------------------------------------------------------------------------
# A few classical yogas (illustrative, not exhaustive)
# --------------------------------------------------------------------------

def detect_yogas(chart: Chart) -> list:
    y = []
    def P(n): return chart.by_name(n)

    # Budhaditya: Sun + Mercury in same sign
    if P("Sun").sign_index == P("Mercury").sign_index:
        y.append(("Budhaditya Yoga",
                  f"Sun & Mercury together in {P('Sun').sign} "
                  f"(house {P('Sun').house}) \u2014 intellect, learning."))

    # Gaja Kesari: Jupiter in a kendra (1/4/7/10) from the Moon
    diff = (P("Jupiter").sign_index - P("Moon").sign_index) % 12
    if diff in (0, 3, 6, 9):
        y.append(("Gaja Kesari Yoga",
                  "Jupiter in a kendra from the Moon \u2014 wisdom, repute."))

    # Chandra-Mangala: Moon + Mars together
    if P("Moon").sign_index == P("Mars").sign_index:
        y.append(("Chandra-Mangala Yoga", "Moon with Mars \u2014 drive, resourcefulness."))

    # Vipareeta (Harsha): lord-of-6 sitting in the 6th, etc. Simplified: any
    # benefic-of-dusthana logic is complex; we flag the classic 6-in-6 Moon case.
    if P("Moon").house == 6 and "Own" in P("Moon").dignity:
        y.append(("Harsha Vipareeta Raja Yoga (partial)",
                  "6th-lord Moon in the 6th \u2014 overcoming rivals/obstacles."))

    # Neechabhanga flag: any debilitated graha (cancellation needs manual check)
    for p in chart.planets:
        if p.dignity == "Debilitated":
            y.append((f"{p.name} debilitated",
                      f"{p.name} debilitated in {p.sign} \u2014 check Neecha Bhanga "
                      "(cancellation) manually."))
    return y


# --------------------------------------------------------------------------
# Pretty printing
# --------------------------------------------------------------------------

def print_report(chart: Chart, when: datetime | None = None):
    asc = chart.ascendant
    print("=" * 66)
    print(f"  KUNDLI  \u2014  {chart.name}")
    print(f"  {chart.dt_local:%d %b %Y, %H:%M}  (UTC{chart.utc_offset_hours:+.1f})"
          f"   lat {chart.lat:.4f}, lon {chart.lon:.4f}")
    print(f"  Ayanamsa (Lahiri): {chart.ayanamsa:.4f}\u00b0")
    print("=" * 66)
    print(f"  Lagna: {asc.sign} ({asc.sign_sanskrit}) {asc.fmt_deg()}"
          f"   |  Nakshatra: {asc.nakshatra} pada {asc.pada}")
    moon = chart.by_name("Moon")
    print(f"  Moon:  {moon.sign} {moon.fmt_deg()}"
          f"   |  {moon.nakshatra} pada {moon.pada} (lord {moon.nakshatra_lord})")
    print("-" * 66)
    print(f"  {'Graha':9s}{'Sign':13s}{'Deg':9s}{'Ho':>3s}  {'Nakshatra':16s}{'Dignity'}")
    print("-" * 66)
    for p in chart.planets:
        r = " (R)" if p.retrograde else ""
        print(f"  {p.name:9s}{p.sign:13s}{p.fmt_deg():9s}{p.house:>3d}  "
              f"{p.nakshatra+' '+str(p.pada):16s}{p.dignity}{r}")
    print("-" * 66)

    print("\n  YOGAS & FLAGS")
    for nm, desc in detect_yogas(chart):
        print(f"   \u2022 {nm}: {desc}")

    print("\n  DIVISIONAL SNAPSHOTS")
    d9 = divisional_chart(chart, navamsa_sign)
    d10 = divisional_chart(chart, dashamsa_sign)
    print(f"   {'Body':11s}{'D1':13s}{'D9 (Navamsa)':15s}{'D10 (Dashamsa)'}")
    for key in ["Ascendant"] + [p.name for p in chart.planets]:
        d1sign = (asc.sign if key == "Ascendant"
                  else chart.by_name(key).sign)
        print(f"   {key:11s}{d1sign:13s}{SIGNS[d9[key]]:15s}{SIGNS[d10[key]]}")

    print("\n  VIMSHOTTARI DASHA (mahadashas)")
    for e in vimshottari(chart, levels=1):
        print(f"   {e['lord']:8s} {e['start']:%Y-%m-%d}  \u2192  {e['end']:%Y-%m-%d}")

    md, ad = current_dasha(chart, when)
    if md:
        label = f"{md['lord']}"
        if ad:
            label += f" \u2013 {ad['lord']}"
        w = when or datetime.now()
        print(f"\n  RUNNING NOW ({w:%d %b %Y}):  {label}")
        if ad:
            print(f"   {md['lord']} mahadasha : {md['start']:%Y-%m-%d} \u2192 {md['end']:%Y-%m-%d}")
            print(f"   {ad['lord']} antardasha: {ad['start']:%Y-%m-%d} \u2192 {ad['end']:%Y-%m-%d}")
    print("=" * 66)


if __name__ == "__main__":
    # Himanshu — 8 Nov 2001, 14:55 IST, Ajmer
    himanshu = build_chart("Himanshu", 2001, 11, 8, 14, 55,
                           utc_offset_hours=5.5, lat=26.4499, lon=74.6399)
    print_report(himanshu, when=datetime(2026, 7, 6))
