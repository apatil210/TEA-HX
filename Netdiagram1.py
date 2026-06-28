import math
import itertools
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(
    page_title="Heat Exchanger Tools",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Tools")
st.caption("Two tools in one Streamlit app: single heat-exchanger design/cost and heat-integration matching optimization.")


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


def style_temperature_cells(df_in, min_hot_outlet_temp, max_cold_outlet_temp):
    styles = pd.DataFrame("", index=df_in.index, columns=df_in.columns)

    hot_col = "Hot Outlet Temp (°C)"
    cold_col = "Cold Outlet Temp (°C)"

    styles.loc[df_in[hot_col] < min_hot_outlet_temp, hot_col] = (
        "background-color: #ff4d4f; color: white;"
    )
    styles.loc[df_in[cold_col] > max_cold_outlet_temp, cold_col] = (
        "background-color: #ff4d4f; color: white;"
    )

    return styles


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

    with c2:
        cph = st.number_input(
            f"Hot specific heat, c_p,h (J/kg-K) - Source {source_num}",
            min_value=1.0,
            value=defaults["cph"],
            step=10.0,
            key=f"src_cph_{source_num}"
        )
        h_hot = st.number_input(
            f"h_hot (W/m²-K) - Source {source_num}",
            min_value=0.0001,
            value=defaults["h_hot"],
            step=10.0,
            key=f"src_h_hot_{source_num}"
        )

    return {
        "thi": thi,
        "mh": mh,
        "cph": cph,
        "h_hot": h_hot,
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


def render_exchanger_inputs(hx_num, defaults):
    st.markdown(f"### Heat Exchanger {hx_num}")
    c1, c2, c3 = st.columns(3)

    with c1:
        area = st.number_input(
            f"HX area (m²) - HX {hx_num}",
            min_value=0.0001,
            value=defaults["area"],
            step=0.1,
            key=f"hx_area_{hx_num}"
        )
        tube_thickness = st.number_input(
            f"Tube thickness, t (m) - HX {hx_num}",
            min_value=0.000001,
            value=defaults["tube_thickness"],
            step=0.0001,
            format="%.6f",
            key=f"hx_tube_thickness_{hx_num}"
        )
        tube_k = st.number_input(
            f"Tube thermal conductivity, k (W/m-K) - HX {hx_num}",
            min_value=0.0001,
            value=defaults["tube_k"],
            step=0.5,
            key=f"hx_tube_k_{hx_num}"
        )

    with c2:
        exchanger_type = st.selectbox(
            f"Exchanger type - HX {hx_num}",
            ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            key=f"hx_exchanger_type_{hx_num}"
        )
        material = st.selectbox(
            f"Material - HX {hx_num}",
            [
                "Carbon steel (base)", "SS304", "SS316", "SS347",
                "Nickel 200", "Monel 400", "Inconel 600",
                "Incoloy 825", "Titanium", "Hastelloy"
            ],
            key=f"hx_material_{hx_num}"
        )

    with c3:
        pressure_band = st.selectbox(
            f"Pressure band - HX {hx_num}",
            ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"],
            key=f"hx_pressure_band_{hx_num}"
        )
        ci_base = st.number_input(
            f"Base cost index - HX {hx_num}",
            min_value=0.0001,
            value=defaults["ci_base"],
            step=1.0,
            key=f"hx_ci_base_{hx_num}"
        )
        ci_calc = st.number_input(
            f"Calculation-year cost index - HX {hx_num}",
            min_value=0.0001,
            value=defaults["ci_calc"],
            step=1.0,
            key=f"hx_ci_calc_{hx_num}"
        )

    return {
        "area": area,
        "tube_thickness": tube_thickness,
        "tube_k": tube_k,
        "exchanger_type": exchanger_type,
        "material": material,
        "pressure_band": pressure_band,
        "ci_base": ci_base,
        "ci_calc": ci_calc,
    }


def reset_invalid_choice(widget_key, valid_options):
    if widget_key in st.session_state and st.session_state[widget_key] not in valid_options:
        del st.session_state[widget_key]


tab1, tab2 = st.tabs([
    "Single HX Design + Cost",
    "Heat Integration Matching"
])

with tab1:
    st.header("Heat Exchanger Design + Cost")

    with st.form("ntu_single_case_form"):
        st.markdown("## Input values")
        col1, col2 = st.columns(2)

        with col1:
            thi = st.number_input("Hot Fluid Inlet Temperature (°C)", value=120.0)
            tci = st.number_input("Initial Cold Fluid Temp (avg T of return water) (°C)", value=25.0)
            mh = st.number_input("Mass Flow of Hot Fluid (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")
            mc = st.number_input("Mass Flow of Cold Fluid (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
            min_hot_outlet_temp = st.number_input("Min outlet temperature for hot fluid (°C)", value=60.0)
            max_cold_outlet_temp = st.number_input("Max outlet temperature for cold fluid (°C)", value=80.0)

        with col2:
            area = st.number_input("Value of HX area (m²)", min_value=0.0001, value=20.0, step=0.1)
            h_hot = st.number_input("HT Coeff of Hot Fluid, h_hot (W/m²-K)", min_value=0.0001, value=1000.0, step=10.0)
            h_cold = st.number_input("HT Coeff of Cold Fluid, h_cold (W/m²-K)", min_value=0.0001, value=1500.0, step=10.0)

        st.markdown("## Tube properties")
        t1, t2 = st.columns(2)

        with t1:
            tube_thickness = st.number_input(
                "Tube Thickness, t (m)",
                min_value=0.000001,
                value=0.001,
                step=0.0001,
                format="%.6f"
            )

        with t2:
            tube_k = st.number_input("Tube Therm Cond, k (W/m-K)", min_value=0.0001, value=15.0, step=0.5)

        st.markdown("## Fluid properties")
        p1, p2 = st.columns(2)

        with p1:
            cph = st.number_input("Hot Fluid Specific Heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)

        with p2:
            cpc = st.number_input("Cold Fluid Specific Heat, c_p,c (Water) (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)

        st.markdown("## Shell-and-tube cost inputs")
        c1, c2, c3 = st.columns(3)

        with c1:
            exchanger_type = st.selectbox(
                "Exchanger type",
                ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"]
            )
            material = st.selectbox(
                "Material of construction",
                [
                    "Carbon steel (base)", "SS304", "SS316", "SS347",
                    "Nickel 200", "Monel 400", "Inconel 600",
                    "Incoloy 825", "Titanium", "Hastelloy"
                ]
            )

        with c2:
            pressure_band = st.selectbox(
                "Design pressure band",
                ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"]
            )
            ci_base = st.number_input("Base cost index", min_value=0.0001, value=500.0, step=1.0)

        with c3:
            ci_calc = st.number_input("Calculation-year cost index", min_value=0.0001, value=800.0, step=1.0)

        submitted = st.form_submit_button("Calculate 10 Iterations")

    if submitted:
        try:
            if thi <= tci:
                st.error("Hot inlet temperature must be greater than cold inlet temperature.")
            elif area <= 0:
                st.error("Heat exchanger area must be greater than zero.")
            elif h_hot <= 0 or h_cold <= 0 or tube_thickness <= 0 or tube_k <= 0:
                st.error("Heat transfer coefficients, tube thickness, and tube thermal conductivity must be greater than zero.")
            else:
                u = calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k)

                rows = []
                for i in range(10):
                    iter_area = area * (1.2 ** i)
                    result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, iter_area)
                    cost = calculate_shell_tube_cost(
                        iter_area,
                        exchanger_type,
                        pressure_band,
                        material,
                        ci_base,
                        ci_calc
                    )

                    rows.append({
                        "Iteration": i + 1,
                        "Area_m2": iter_area,
                        "T_h_in_C": thi,
                        "T_h_out_C": result["T_h_out"],
                        "T_c_in_C": tci,
                        "T_c_out_C": result["T_c_out"],
                        "U_W_m2K": u,
                        "UA_W_K": result["UA"],
                        "NTU": result["NTU"],
                        "Effectiveness": result["Effectiveness"],
                        "Q_kW": result["Q_kW"],
                        "HX_Cost_USD": cost["updated_cost"],
                    })

                df = pd.DataFrame(rows)

                st.subheader("Iteration table")
                df_display = df[
                    [
                        "Area_m2",
                        "T_h_in_C",
                        "T_h_out_C",
                        "T_c_in_C",
                        "T_c_out_C",
                        "Q_kW",
                        "HX_Cost_USD",
                    ]
                ].rename(columns={
                    "Area_m2": "Area (m²)",
                    "T_h_in_C": "Hot Inlet Temp (°C)",
                    "T_h_out_C": "Hot Outlet Temp (°C)",
                    "T_c_in_C": "Cold Inlet Temp (°C)",
                    "T_c_out_C": "Cold Outlet Temp (°C)",
                    "Q_kW": "Heat Duty (kW)",
                    "HX_Cost_USD": "HX Cost ($)",
                })

                styled_df = (
                    df_display.style
                    .apply(
                        style_temperature_cells,
                        axis=None,
                        min_hot_outlet_temp=min_hot_outlet_temp,
                        max_cold_outlet_temp=max_cold_outlet_temp,
                    )
                    .format({
                        "Area (m²)": "{:.4f}",
                        "Hot Inlet Temp (°C)": "{:.2f}",
                        "Hot Outlet Temp (°C)": "{:.2f}",
                        "Cold Inlet Temp (°C)": "{:.2f}",
                        "Cold Outlet Temp (°C)": "{:.2f}",
                        "Heat Duty (kW)": "{:.4f}",
                        "HX Cost ($)": "${:,.2f}",
                    })
                )

                st.dataframe(
                    styled_df,
                    use_container_width=True
                )

                st.subheader("Minimum Cost Heat Exchanger Configuration")

                valid_mask = (
                    (df["T_h_out_C"] >= min_hot_outlet_temp) &
                    (df["T_c_out_C"] <= max_cold_outlet_temp)
                )

                valid_rows = df[valid_mask]

                if not valid_rows.empty:
                    best_row = valid_rows.loc[valid_rows["HX_Cost_USD"].idxmin()]

                    result_data = pd.DataFrame({
                        "Parameter": [
                            "Hot fluid inlet temperature (°C)",
                            "Hot fluid outlet temperature (°C)",
                            "Cold fluid inlet temperature (°C)",
                            "Cold fluid outlet temperature (°C)",
                            "Heat Exchanger (HX) duty (kW)",
                            "Heat Exchanger cost ($)"
                        ],
                        "Value": [
                            f"{best_row['T_h_in_C']:.2f}",
                            f"{best_row['T_h_out_C']:.2f}",
                            f"{best_row['T_c_in_C']:.2f}",
                            f"{best_row['T_c_out_C']:.2f}",
                            f"{best_row['Q_kW']:.4f}",
                            f"${best_row['HX_Cost_USD']:,.2f}"
                        ]
                    })

                    st.table(result_data)
                else:
                    st.info("No minimum cost condition reached.")

                st.subheader("Heat Exchanger Cost vs Heat Duty")

                base = alt.Chart(df).encode(
                    x=alt.X("Q_kW:Q", title="Heat Duty (kW)"),
                    y=alt.Y("HX_Cost_USD:Q", title="HX Cost ($)")
                )

                line = base.mark_line()
                points = base.mark_point(filled=True, size=80)

                chart = (line + points).interactive()

                st.altair_chart(chart, use_container_width=True)

                csv = df_display.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download results as CSV",
                    data=csv,
                    file_name="heat_exchanger_iteration_results.csv",
                    mime="text/csv"
                )

        except Exception as e:
            st.error(str(e))

with tab2:
    st.header("Heat Integration Cost Optimization")
    st.caption(
        "Enter 4 heat sources, 4 heat sinks, and 4 heat exchangers, "
        "then assign each source to one unique sink and one unique exchanger."
    )

    source_defaults = {
        "thi": 120.0,
        "mh": 1.2,
        "cph": 2200.0,
        "h_hot": 1000.0,
    }

    sink_defaults = {
        "tci": 25.0,
        "mc": 1.0,
        "cpc": 4180.0,
        "h_cold": 1500.0,
    }

    hx_defaults = {
        "area": 20.0,
        "tube_thickness": 0.001,
        "tube_k": 15.0,
        "ci_base": 500.0,
        "ci_calc": 800.0,
    }

    if "matched_results_df" not in st.session_state:
        st.session_state.matched_results_df = None
    if "matched_total_cost" not in st.session_state:
        st.session_state.matched_total_cost = None
    if "matched_total_heat_duty" not in st.session_state:
        st.session_state.matched_total_heat_duty = None

    if "optimized_results_df" not in st.session_state:
        st.session_state.optimized_results_df = None
    if "optimized_total_cost" not in st.session_state:
        st.session_state.optimized_total_cost = None
    if "optimized_total_q" not in st.session_state:
        st.session_state.optimized_total_q = None
    if "optimized_feasible_count" not in st.session_state:
        st.session_state.optimized_feasible_count = None

    st.markdown("## Inputs for Heat sources")
    source_tabs = st.tabs([f"Source {i}" for i in range(1, 5)])
    sources = []
    for i, tab in enumerate(source_tabs, start=1):
        with tab:
            sources.append(render_source_inputs(i, source_defaults))

    st.markdown("## Inputs for Heat sinks")
    sink_tabs = st.tabs([f"Sink {i}" for i in range(1, 5)])
    sinks = []
    for i, tab in enumerate(sink_tabs, start=1):
        with tab:
            sinks.append(render_sink_inputs(i, sink_defaults))

    st.markdown("## Inputs for Heat exchangers")
    hx_tabs = st.tabs([f"HX {i}" for i in range(1, 5)])
    exchangers = []
    for i, tab in enumerate(hx_tabs, start=1):
        with tab:
            exchangers.append(render_exchanger_inputs(i, hx_defaults))

    st.markdown("## Assign sinks and exchangers to each source")

    sink_labels = [f"Sink {i}" for i in range(1, 5)]
    hx_labels = [f"HX {i}" for i in range(1, 5)]

    selected_sinks = []
    selected_hx = []

    for i in range(1, 5):
        st.markdown(f"### Matching for Source {i}")
        c1, c2 = st.columns(2)

        remaining_sinks = [s for s in sink_labels if s not in selected_sinks]
        remaining_hx = [h for h in hx_labels if h not in selected_hx]

        sink_key = f"match_sink_{i}"
        hx_key = f"match_hx_{i}"

        reset_invalid_choice(sink_key, remaining_sinks)
        reset_invalid_choice(hx_key, remaining_hx)

        with c1:
            sink_choice = st.selectbox(
                f"Choose sink for Source {i}",
                options=remaining_sinks,
                key=sink_key
            )

        selected_sinks.append(sink_choice)

        remaining_hx = [h for h in hx_labels if h not in selected_hx]
        reset_invalid_choice(hx_key, remaining_hx)

        with c2:
            hx_choice = st.selectbox(
                f"Choose exchanger for Source {i}",
                options=remaining_hx,
                key=hx_key
            )

        selected_hx.append(hx_choice)

    calculate = st.button("Calculate results for matched system")

    if calculate:
        results_rows = []

        sink_index_map = {f"Sink {i}": i - 1 for i in range(1, 5)}
        hx_index_map = {f"HX {i}": i - 1 for i in range(1, 5)}

        if len(set(selected_sinks)) != 4:
            st.error("Each source must be assigned to a unique sink.")
        elif len(set(selected_hx)) != 4:
            st.error("Each source must be assigned to a unique heat exchanger.")
        else:
            for i in range(1, 5):
                source = sources[i - 1]
                sink = sinks[sink_index_map[selected_sinks[i - 1]]]
                hx = exchangers[hx_index_map[selected_hx[i - 1]]]

                try:
                    if source["thi"] <= sink["tci"]:
                        st.error(
                            f"Source {i}: hot inlet temperature must be greater "
                            f"than the selected sink cold inlet temperature."
                        )
                        continue

                    if hx["area"] <= 0:
                        st.error(f"Source {i}: exchanger area must be greater than zero.")
                        continue

                    if (
                        source["h_hot"] <= 0
                        or sink["h_cold"] <= 0
                        or hx["tube_thickness"] <= 0
                        or hx["tube_k"] <= 0
                    ):
                        st.error(f"Source {i}: invalid heat-transfer or tube-property input.")
                        continue

                    u = calculate_overall_u(
                        source["h_hot"],
                        sink["h_cold"],
                        hx["tube_thickness"],
                        hx["tube_k"]
                    )

                    result = solve_known_mc(
                        source["thi"],
                        sink["tci"],
                        source["mh"],
                        sink["mc"],
                        source["cph"],
                        sink["cpc"],
                        u,
                        hx["area"]
                    )

                    cost = calculate_shell_tube_cost(
                        hx["area"],
                        hx["exchanger_type"],
                        hx["pressure_band"],
                        hx["material"],
                        hx["ci_base"],
                        hx["ci_calc"]
                    )

                    results_rows.append({
                        "Source": f"Source {i}",
                        "Sink": selected_sinks[i - 1],
                        "Exchanger": selected_hx[i - 1],
                        "Hot outlet temp (°C)": f"{result['T_h_out']:.2f}",
                        "Cold outlet temp (°C)": f"{result['T_c_out']:.2f}",
                        "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                        "Overall U (W/m²-K)": f"{u:.2f}",
                        "NTU": f"{result['NTU']:.4f}",
                        "Effectiveness": f"{result['Effectiveness']:.4f}",
                        "HX cost ($)": f"${cost['updated_cost']:,.2f}",
                        "HX cost numeric": cost["updated_cost"],
                        "Heat duty numeric": result["Q_kW"],
                    })

                except Exception as e:
                    st.error(f"Source {i}: {str(e)}")

        if results_rows:
            results_df = pd.DataFrame(results_rows)
            st.session_state.matched_total_cost = results_df["HX cost numeric"].sum()
            st.session_state.matched_total_heat_duty = results_df["Heat duty numeric"].sum()
            st.session_state.matched_results_df = results_df.drop(
                columns=["HX cost numeric", "Heat duty numeric"]
            )

    

    optimize = st.button("Click to Optimize for maximum heat integration", type="secondary")
    st.markdown("## Results")
    
    if optimize:
        best_solution = None
        best_total_cost = None
        best_total_q = None
        feasible_count = 0

        sink_permutations = list(itertools.permutations(range(4)))
        hx_permutations = list(itertools.permutations(range(4)))

        for sink_perm in sink_permutations:
            for hx_perm in hx_permutations:
                current_rows = []
                current_total_cost = 0.0
                current_total_q = 0.0
                feasible = True

                for i in range(4):
                    source = sources[i]
                    sink = sinks[sink_perm[i]]
                    hx = exchangers[hx_perm[i]]

                    try:
                        if source["thi"] <= sink["tci"]:
                            feasible = False
                            break

                        if hx["area"] <= 0:
                            feasible = False
                            break

                        if (
                            source["h_hot"] <= 0
                            or sink["h_cold"] <= 0
                            or hx["tube_thickness"] <= 0
                            or hx["tube_k"] <= 0
                        ):
                            feasible = False
                            break

                        u = calculate_overall_u(
                            source["h_hot"],
                            sink["h_cold"],
                            hx["tube_thickness"],
                            hx["tube_k"]
                        )

                        result = solve_known_mc(
                            source["thi"],
                            sink["tci"],
                            source["mh"],
                            sink["mc"],
                            source["cph"],
                            sink["cpc"],
                            u,
                            hx["area"]
                        )

                        cost = calculate_shell_tube_cost(
                            hx["area"],
                            hx["exchanger_type"],
                            hx["pressure_band"],
                            hx["material"],
                            hx["ci_base"],
                            hx["ci_calc"]
                        )

                        current_total_cost += cost["updated_cost"]
                        current_total_q += result["Q_kW"]

                        current_rows.append({
                            "Source": f"Source {i + 1}",
                            "Sink": f"Sink {sink_perm[i] + 1}",
                            "Exchanger": f"HX {hx_perm[i] + 1}",
                            "Hot outlet temp (°C)": f"{result['T_h_out']:.2f}",
                            "Cold outlet temp (°C)": f"{result['T_c_out']:.2f}",
                            "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                            "Overall U (W/m²-K)": f"{u:.2f}",
                            "NTU": f"{result['NTU']:.4f}",
                            "Effectiveness": f"{result['Effectiveness']:.4f}",
                            "HX cost ($)": f"${cost['updated_cost']:,.2f}",
                        })

                    except Exception:
                        feasible = False
                        break

                if feasible:
                    feasible_count += 1

                    if (
                        best_solution is None
                        or current_total_q > best_total_q
                        or (
                            abs(current_total_q - best_total_q) < 1e-9
                            and current_total_cost < best_total_cost
                        )
                    ):
                        best_solution = current_rows
                        best_total_cost = current_total_cost
                        best_total_q = current_total_q

        if best_solution is not None:
            st.session_state.optimized_results_df = pd.DataFrame(best_solution)
            st.session_state.optimized_total_cost = best_total_cost
            st.session_state.optimized_total_q = best_total_q
            st.session_state.optimized_feasible_count = feasible_count
        else:
            st.session_state.optimized_results_df = None
            st.session_state.optimized_total_cost = None
            st.session_state.optimized_total_q = None
            st.session_state.optimized_feasible_count = 0

    if st.session_state.matched_results_df is not None:
        st.subheader("Matched results")
        st.dataframe(st.session_state.matched_results_df, use_container_width=True)

        # st.markdown("## 5) Total cost of heat integration")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total cost of heat integration for selected pairs", f"${st.session_state.matched_total_cost:,.2f}")
        with c2:
            st.metric("Total heat integration for selected pairs", f"{st.session_state.matched_total_heat_duty:.4f} kW")

    if st.session_state.optimized_results_df is not None:
        st.subheader("Optimal matched results for maximum heat integration")
        st.dataframe(st.session_state.optimized_results_df, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Maximum total heat integration", f"{st.session_state.optimized_total_q:.4f} kW")
        with c2:
            st.metric("Cost for maximum heat integration", f"${st.session_state.optimized_total_cost:,.2f}")

        total_assignments = math.factorial(4) * math.factorial(4)
        st.caption(
            f"Feasible assignments found: {st.session_state.optimized_feasible_count} "
            f"out of {total_assignments} total assignments checked."
        )
    elif optimize:
        st.warning("No feasible one-to-one assignment found for the given inputs.")
        
