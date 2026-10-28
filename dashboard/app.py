"""Citi Bike Jersey City dashboard.

    pip install -r dashboard/requirements.txt
    streamlit run dashboard/app.py

Reads the small CSVs in dashboard/data (regenerate with dashboard/export.py).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parent / "data"

st.set_page_config(page_title="Citi Bike Jersey City", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"{name}.csv")


growth = load("03_like_for_like_growth")
monthly = load("monthly_trips").assign(month_start=lambda d: pd.to_datetime(d["month_start"]))
hourly = load("hourly_profile")
stations = load("stations")
weather = load("04_weather_effect")
flows = load("05_commuter_flows")
mix = load("07_rider_mix")

st.title("Citi Bike Jersey City, 2019 to 2024")
st.caption(
    "4.3M trips from a Kimball star schema. The headline growth is mostly the network "
    "getting bigger, so the first chart compares like with like."
)

naive = growth["all_trips_index"].iloc[-1] / 100
like_for_like = growth["same_stations_index"].iloc[-1] / 100 - 1
a, b, c, d = st.columns(4)
a.metric("Valid trips analysed", f"{growth['all_trips'].sum():,}")
b.metric("Naive growth since 2019", f"{naive:.1f}x")
c.metric("Like-for-like growth", f"+{like_for_like:.0%}", help="Same 49 stations, 2019 vs 2024")
d.metric("Stations tracked", f"{stations['station_key'].nunique():,}")

st.subheader("Growth: naive vs like-for-like")
long = growth.melt(
    id_vars="year",
    value_vars=["all_trips_index", "jersey_city_index", "same_stations_index"],
    var_name="measure",
    value_name="index (2019 = 100)",
)
long["measure"] = long["measure"].map(
    {
        "all_trips_index": "All trips in the files",
        "jersey_city_index": "Jersey City stations",
        "same_stations_index": "Same 49 stations (like-for-like)",
    }
)
st.plotly_chart(
    px.line(long, x="year", y="index (2019 = 100)", color="measure", markers=True),
    width="stretch",
)
st.caption(
    "From 2021 the files also carry Hoboken, and Jersey City kept adding stations. "
    "Tracking each station through its ID changes is what makes the like-for-like line possible."
)

left, right = st.columns(2)
with left:
    st.subheader("Monthly trips and weather")
    st.plotly_chart(
        px.bar(monthly, x="month_start", y="jersey_city_trips", color="avg_temp_max_c",
               color_continuous_scale="RdYlBu_r", labels={"avg_temp_max_c": "Avg max temp (C)"}),
        width="stretch",
    )
with right:
    st.subheader("Effect of weather on daily trips")
    st.plotly_chart(
        px.bar(weather, x="pct_change_in_trips", y="comparison", orientation="h"),
        width="stretch",
    )

st.subheader("When people ride")
year = st.select_slider("Year", options=sorted(hourly["year"].unique()), value=2024)
st.plotly_chart(
    px.line(hourly[hourly["year"] == year], x="hour", y="trips_per_day", color="day_type", markers=True),
    width="stretch",
)

left, right = st.columns(2)
with left:
    st.subheader("Station map")
    metric = st.radio("Size by", ["trips_2024", "trips_all_years"], horizontal=True)
    st.plotly_chart(
        px.scatter_map(stations, lat="lat", lon="lng", size=metric, color="area",
                       hover_name="station_name", zoom=11.5, height=480),
        width="stretch",
    )
with right:
    st.subheader("Commuter flows: stations that drain or fill on weekday mornings")
    st.dataframe(flows, hide_index=True, width="stretch")

st.subheader("Rider mix")
st.dataframe(mix, hide_index=True, width="stretch")
st.caption(
    "Do not read a trend into pct_electric across 2023 to 2024: the jump on 1 January 2024 "
    "is a change in how the feed labels bikes, not a fleet that tripled overnight."
)
