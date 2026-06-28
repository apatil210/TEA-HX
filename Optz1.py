import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Heat Exchanger Design + Cost",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Design + Cost")
st.caption("Calculate performance and cost for up to 4 heat source-sink pairs.")


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


def render_case_inputs(case_num, defaults):
    st.markdown(f"## Pair {case_num}")

    col1, col2 = st.columns(2)

    with col1:
        thi = st.number_input(
            f"Hot Fluid Inlet Temperature (°C) - Pair {case_num}",
            value=defaults["thi"],
            key=f"thi_{case_num}"
        )
        tci = st.number_input(
            f"Initial Cold Fluid Temp (°C) - Pair {case_num}",
            value=defaults["tci"],
            key=f"tci_{case_num}"
        )
        mh = st.number_input(
            f"Mass Flow of Hot Fluid (kg/s) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["mh"],
            step=0.1,
            format="%.4f",
            key=f"mh_{case_num}"
        )
        mc = st.number_input(
            f"Mass Flow of Cold Fluid (kg/s) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["mc"],
            step=0.1,
            format="%.4f",
            key=f"mc_{case_num}"
        )

    with col2:
        area = st.number_input(
            f"HX Area (m²) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["area"],
            step=0.1,
            key=f"area_{case_num}"
        )
        h_hot = st.number_input(
            f"h_hot (W/m²-K) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["h_hot"],
            step=10.0,
            key=f"h_hot_{case_num}"
        )
        h_cold = st.number_input(
            f"h_cold (W/m²-K) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["h_cold"],
            step=10.0,
            key=f"h_cold_{case_num}"
        )

    st.markdown("### Tube properties")
    t1, t2 = st.columns(2)

    with t1:
        tube_thickness = st.number_input(
            f"Tube Thickness, t (m) - Pair {case_num}",
            min_value=0.000001,
            value=defaults["tube_thickness"],
            step=0.0001,
            format="%.6f",
            key=f"tube_thickness_{case_num}"
        )

    with t2:
        tube_k = st.number_input(
            f"Tube Thermal Conductivity, k (W/m-K) - Pair {case_num}",
            min_value=0.0001,
            value=defaults["tube_k"],
            step=0.5,
            key=f"tube_k_{case_num}"
        )

    st.markdown("### Fluid properties")
    p1, p2 = st.columns(2)

    with p1:
        cph = st.number_input(
            f"Hot Fluid Specific Heat, c_p,h (J/kg-K) - Pair {case_num}",
            min_value=1.0,
            value=defaults["cph"],
            step=10.0,
            key=f"cph_{case_num}"
        )

    with p2:
        cpc = st.number_input(
            f"Cold Fluid Specific Heat, c_p,c (J/kg-K) - Pair {case_num}",
            min_value=1.0,
            value=defaults["cpc"],
            step=10.0,
            key=f"cpc_{case_num}"
        )

    st.markdown("### Shell-and-tube cost inputs")
    c1, c2, c3 = st.columns(3)

    with c1:
        exchanger_type = st.selectbox(
            f"Exchanger type - Pair {case_num}",
            ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            index=["Floating head", "Fixed head", "U-tube", "Kettle reboiler"].index(defaults["exchanger_type"]),
            key=f"exchanger_type_{case_num}"
        )
        material = st.selectbox(
            f"Material - Pair {case_num}",
            [
                "Carbon steel (base)", "SS304", "SS316", "SS347",
                "Nickel 200", "Monel 400", "Inconel 600",
                "Incoloy 825", "Titanium", "Hastelloy"
            ],
            index=[
                "Carbon steel (base)", "SS304", "SS316", "SS347",
                "Nickel 200", "Monel 400", "Inconel 600",
                "Incoloy 825", "Titanium", "Hastelloy"
            ].index(defaults["material"]),
            key=f"material_{case_num}"
        )

    with c2:
        pressure_band = st.selectbox(
            f"Pressure band - Pair {case_num}",
            ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"],
            index=[
                "Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"
            ].index(defaults["pressure_band"]),
            key=f"pressure_band_{case_num}"
        )
        ci_base = st.number_input(
            f"Base cost index - Pair {case_num}",
            min_value=0.0001,
            value=defaults["ci_base"],
            step=1.0,
            key=f"ci_base_{case_num}"
        )

    with c3:
        ci_calc = st.number_input(
            f"Calculation-year cost index - Pair {case_num}",
            min_value=0.0001,
            value=defaults["ci_calc"],
            step=1.0,
            key=f"ci_calc_{case_num}"
        )

    return {
        "thi": thi,
        "tci": tci,
        "mh": mh,
        "mc": mc,
        "area": area,
        "h_hot": h_hot,
        "h_cold": h_cold,
        "tube_thickness": tube_thickness,
        "tube_k": tube_k,
        "cph": cph,
        "cpc": cpc,
        "exchanger_type": exchanger_type,
        "material": material,
        "pressure_band": pressure_band,
        "ci_base": ci_base,
        "ci_calc": ci_calc,
    }


default_case = {
    "thi": 120.0,
    "tci": 25.0,
    "mh": 1.2,
    "mc": 1.0,
    "area": 20.0,
    "h_hot": 1000.0,
    "h_cold": 1500.0,
    "tube_thickness": 0.001,
    "tube_k": 15.0,
    "cph": 2200.0,
    "cpc": 4180.0,
    "exchanger_type": "Floating head",
    "material": "Carbon steel (base)",
    "pressure_band": "Up to 700 kPag (base)",
    "ci_base": 500.0,
    "ci_calc": 800.0,
}

with st.form("hx_multi_case_form"):
    st.markdown("Enter data for 4 heat source-sink pairs.")

    tabs = st.tabs(["Pair 1", "Pair 2", "Pair 3", "Pair 4"])
    all_cases = []

    for i, tab in enumerate(tabs, start=1):
        with tab:
            case_inputs = render_case_inputs(i, default_case)
            all_cases.append(case_inputs)

    submitted = st.form_submit_button("Calculate All Pairs")


if submitted:
    results_rows = []
    has_error = False

    for i, case in enumerate(all_cases, start=1):
        try:
            if case["thi"] <= case["tci"]:
                st.error(f"Pair {i}: Hot inlet temperature must be greater than cold inlet temperature.")
                has_error = True
                continue

            if case["area"] <= 0:
                st.error(f"Pair {i}: Heat exchanger area must be greater than zero.")
                has_error = True
                continue

            if (
                case["h_hot"] <= 0
                or case["h_cold"] <= 0
                or case["tube_thickness"] <= 0
                or case["tube_k"] <= 0
            ):
                st.error(f"Pair {i}: Heat transfer coefficients, tube thickness, and tube thermal conductivity must be greater than zero.")
                has_error = True
                continue

            u = calculate_overall_u(
                case["h_hot"],
                case["h_cold"],
                case["tube_thickness"],
                case["tube_k"]
            )

            result = solve_known_mc(
                case["thi"],
                case["tci"],
                case["mh"],
                case["mc"],
                case["cph"],
                case["cpc"],
                u,
                case["area"]
            )

            cost = calculate_shell_tube_cost(
                case["area"],
                case["exchanger_type"],
                case["pressure_band"],
                case["material"],
                case["ci_base"],
                case["ci_calc"]
            )

            results_rows.append({
                "Pair": f"Pair {i}",
                "Hot outlet temp (°C)": f"{result['T_h_out']:.2f}",
                "Cold outlet temp (°C)": f"{result['T_c_out']:.2f}",
                "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                "Overall U (W/m²-K)": f"{u:.2f}",
                "NTU": f"{result['NTU']:.4f}",
                "Effectiveness": f"{result['Effectiveness']:.4f}",
                "HX cost ($)": f"${cost['updated_cost']:,.2f}",
            })

        except Exception as e:
            st.error(f"Pair {i}: {str(e)}")
            has_error = True

    if results_rows:
        st.subheader("Results for all pairs")
        results_df = pd.DataFrame(results_rows)
        st.dataframe(results_df, use_container_width=True)

    if not results_rows and has_error:
        st.warning("No valid pair could be calculated.")
