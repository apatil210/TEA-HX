import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

from pina import PinchAnalyzer, make_stream  # pinch-analysis library


# --------------------------------------------------------------------
# Streamlit page setup
# --------------------------------------------------------------------
st.set_page_config(page_title="Pinch Composite Curves", layout="wide")
st.title("Pinch Analysis – Composite Curves")

st.markdown(
    """
This app lets you define **hot** and **cold** streams, set a minimum approach temperature (ΔTmin),
and then performs pinch analysis to plot the **hot and cold composite curves**.

The plot shows:
- Heat exchanger overlap region (internal heat recovery),
- Minimum hot utility (external heat source),
- Minimum cold utility (external heat sink),
- Pinch temperature(s).
"""
)


# --------------------------------------------------------------------
# Initialize session_state for streams
# --------------------------------------------------------------------
if "streams" not in st.session_state:
    st.session_state.streams = []  # list of dicts: {type, Ts, Tt, Cp}


def add_stream(stream_type: str, Ts: float, Tt: float, Cp: float):
    """Add a stream to session_state."""
    st.session_state.streams.append(
        {"type": stream_type, "Ts": Ts, "Tt": Tt, "Cp": Cp}
    )


# --------------------------------------------------------------------
# Sidebar controls: ΔTmin + stream entry
# --------------------------------------------------------------------
with st.sidebar:
    st.header("Analysis settings")

    dt_min = st.number_input(
        "Minimum approach temperature ΔTmin (°C)",
        min_value=1.0,
        value=20.0,
        step=1.0,
        help="Typical values: 10–30 °C, depending on process and economics.",
    )

    st.subheader("Add a stream")

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
            if Ts == Tt:
                st.warning("Supply and target temperatures must be different.")
            elif Cp <= 0:
                st.warning("Cp must be > 0.")
            else:
                add_stream(stream_type, Ts, Tt, Cp)
                st.success("Stream added.")


# --------------------------------------------------------------------
# Show current streams
# --------------------------------------------------------------------
st.subheader("Defined streams")

if len(st.session_state.streams) == 0:
    st.info("No streams defined yet. Use the sidebar to add hot and cold streams.")
else:
    st.table(st.session_state.streams)


# --------------------------------------------------------------------
# Pinch analysis and plotting logic
# --------------------------------------------------------------------
run_button = st.button("Run pinch analysis and plot curves")

if run_button:
    if len(st.session_state.streams) == 0:
        st.error("Please add at least one hot and one cold stream.")
    else:
        # Build pinch analyzer with half ΔTmin shift (standard composite-curve method).
        temp_shift = dt_min / 2.0
        analyzer = PinchAnalyzer(temp_shift)

        hot_present = False
        cold_present = False

        for s in st.session_state.streams:
            Ts = s["Ts"]
            Tt = s["Tt"]
            Cp = s["Cp"]

            # Total heat load magnitude for the stream
            Q = Cp * abs(Ts - Tt)  # kW

            if s["type"].startswith("Hot"):
                # Hot stream releases heat → positive Q in pina.
                pina_stream = make_stream(Q, Ts, Tt)
                hot_present = True
            else:
                # Cold stream needs heat → negative Q in pina.
                pina_stream = make_stream(-Q, Ts, Tt)
                cold_present = True

            analyzer.add_streams(pina_stream)

        if not (hot_present and cold_present):
            st.error("You must define at least one hot and one cold stream.")
        else:
            # Get composite curves and targets from pina.
            hot_curve = np.array(analyzer.shifted_hot_composite_curve)
            cold_curve = np.array(analyzer.shifted_cold_composite_curve)

            heating_demand = analyzer.heating_demand
            cooling_demand = analyzer.cooling_demand
            hot_utility = analyzer.hot_utility_target
            cold_utility = analyzer.cold_utility_target
            heat_recovery = analyzer.heat_recovery_target
            pinch_temps = analyzer.pinch_temps

            # ------------------------------------------------------------
            # Plotting – similar to standard pinch composite curves.
            # ------------------------------------------------------------
            fig, ax = plt.subplots(figsize=(8, 6))

            # Hot composite curve (red)
            ax.plot(
                hot_curve[:, 0],
                hot_curve[:, 1],
                "r.-",
                label="Hot composite curve",
            )

            # Cold composite curve (blue)
            ax.plot(
                cold_curve[:, 0],
                cold_curve[:, 1],
                "b.-",
                label="Cold composite curve",
            )

            ax.set_xlabel("Duty / Enthalpy (kW)")
            ax.set_ylabel("Shifted temperature (°C)")
            ax.grid(True, alpha=0.3)

            # Heat-exchanger overlap region (where both curves exist).
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

            # Vertical guides for utility regions (conceptual).
            ax.axvline(
                hot_curve[:, 0].min(),
                color="cyan",
                linestyle="--",
                linewidth=1,
                label="Cold utility region",
            )
            ax.axvline(
                hot_curve[:, 0].max(),
                color="orange",
                linestyle="--",
                linewidth=1,
                label="Hot utility region",
            )

            # Pinch temperature(s) as horizontal lines.
            for i, Tpinch in enumerate(pinch_temps):
                ax.axhline(
                    Tpinch,
                    color="k",
                    linestyle=":",
                    linewidth=1,
                    label="Pinch temperature" if i == 0 else "",
                )

            ax.legend(loc="best")

            st.pyplot(fig)

            # ------------------------------------------------------------
            # Numeric results panel
            # ------------------------------------------------------------
            st.subheader("Energy targets")

            col1, col2, col3 = st.columns(3)
            col1.metric("Heating demand (kW)", f"{heating_demand:.1f}")
            col2.metric("Cooling demand (kW)", f"{cooling_demand:.1f}")
            col3.metric("Heat recovery target (kW)", f"{heat_recovery:.1f}")

            col4, col5 = st.columns(2)
            col4.metric("Minimum hot utility QH,min (kW)", f"{hot_utility:.1f}")
            col5.metric("Minimum cold utility QC,min (kW)", f"{cold_utility:.1f}")

            st.markdown(
                f"**Pinch temperature(s)** (shifted scale): "
                + ", ".join(f"{T:.1f} °C" for T in pinch_temps)
            )
