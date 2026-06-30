import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

from pina import PinchAnalyzer, make_stream  # pinch-analysis library

st.set_page_config(page_title="Pinch Composite Curves", layout="wide")

st.title("Pinch Analysis – Composite Curves")

st.markdown(
    """
This app lets you define hot and cold streams, choose a minimum approach temperature (ΔTmin),
and then plots the **hot and cold composite curves**, showing:
- Heat exchanger overlap (maximum heat recovery region),
- Minimum hot utility (heat source),
- Minimum cold utility (heat sink),
similar to standard pinch-technology diagrams.
"""
)

# --------------------------------------------------------------------
# Helper: initialize session state for streams
# --------------------------------------------------------------------
if "streams" not in st.session_state:
    st.session_state.streams = []  # list of dicts: {type, Ts, Tt, Cp}


def add_stream(stream_type, Ts, Tt, Cp):
    st.session_state.streams.append(
        {
            "type": stream_type,
            "Ts": Ts,
            "Tt": Tt,
            "Cp": Cp,
        }
    )


# --------------------------------------------------------------------
# Sidebar: ΔTmin + stream entry form
# --------------------------------------------------------------------
with st.sidebar:
    st.header("Pinch settings")

    dt_min = st.number_input(
        "Minimum approach temperature ΔTmin (°C)",
        min_value=1.0,
        value=20.0,
        step=1.0,
        help="Typical values are 10–30 °C depending on process and economics.",
    )

    st.subheader("Add stream")

    with st.form("add_stream_form", clear_on_submit=True):
        stream_type = st.selectbox(
            "Stream type",
            options=["Hot (needs cooling)", "Cold (needs heating)"],
        )
        Ts = st.number_input("Supply temperature Ts (°C)", value=200.0)
        Tt = st.number_input("Target temperature Tt (°C)", value=60.0)
        Cp = st.number_input(
            "Heat capacity flow Cp (kW/°C)",
            value=10.0,
            min_value=0.0,
            step=0.5,
        )
        submitted = st.form_submit_button("Add stream")

        if submitted:
            if Ts == Tt or Cp <= 0:
                st.warning("Ts must differ from Tt and Cp must be > 0.")
            else:
                add_stream(stream_type, Ts, Tt, Cp)
                st.success("Stream added.")


# --------------------------------------------------------------------
# Main: show current streams
# --------------------------------------------------------------------
st.subheader("Defined streams")

if len(st.session_state.streams) == 0:
    st.info("No streams yet. Use the sidebar to add hot and cold streams.")
else:
    st.table(st.session_state.streams)

# --------------------------------------------------------------------
# Run pinch analysis and plot composite curves
# --------------------------------------------------------------------
run_button = st.button("Run pinch analysis and plot curves")

if run_button and len(st.session_state.streams) == 0:
    st.error("Please add at least one hot and one cold stream.")
elif run_button and len(st.session_state.streams) > 0:
    # Build PinchAnalyzer with half ΔTmin shift
    temp_shift = dt_min / 2.0
    analyzer = PinchAnalyzer(temp_shift)

    hot_present = False
    cold_present = False

    for s in st.session_state.streams:
        Ts = s["Ts"]
        Tt = s["Tt"]
        Cp = s["Cp"]

        # Total heat load magnitude for this stream
        Q = Cp * abs(Ts - Tt)  # kW

        if s["type"].startswith("Hot"):
            # Hot stream: releases heat -> positive Q in pina
            pina_stream = make_stream(Q, Ts, Tt)
            hot_present = True
        else:
            # Cold stream: needs heat -> negative Q in pina
            pina_stream = make_stream(-Q, Ts, Tt)
            cold_present = True

        analyzer.add_streams(pina_stream)

    if not (hot_present and cold_present):
        st.error("You must define at least one hot and one cold stream.")
    else:
        # Access composite curves and energy targets
        # Each curve is a list of (enthalpy, temperature) points.
        hot_curve = np.array(analyzer.shifted_hot_composite_curve)
        cold_curve = np.array(analyzer.shifted_cold_composite_curve)

        heating_demand = analyzer.heating_demand
        cooling_demand = analyzer.cooling_demand
        hot_utility = analyzer.hot_utility_target
        cold_utility = analyzer.cold_utility_target
        heat_recovery = analyzer.heat_recovery_target
        pinch_temps = analyzer.pinch_temps

        # ----------------------------------------------------------------
        # Plot – similar to typical pinch composite curves
        # ----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(8, 6))

        # Hot composite curve (usually red)
        ax.plot(
            hot_curve[:, 0],
            hot_curve[:, 1],
            "r.-",
            label="Hot composite curve",
        )

        # Cold composite curve (usually blue)
        ax.plot(
            cold_curve[:, 0],
            cold_curve[:, 1],
            "b.-",
            label="Cold composite curve",
        )

        ax.set_xlabel("Duty / Enthalpy (kW)")
        ax.set_ylabel("Shifted temperature (°C)")
        ax.grid(True, alpha=0.3)

        # Determine overlap (heat exchanger region) in enthalpy space
        hx_start = max(hot_curve[:, 0].min(), cold_curve[:, 0].min())
        hx_end = min(hot_curve[:, 0].max(), cold_curve[:, 0].max())

        if hx_end > hx_start:
            ax.axvspan(
                hx_start,
                hx_end,
                color="gray",
                alpha=0.2,
                label="Heat exchanger overlap",
            )

        # Mark vertical lines for cold and hot utility regions
        # Left non-overlap → minimum cold utility
        ax.axvline(
            hot_curve[:, 0].min(),
            color="cyan",
            linestyle="--",
            linewidth=1,
            label="Cold utility region",
        )
        # Right non-overlap → minimum hot utility
        ax.axvline(
            hot_curve[:, 0].max(),
            color="orange",
            linestyle="--",
            linewidth=1,
            label="Hot utility region",
        )

        # Mark pinch temperature(s)
        for Tpinch in pinch_temps:
            ax.axhline(
                Tpinch,
                color="k",
                linestyle=":",
                linewidth=1,
                label="Pinch temperature" if Tpinch == pinch_temps[0] else "",
            )

        ax.legend(loc="best")

        st.pyplot(fig)

        # ----------------------------------------------------------------
        # Numeric results
        # ----------------------------------------------------------------
        st.subheader("Energy targets")

        col1, col2, col3 = st.columns(3)
        col1.metric("Heating demand (kW)", f"{heating_demand:.1f}")
        col2.metric("Cooling demand (kW)", f"{cooling_demand:.1f}")
        col3.metric("Heat recovery target (kW)", f"{heat_recovery:.1f}")

        col4, col5 = st.columns(2)
        col4.metric("Minimum hot utility QH,min (kW)", f"{hot_utility:.1f}")
        col5.metric("Minimum cold utility QC,min (kW)", f"{cold_utility:.1f}")

        st.markdown(
            f"**Pinch temperature(s)** (shifted scale): {', '.join(f'{T:.1f} °C' for T in pinch_temps)}"
        )
