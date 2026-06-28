import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Heat Exchanger Design + Cost",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Design + Cost")
st.caption("4 hot/cold stream pairs using the same heat exchanger design and cost basis.")


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


NUM_PAIRS = 4

with st.form("hx_multi_case_form"):
    st.markdown("## Shared heat exchanger inputs")
    col1, col2 = st.columns(2)

    with col1:
        area = st.number_input("Value of HX area (m²)", min_value=0.0001, value=20.0, step=0.1)
        h_hot = st.number_input("HT Coeff of Hot Fluid, h_hot (W/m²-K)", min_value=0.0001, value=1000.0, step=10.0)
        h_cold = st.number_input("HT Coeff of Cold Fluid, h_cold (W/m²-K)", min_value=0.0001, value=1500.0, step=10.0)

    with col2:
        tube_thickness = st.number_input(
            "Tube Thickness, t (m)",
            min_value=0.000001,
            value=0.001,
            step=0.0001,
            format="%.6f"
        )
        tube_k = st.number_input("Tube Therm Cond, k (W/m-K)", min_value=0.0001, value=15.0, step=0.5)

    st.markdown("## Shared shell-and-tube cost inputs")
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

    st.markdown("## Inputs for 4 heat source-sink pairs")

    pair_inputs = []
    tabs = st.tabs([f"Pair {i}" for i in range(1, NUM_PAIRS + 1)])

    default_values = [
        {"thi": 120.0, "tci": 25.0, "mh": 1.2, "mc": 1.0, "cph": 2200.0, "cpc": 4180.0},
        {"thi": 115.0, "tci": 25.0, "mh": 1.1, "mc": 1.0, "cph": 2200.0, "cpc": 4180.0},
        {"thi": 110.0, "tci": 25.0, "mh": 1.0, "mc": 1.0, "cph": 2200.0, "cpc": 4180.0},
        {"thi": 105.0, "tci": 25.0, "mh": 0.9, "mc": 1.0, "cph": 2200.0, "cpc": 4180.0},
    ]

    for i, tab in enumerate(tabs, start=1):
        with tab:
            st.markdown(f"### Pair {i}")
            pcol1, pcol2 = st.columns(2)

            with pcol1:
                thi = st.number_input(
                    f"Hot Fluid Inlet Temperature (°C) - Pair {i}",
                    value=default_values[i - 1]["thi"],
                    key=f"thi_{i}"
                )
                tci = st.number_input(
                    f"Initial Cold Fluid Temp (°C) - Pair {i}",
                    value=default_values[i - 1]["tci"],
                    key=f"tci_{i}"
                )
                mh = st.number_input(
                    f"Mass Flow of Hot Fluid (kg/s) - Pair {i}",
                    min_value=0.0001,
                    value=default_values[i - 1]["mh"],
                    step=0.1,
                    format="%.4f",
                    key=f"mh_{i}"
                )

            with pcol2:
                mc = st.number_input(
                    f"Mass Flow of Cold Fluid (kg/s) - Pair {i}",
                    min_value=0.0001,
                    value=default_values[i - 1]["mc"],
                    step=0.1,
                    format="%.4f",
                    key=f"mc_{i}"
                )
                cph = st.number_input(
                    f"Hot Fluid Specific Heat, c_p,h (J/kg-K) - Pair {i}",
                    min_value=1.0,
                    value=default_values[i - 1]["cph"],
                    step=10.0,
                    key=f"cph_{i}"
                )
                cpc = st.number_input(
                    f"Cold Fluid Specific Heat, c_p,c (J/kg-K) - Pair {i}",
                    min_value=1.0,
                    value=default_values[i - 1]["cpc"],
                    step=10.0,
                    key=f"cpc_{i}"
                )

            pair_inputs.append({
                "pair": i,
                "thi": thi,
                "tci": tci,
                "mh": mh,
                "mc": mc,
                "cph": cph,
                "cpc": cpc
            })

    submitted = st.form_submit_button("Calculate all 4 pairs")


if submitted:
    try:
        validation_errors = []

        if area <= 0:
            validation_errors.append("Heat exchanger area must be greater than zero.")
        if h_hot <= 0 or h_cold <= 0 or tube_thickness <= 0 or tube_k <= 0:
            validation_errors.append(
                "Heat transfer coefficients, tube thickness, and tube thermal conductivity must be greater than zero."
            )

        for pair in pair_inputs:
            if pair["thi"] <= pair["tci"]:
                validation_errors.append(
                    f"Pair {pair['pair']}: Hot inlet temperature must be greater than cold inlet temperature."
                )
            if pair["mh"] <= 0 or pair["mc"] <= 0:
                validation_errors.append(
                    f"Pair {pair['pair']}: Mass flow rates must be greater than zero."
                )
            if pair["cph"] <= 0 or pair["cpc"] <= 0:
                validation_errors.append(
                    f"Pair {pair['pair']}: Specific heats must be greater than zero."
                )

        if validation_errors:
            for err in validation_errors:
                st.error(err)
        else:
            u = calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k)
            cost = calculate_shell_tube_cost(
                area,
                exchanger_type,
                pressure_band,
                material,
                ci_base,
                ci_calc
            )

            results_rows = []

            for pair in pair_inputs:
                result = solve_known_mc(
                    pair["thi"],
                    pair["tci"],
                    pair["mh"],
                    pair["mc"],
                    pair["cph"],
                    pair["cpc"],
                    u,
                    area
                )

                results_rows.append({
                    "Pair": f"Pair {pair['pair']}",
                    "Hot inlet (°C)": f"{pair['thi']:.2f}",
                    "Cold inlet (°C)": f"{pair['tci']:.2f}",
                    "Hot outlet (°C)": f"{result['T_h_out']:.2f}",
                    "Cold outlet (°C)": f"{result['T_c_out']:.2f}",
                    "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                    "UA (W/K)": f"{result['UA']:.2f}",
                    "NTU": f"{result['NTU']:.4f}",
                    "Effectiveness": f"{result['Effectiveness']:.4f}",
                })

            results_df = pd.DataFrame(results_rows)

            st.subheader("Results for all 4 pairs")
            st.table(results_df)

            st.subheader("Shared heat exchanger summary")
            shared_df = pd.DataFrame({
                "Parameter": [
                    "Overall heat transfer coefficient, U (W/m²-K)",
                    "Heat exchanger area (m²)",
                    "Shared exchanger cost ($)"
                ],
                "Value": [
                    f"{u:.2f}",
                    f"{area:.2f}",
                    f"${cost['updated_cost']:,.2f}"
                ]
            })
            st.table(shared_df)

    except Exception as e:
        st.error(str(e))
