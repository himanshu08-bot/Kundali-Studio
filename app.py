"""
app.py  —  Kundli Studio
========================
A Streamlit front-end over vedic_engine.py (precise) + matching.py.

Run:
    pip install streamlit pyswisseph matplotlib
    streamlit run app.py

Architecture mirrors an NGS pipeline: a precise compute core (the ephemeris
"caller"), a thin UI on top, and honest labelling of what is exact
(astronomy) vs interpretive (Jyotish tradition).
"""

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, date, time

from vedic_engine import (build_chart, vimshottari, current_dasha,
                          detect_yogas, divisional_chart, navamsa_sign,
                          dashamsa_sign, SIGNS)
from matching import compatibility

# ------- small city table so users don't need to look up coordinates -------
CITIES = {
    "Ajmer":        (26.4499, 74.6399, 5.5),
    "Delhi":        (28.6139, 77.2090, 5.5),
    "Mumbai":       (19.0760, 72.8777, 5.5),
    "Dharamshala":  (32.2190, 76.3234, 5.5),
    "Leh":          (34.1526, 77.5771, 5.5),
    "Udaipur":      (24.5854, 73.7125, 5.5),
    "Bengaluru":    (12.9716, 77.5946, 5.5),
    "Kolkata":      (22.5726, 88.3639, 5.5),
    "Custom / other": None,
}

ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
        "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra",
        "Ketu": "Ke"}

# North-Indian house centroids on a unit square (origin bottom-left, y up)
HOUSE_XY = {1: (.50, .70), 2: (.30, .88), 3: (.12, .70), 4: (.30, .50),
            5: (.12, .30), 6: (.30, .12), 7: (.50, .30), 8: (.70, .12),
            9: (.88, .30), 10: (.70, .50), 11: (.88, .70), 12: (.70, .88)}


def draw_north_indian(chart):
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off"); ax.set_aspect("equal")
    L = dict(color="#334155", lw=1.4)
    ax.plot([0, 1, 1, 0, 0], [0, 0, 1, 1, 0], **L)          # square
    ax.plot([0, 1], [0, 1], **L); ax.plot([0, 1], [1, 0], **L)  # diagonals
    ax.plot([.5, 1, .5, 0, .5], [0, .5, 1, .5, 0], **L)      # diamond

    asc_sign = chart.ascendant.sign_index
    by_house = {}
    for p in chart.planets:
        by_house.setdefault(p.house, []).append(p)

    for h, (x, y) in HOUSE_XY.items():
        sign_no = (asc_sign + (h - 1)) % 12 + 1
        ax.text(x, y + 0.055, str(sign_no), ha="center", va="center",
                fontsize=8, color="#94a3b8")
        bodies = by_house.get(h, [])
        labels = []
        for p in bodies:
            tag = ABBR[p.name] + ("\u1d63" if p.retrograde else "")
            labels.append(tag)
        if h == 1:
            labels = ["La"] + labels
        if labels:
            ax.text(x, y - 0.02, "  ".join(labels), ha="center", va="center",
                    fontsize=9.5, color="#0f172a", fontweight="bold")
    ax.set_title(f"{chart.name} \u2014 Lagna {chart.ascendant.sign}",
                 fontsize=11, color="#0f172a")
    return fig


def render_chart_report(chart, when):
    a = chart.ascendant
    m = chart.by_name("Moon")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.pyplot(draw_north_indian(chart))
    with c2:
        st.markdown(f"### {chart.name}")
        st.write(f"**Lagna:** {a.sign} ({a.sign_sanskrit}) {a.fmt_deg()}")
        st.write(f"**Lagna nakshatra:** {a.nakshatra} pada {a.pada}")
        st.write(f"**Moon:** {m.sign} {m.fmt_deg()} \u2014 {m.nakshatra} "
                 f"pada {m.pada} (lord {m.nakshatra_lord})")
        st.write(f"**Sun:** {chart.by_name('Sun').sign}")
        st.write(f"**Ayanamsa (Lahiri):** {chart.ayanamsa:.3f}\u00b0")
        md, ad = current_dasha(chart, when)
        if md:
            lbl = md["lord"] + (f" \u2013 {ad['lord']}" if ad else "")
            st.success(f"**Running now:** {lbl}")

    st.markdown("#### Planetary positions")
    st.dataframe(
        [{"Graha": p.name, "Sign": p.sign, "Deg": p.fmt_deg(),
          "House": p.house, "Nakshatra": f"{p.nakshatra} {p.pada}",
          "Dignity": p.dignity, "Retro": "R" if p.retrograde else ""}
         for p in chart.planets],
        use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Yogas & flags")
        for nm, desc in detect_yogas(chart):
            st.write(f"- **{nm}** — {desc}")
    with col_b:
        st.markdown("#### Divisional charts")
        d9 = divisional_chart(chart, navamsa_sign)
        d10 = divisional_chart(chart, dashamsa_sign)
        st.dataframe(
            [{"Body": k, "D1": (a.sign if k == "Ascendant"
                                else chart.by_name(k).sign),
              "D9": SIGNS[d9[k]], "D10": SIGNS[d10[k]]}
             for k in ["Ascendant"] + [p.name for p in chart.planets]],
            use_container_width=True, hide_index=True)

    st.markdown("#### Vimshottari Dasha")
    st.dataframe(
        [{"Mahadasha": e["lord"],
          "From": e["start"].strftime("%Y-%m-%d"),
          "To": e["end"].strftime("%Y-%m-%d")}
         for e in vimshottari(chart, levels=1)],
        use_container_width=True, hide_index=True)


def birth_form(prefix: str, defaults=None):
    d = defaults or {}
    st.markdown(f"**{prefix}**")
    name = st.text_input("Name", d.get("name", ""), key=prefix + "name")
    col1, col2 = st.columns(2)
    with col1:
        dob = st.date_input("Date of birth", d.get("dob", date(2000, 1, 1)),
                            min_value=date(1900, 1, 1),
                            max_value=date(2100, 1, 1), key=prefix + "dob")
    with col2:
        tob = st.time_input("Time of birth", d.get("tob", time(12, 0)),
                            key=prefix + "tob")
    city = st.selectbox("City", list(CITIES.keys()),
                        index=list(CITIES.keys()).index(d.get("city", "Ajmer")),
                        key=prefix + "city")
    if CITIES[city] is None:
        c1, c2, c3 = st.columns(3)
        lat = c1.number_input("Latitude", value=26.45, key=prefix + "lat")
        lon = c2.number_input("Longitude", value=74.64, key=prefix + "lon")
        tz = c3.number_input("UTC offset (h)", value=5.5, step=0.5, key=prefix + "tz")
    else:
        lat, lon, tz = CITIES[city]
    return name, dob, tob, lat, lon, tz


# --------------------------------------------------------------------------
st.set_page_config(page_title="Kundli Studio", page_icon="\u2728", layout="wide")
st.title("\u2728 Kundli Studio")
st.caption("Precise sidereal (Lahiri) engine \u2014 Swiss Ephemeris. "
           "Astronomy is exact; the Jyotish interpretation on top is a "
           "traditional lens for reflection, not validated prediction.")

tab1, tab2 = st.tabs(["Single chart", "Compatibility (Moon-based)"])

with tab1:
    name, dob, tob, lat, lon, tz = birth_form("Birth details",
        {"name": "Himanshu", "dob": date(2001, 11, 8),
         "tob": time(14, 55), "city": "Ajmer"})
    if st.button("Cast chart", type="primary"):
        chart = build_chart(name or "Chart", dob.year, dob.month, dob.day,
                            tob.hour, tob.minute, tz, lat, lon)
        render_chart_report(chart, datetime.now())

with tab2:
    st.info("Both kundlis need a birth **time** to fix the Moon's nakshatra. "
            "If a time is unknown, the Moon (and therefore the match) is "
            "uncertain \u2014 the tool will still compute, but treat it as provisional.")
    cA, cB = st.columns(2)
    with cA:
        na, da, ta, la, loa, tza = birth_form("Person A",
            {"name": "Himanshu", "dob": date(2001, 11, 8),
             "tob": time(14, 55), "city": "Ajmer"})
    with cB:
        nb, db, tb, lb, lob, tzb = birth_form("Person B",
            {"name": "Partner", "dob": date(1999, 6, 14),
             "tob": time(12, 0), "city": "Custom / other"})
    if st.button("Check compatibility", type="primary"):
        ca = build_chart(na, da.year, da.month, da.day, ta.hour, ta.minute, tza, la, loa)
        cb = build_chart(nb, db.year, db.month, db.day, tb.hour, tb.minute, tzb, lb, lob)
        res = compatibility(ca.by_name("Moon").lon, cb.by_name("Moon").lon,
                            na or "A", nb or "B")
        c1, c2 = st.columns(2)
        c1.metric(f"{res['a']['name']} Moon",
                  f"{res['a']['rashi']}", res['a']['nak'])
        c2.metric(f"{res['b']['name']} Moon",
                  f"{res['b']['rashi']}", res['b']['nak'])
        st.dataframe(
            [{"Koota": r[0], "Score": r[1], "Max": r[2], "Note": r[3]}
             for r in res["rows"]],
            use_container_width=True, hide_index=True)
        st.subheader(f"Core score: {res['score']} / {res['max']}")
        st.caption("This is 26 of the classical 36 (Graha Maitri + Gana + "
                   "Bhakoot + Nadi). Bhakoot and Nadi are the two most "
                   "emphasised kootas. Add Varna/Vashya/Tara/Yoni for the full 36.")
