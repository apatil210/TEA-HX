import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Heat Exchanger Matching + Cost",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Matching + Cost")
st.caption("Enter 4 heat sources and 4 heat sinks, then create a one-to-one matching.")


def counterflow_effectiveness(ntu: float, cr: float) -> float:
    if ntu <= 0:
        return 0.0
    if abs(cr - 1.0) < 1e-9:
        return ntu / (1.0 + ntu)
    e = math.exp(-ntu * (1.0 - cr))
    return (1.0 - e) / (1.0 - cr * e)


def calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k):
    resistance = (1.0 / h_hot) + (tube_thickness / tube_k) + (1.0 / h_cold)
    return 1.0 / resistance


def solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area):
    ua = u * area
    ch = mh * cph
    cc = mc * cpc
    cmin = min(ch, cc)
    cmax = max(ch, cc)
    cr = cmin / cmax if cmax > 0 else 0.0
    ntu = ua / cmin if cmin > 0 else 0.0
    eps = counterflow_effectiveness(ntu, cr)
    qmax = cmin * (thi - tci)
    q = eps * qmax
    tho = thi - q / ch
    tco = tci + q / cc

    return {
        "UA": ua,
        "C_h": ch,
        "C_c": cc,
        "C_min": cmin,
        "C_max": cmax,
        "C_r": cr,
        "NTU": ntu,
        "Effectiveness": eps,
        "Q_kW": q / 1000.0,
        "T_h_out": tho,
        "T_c_out": tco,
    }


def shell_tube_base_cost_si(area_m2):
    lnA = math.log(area_m2)
    return math.exp(8.202 + 0.01506 * lnA + 0.06811 * (lnA ** 2))


def exchanger_type_factor(area_m2, exchanger_type):
    lnA = math.log(area_m2)
    if exchanger_type == "Floating head":
        return 1.0
    elif exchanger_type == "Fixed head":
        return math.exp(-0.9003 + 0.0906 * lnA)
    elif exchanger_type == "U-tube":
        return math.exp(-0.7844 + 0.0830 * lnA)
    elif exchanger_type == "Kettle reboiler":
        return 1.35
    else:
        raise ValueError("Invalid exchanger type selected.")


def pressure_factor(area_m2, pressure_band):
    lnA = math.log(area_m2)
    if pressure_band == "Up to 700 kPag (base)":
        return 1.0
    elif pressure_band == "700–2100 kPag":
        return 0.8955 + 0.04981 * lnA
    elif pressure_band == "2100–4200 kPag":
        return 1.2002 + 0.07140 * lnA
    elif pressure_band == "4200–6200 kPag":
        return 1.4272 + 0.12088 * lnA
    else:
        raise ValueError("Invalid pressure band selected.")


def material_factor(area_m2, material):
    lnA = math.log(area_m2)
    if material == "Carbon steel (base)":
        return 1.0
    elif material == "SS304":
        return 1.1991 + 0.15984 * lnA
    elif material == "SS316":
        return 1.4144 + 0.23296 * lnA
    elif material == "SS347":
        return 1.1388 + 0.22186 * lnA
    elif material == "Nickel 200":
        return 2.9553 + 0.60859 * lnA
    elif material == "Monel 400":
        return 2.3296 + 0.43377 * lnA
    elif material == "Inconel 600":
        return 2.4103 + 0.50764 * lnA
    elif material == "Incoloy 825":
        return 2.3665 + 0.49706 * lnA
    elif material == "Titanium":
        return 2.5617 + 0.42913 * lnA
    elif material == "Hastelloy":
        return 3.7614 + 1.51774 * lnA
    else:
        raise ValueError("Invalid material selected.")


def calculate_shell_tube_cost(area_m2, exchanger_type, pressure_band, material, ci_base, ci_calc):
    cb = shell_tube_base_cost_si(area_m2)
    fd = exchanger_type_factor(area_m2, exchanger_type)
    fp = pressure_factor(area_m2, pressure_band)
    fm = material_factor(area_m2, material)
    purchased_cost = cb * fd * fp * fm
    updated_cost = purchased_cost * (ci_calc / ci_base)
    return {
        "base_cost": cb,
        "purchased_cost": purchased_cost,
        "updated_cost": updated_cost,
    }


def render_source_inputs(source_num, defaults):
    st.markdown(f"### Heat Source {source_num}")
    c1, c2 = st.columns(2)

    with c1:
        thi = st.number_input(
            f"Hot inlet temperature (°C) - Source {source_num}",
            value=defaults["thi"],
            key=f"src_thi_{source_num}"
        )
        mh = st.number_input(
            f"Hot mass flow (kg/s) - Source {source_num}",
            min_value=0.0001,
            value=defaults["mh"],
            step=0.1,
            format="%.4f",
            key=f"src_mh_{source_num}"
        )
        cph = st.number_input(
            f"Hot specific heat, c_p,h (J/kg-K) - Source {source_num}",
            min_value=1.0,
            value=defaults["cph"],
            step=10.0,
            key=f"src_cph_{source_num}"
        )

    with c2:
        area = st.number_input(
            f"HX area (m²) - Source {source_num}",
            min_value=0.0001,
            value=defaults["area"],
            step=0.1,
            key=f"src_area_{source_num}"
        )
        h_hot = st.number_input(
            f"h_hot (W/m²-K) - Source {source_num}",
            min_value=0.0001,
            value=defaults["h_hot"],
            step=10.0,
            key=f"src_h_hot_{source_num}"
        )

    st.markdown(f"#### Tube and cost data - Source {source_num}")
    d1, d2, d3 = st.columns(3)

    with d1:
        tube_thickness = st.number_input(
            f"Tube thickness, t (m) - Source {source_num}",
            min_value=0.000001,
            value=defaults["tube_thickness"],
            step=0.0001,
            format="%.6f",
            key=f"src_tube_thickness_{source_num}"
        )
        tube_k = st.number_input(
            f"Tube thermal conductivity, k (W/m-K) - Source {source_num}",
            min_value=0.0001,
            value=defaults["tube_k"],
            step=0.5,
            key=f"src_tube_k_{source_num}"
        )

    with d2:
        exchanger_type = st.selectbox(
            f"Exchanger type - Source {source_num}",
            ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            key=f"src_exchanger_type_{source_num}"
        )
        material = st.selectbox(
            f"Material - Source {source_num}",
            [
                "Carbon steel (base)", "SS304", "SS316", "SS347",
                "Nickel 200", "Monel 400", "Inconel 600",
                "Incoloy 825", "Titanium", "Hastelloy"
            ],
            key=f"src_material_{source_num}"
        )

    with d3:
        pressure_band = st.selectbox(
            f"Pressure band - Source {source_num}",
            ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"],
            key=f"src_pressure_band_{source_num}"
        )
        ci_base = st.number_input(
            f"Base cost index - Source {source_num}",
            min_value=0.0001,
            value=defaults["ci_base"],
            step=1.0,
            key=f"src_ci_base_{source_num}"
        )
        ci_calc = st.number_input(
            f"Calculation-year cost index - Source {source_num}",
            min_value=0.0001,
            value=defaults["ci_calc"],
            step=1.0,
            key=f"src_ci_calc_{source_num}"
        )

    return {
        "thi": thi,
        "mh": mh,
        "cph": cph,
        "area": area,
        "h_hot": h_hot,
        "tube_thickness": tube_thickness,
        "tube_k": tube_k,
        "exchanger_type": exchanger_type,
        "material": material,
        "pressure_band": pressure_band,
        "ci_base": ci_base,
        "ci_calc": ci_calc,
    }


def render_sink_inputs(sink_num, defaults):
    st.markdown(f"### Heat Sink {sink_num}")
    c1, c2 = st.columns(2)

    with c1:
        tci = st.number_input(
            f"Cold inlet temperature (°C) - Sink {sink_num}",
            value=defaults["tci"],
            key=f"snk_tci_{sink_num}"
        )
        mc = st.number_input(
            f"Cold mass flow (kg/s) - Sink {sink_num}",
            min_value=0.0001,
            value=defaults["mc"],
            step=0.1,
            format="%.4f",
            key=f"snk_mc_{sink_num}"
        )

    with c2:
        cpc = st.number_input(
            f"Cold specific heat, c_p,c (J/kg-K) - Sink {sink_num}",
            min_value=1.0,
            value=defaults["cpc"],
            step=10.0,
            key=f"snk_cpc_{sink_num}"
        )
        h_cold = st.number_input(
            f"h_cold (W/m²-K) - Sink {sink_num}",
            min_value=0.0001,
            value=defaults["h_cold"],
            step=10.0,
            key=f"snk_h_cold_{sink_num}"
        )

    return {
        "tci": tci,
        "mc": mc,
        "cpc": cpc,
        "h_cold": h_cold,
    }


source_defaults = {
    "thi": 120.0,
    "mh": 1.2,
    "cph": 2200.0,
    "area": 20.0,
    "h_hot": 1000.0,
    "tube_thickness": 0.001,
    "tube_k": 15.0,
    "ci_base": 500.0,
    "ci_calc": 800.0,
}

sink_defaults = {
    "tci": 25.0,
    "mc": 1.0,
    "cpc": 4180.0,
    "h_cold": 1500.0,
}

st.markdown("## 1) Enter heat-source data")
source_tabs = st.tabs([f"Source {i}" for i in range(1, 5)])
sources = []
for i, tab in enumerate(source_tabs, start=1):
    with tab:
        sources.append(render_source_inputs(i, source_defaults))

st.markdown("## 2) Enter heat-sink data")
sink_tabs = st.tabs([f"Sink {i}" for i in range(1, 5)])
sinks = []
for i, tab in enumerate(sink_tabs, start=1):
    with tab:
        sinks.append(render_sink_inputs(i, sink_defaults))

st.markdown("## 3) Choose source-to-sink matching")

sink_labels = [f"Sink {i}" for i in range(1, 5)]
selected_sinks = []

m1, m2, m3, m4 = st.columns(4)

with m1:
    match_1 = st.selectbox(
        "Source 1 →",
        options=sink_labels,
        key="match_1"
    )
    selected_sinks.append(match_1)

with m2:
    options_2 = [s for s in sink_labels if s not in selected_sinks]
    match_2 = st.selectbox(
        "Source 2 →",
        options=options_2,
        key="match_2"
    )
    selected_sinks.append(match_2)

with m3:
    options_3 = [s for s in sink_labels if s not in selected_sinks]
    match_3 = st.selectbox(
        "Source 3 →",
        options=options_3,
        key="match_3"
    )
    selected_sinks.append(match_3)

with m4:
    options_4 = [s for s in sink_labels if s not in selected_sinks]
    match_4 = st.selectbox(
        "Source 4 →",
        options=options_4,
        key="match_4"
    )
    selected_sinks.append(match_4)

matches = [match_1, match_2, match_3, match_4]

calculate = st.button("Calculate selected matches", type="primary")


if calculate:
    results_rows = []
    sink_index_map = {
        "Sink 1": 0,
        "Sink 2": 1,
        "Sink 3": 2,
        "Sink 4": 3,
    }

    if len(set(matches)) != 4:
        st.error("Each source must be assigned to a unique sink.")
    else:
        for i, sink_label in enumerate(matches, start=1):
            source = sources[i - 1]
            sink = sinks[sink_index_map[sink_label]]

            try:
                if source["thi"] <= sink["tci"]:
                    st.error(f"Source {i} matched with {sink_label}: hot inlet temperature must be greater than cold inlet temperature.")
                    continue

                if source["area"] <= 0:
                    st.error(f"Source {i}: heat exchanger area must be greater than zero.")
                    continue

                if (
                    source["h_hot"] <= 0
                    or sink["h_cold"] <= 0
                    or source["tube_thickness"] <= 0
                    or source["tube_k"] <= 0
                ):
                    st.error(f"Source {i} matched with {sink_label}: heat transfer coefficients, tube thickness, and tube conductivity must be greater than zero.")
                    continue

                u = calculate_overall_u(
                    source["h_hot"],
                    sink["h_cold"],
                    source["tube_thickness"],
                    source["tube_k"]
                )

                result = solve_known_mc(
                    source["thi"],
                    sink["tci"],
                    source["mh"],
                    sink["mc"],
                    source["cph"],
                    sink["cpc"],
                    u,
                    source["area"]
                )

                cost = calculate_shell_tube_cost(
                    source["area"],
                    source["exchanger_type"],
                    source["pressure_band"],
                    source["material"],
                    source["ci_base"],
                    source["ci_calc"]
                )

                results_rows.append({
                    "Source": f"Source {i}",
                    "Matched sink": sink_label,
                    "Hot outlet temp (°C)": f"{result['T_h_out']:.2f}",
                    "Cold outlet temp (°C)": f"{result['T_c_out']:.2f}",
                    "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                    "Overall U (W/m²-K)": f"{u:.2f}",
                    "NTU": f"{result['NTU']:.4f}",
                    "Effectiveness": f"{result['Effectiveness']:.4f}",
                    "HX cost ($)": f"${cost['updated_cost']:,.2f}",
                })

            except Exception as e:
                st.error(f"Source {i} matched with {sink_label}: {str(e)}")

        if results_rows:
            st.subheader("Matched-pair results")
            results_df = pd.DataFrame(results_rows)
            st.dataframe(results_df, use_container_width=True)
