import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Heat Exchanger Design + Cost",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Design + Cost")


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
                iter_area = area * (1.05 ** i)
                result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, iter_area)
                cost = calculate_shell_tube_cost(
                    iter_area,
                    exchanger_type,
                    pressure_band,
                    material,
                    ci_base,
                    ci_calc
                )

                hot_violation = result["T_h_out"] < min_hot_outlet_temp
                cold_violation = result["T_c_out"] > max_cold_outlet_temp
                mark_red = hot_violation or cold_violation

                rows.append({
                    "Iteration": i + 1,
                    "Area_m2": iter_area,
                    "T_h_in_C": thi,
                    "T_h_out_C": result["T_h_out"],
                    "T_c_in_C": tci,
                    "T_c_out_C": result["T_c_out"],
                    "Q_kW": result["Q_kW"],
                    "HX_Cost_USD": cost["updated_cost"],
                    "Mark_Red": mark_red,
                })

            df = pd.DataFrame(rows)

            def highlight_rows(row):
                if row["Mark_Red"]:
                    return ["background-color: red; color: white;"] * len(row)
                return [""] * len(row)

            df_display = df[
                [
                    "Area_m2",
                    "T_h_in_C",
                    "T_h_out_C",
                    "T_c_in_C",
                    "T_c_out_C",
                    "Q_kW",
                    "HX_Cost_USD",
                    "Mark_Red",
                ]
            ].rename(columns={
                "Area_m2": "Area (m²)",
                "T_h_in_C": "Hot Inlet Temp (°C)",
                "T_h_out_C": "Hot Outlet Temp (°C)",
                "T_c_in_C": "Cold Inlet Temp (°C)",
                "T_c_out_C": "Cold Outlet Temp (°C)",
                "Q_kW": "Heat Duty (kW)",
                "HX_Cost_USD": "HX Cost ($)",
                "Mark_Red": "Constraint Violation",
            })

            styled_df = (
                df_display.style
                .apply(highlight_rows, axis=1)
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

            st.subheader("Results table")
            st.dataframe(styled_df, use_container_width=True)

            st.subheader("Heat Duty and Cost vs Iteration")
            chart_q_cost = df.set_index("Iteration")[["Q_kW", "HX_Cost_USD"]]
            st.line_chart(chart_q_cost)

            st.subheader("Outlet Temperatures vs Iteration")
            chart_temp = df.set_index("Iteration")[["T_h_out_C", "T_c_out_C"]]
            st.line_chart(chart_temp)

            st.subheader("Area progression")
            chart_area = df.set_index("Iteration")[["Area_m2"]]
            st.line_chart(chart_area)

            csv = df_display.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="heat_exchanger_iteration_results.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(str(e))
