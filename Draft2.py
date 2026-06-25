import math
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="NTU Heat Exchanger + Cost Sweep",
    page_icon="♨️",
    layout="wide"
)

st.title("NTU Heat Exchanger + Cost Sweep")
st.write(
    "Calculate outlet temperatures, exchanger cost, and perform an area sweep with "
    "10 points at 5% area increments to find the minimum cost."
)

with st.expander("Equations used", expanded=False):
    st.markdown(r"""
### NTU / Effectiveness model
- Heat capacity rates: \(C_h = \dot m_h c_{p,h}\), \(C_c = \dot m_c c_{p,c}\)
- Total conductance: \(UA = U \times A\)
- Capacity ratio: \(C_r = C_{min}/C_{max}\)
- NTU: \(NTU = UA/C_{min}\)
- Counter-flow effectiveness:
  - for \(C_r \neq 1\): \(\varepsilon = \frac{1-e^{-NTU(1-C_r)}}{1-C_r e^{-NTU(1-C_r)}}\)
  - for \(C_r = 1\): \(\varepsilon = \frac{NTU}{1+NTU}\)
- Heat transfer: \(Q = \varepsilon C_{min}(T_{h,i}-T_{c,i})\)
- Outlet temperatures:
  - \(T_{h,o} = T_{h,i} - Q/C_h\)
  - \(T_{c,o} = T_{c,i} + Q/C_c\)

### Cost model
- Hot-side conductance: \(\alpha = U_h A_h\)
- Cold-side conductance: \(\beta = U_c A_c\)
- Unit conductance cost fit:
  - \(C(\alpha) = a\alpha^b + c\)
- Side exchanger cost:
  - \(\text{Cost}_{hot} = \alpha(a_h\alpha^{b_h}+c_h)\)
  - \(\text{Cost}_{cold} = \beta(a_c\beta^{b_c}+c_c)\)
- Total exchanger cost:
  - \(\text{Cost}_{HX,total} = \text{Cost}_{hot} + \text{Cost}_{cold}\)

### Area sweep
- \(A_n = A_0(1.05)^n\), for \(n = 0,1,\dots,9\)
""")

COST_DATABASE = {
    "Scenario 1: <100C, water-water / water-aircooled": {
        "hot": {"label": "Plate HX", "a": 517.37, "b": 0.82, "c": 0.03},
        "cold": {"label": "Air-cooled HX", "a": 18023, "b": -0.90, "c": 0.90},
    },
    "Scenario 1: 100-175C, organic-organic / organic-aircooled": {
        "hot": {"label": "Plate HX", "a": 348.61, "b": -0.75, "c": 0.13},
        "cold": {"label": "Air-cooled HX", "a": 13417, "b": -0.85, "c": 1.66},
    },
    "Scenario 1: 175-400C, organic-organic / organic-aircooled": {
        "hot": {"label": "Double pipe HX", "a": 1255.1, "b": -0.74, "c": 0.35},
        "cold": {"label": "Air-cooled HX", "a": 13417, "b": -0.85, "c": 1.66},
    },
    "Scenario 1: >400C, molten salt-molten salt / organic-aircooled": {
        "hot": {"label": "Shell-and-tube HX", "a": 6166, "b": -0.88, "c": 1.89},
        "cold": {"label": "Air-cooled HX", "a": 13417, "b": -0.85, "c": 1.66},
    },
    "Scenario 2: <100C, water-air / water-aircooled": {
        "hot": {"label": "Shell-and-tube HX", "a": 56401, "b": -0.87, "c": 1.53},
        "cold": {"label": "Air-cooled HX", "a": 18023, "b": -0.90, "c": 0.90},
    },
    "Scenario 2: 100-400C, organic-air / organic-aircooled": {
        "hot": {"label": "Shell-and-tube HX", "a": 59043, "b": -0.87, "c": 1.58},
        "cold": {"label": "Air-cooled HX", "a": 13417, "b": -0.85, "c": 1.66},
    },
    "Scenario 2: >400C, molten salt-air / organic-aircooled": {
        "hot": {"label": "Shell-and-tube HX", "a": 60557, "b": -0.87, "c": 2.44},
        "cold": {"label": "Air-cooled HX", "a": 13417, "b": -0.85, "c": 1.66},
    },
}

def counterflow_effectiveness(ntu: float, cr: float) -> float:
    if ntu <= 0:
        return 0.0
    if abs(cr - 1.0) < 1e-9:
        return ntu / (1.0 + ntu)
    e = math.exp(-ntu * (1.0 - cr))
    return (1.0 - e) / (1.0 - cr * e)

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
        "U": u,
        "A": area,
        "UA": ua,
        "C_h": ch,
        "C_c": cc,
        "C_min": cmin,
        "C_max": cmax,
        "C_r": cr,
        "NTU": ntu,
        "epsilon": eps,
        "Q": q,
        "T_h_out": tho,
        "T_c_out": tco,
    }

def solve_from_target_q_tco(thi, tci, mh, cph, cpc, u, area, q_target, tco_target):
    delta_tc = tco_target - tci
    if delta_tc <= 0:
        raise ValueError("Target cold outlet temperature must be greater than cold inlet temperature.")
    mc = q_target / (cpc * delta_tc)
    results = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area)
    results["m_c"] = mc
    results["Q_target"] = q_target
    results["T_c_out_target"] = tco_target
    results["Q_error_pct"] = ((results["Q"] - q_target) / q_target * 100.0) if q_target != 0 else 0.0
    return results

def unit_cost_from_conductance(x, a, b, c):
    return a * (x ** b) + c

def side_exchanger_cost(x, a, b, c):
    return x * unit_cost_from_conductance(x, a, b, c)

def total_exchanger_cost(alpha, beta, scenario_name):
    scenario = COST_DATABASE[scenario_name]
    hot = scenario["hot"]
    cold = scenario["cold"]

    hot_unit_cost = unit_cost_from_conductance(alpha, hot["a"], hot["b"], hot["c"])
    cold_unit_cost = unit_cost_from_conductance(beta, cold["a"], cold["b"], cold["c"])

    hot_cost = side_exchanger_cost(alpha, hot["a"], hot["b"], hot["c"])
    cold_cost = side_exchanger_cost(beta, cold["a"], cold["b"], cold["c"])
    total_cost = hot_cost + cold_cost

    return {
        "hot_unit_cost": hot_unit_cost,
        "cold_unit_cost": cold_unit_cost,
        "hot_cost": hot_cost,
        "cold_cost": cold_cost,
        "total_cost": total_cost,
        "hot_label": hot["label"],
        "cold_label": cold["label"],
    }

mode = st.radio(
    "Choose NTU calculation mode",
    [
        "Known cold-flow rate → find outlet temperatures",
        "Known duty and target cold outlet → estimate cold-flow rate",
    ],
    horizontal=True
)

with st.form("ntu_cost_sweep_form"):
    st.markdown("## Thermal inputs")
    col1, col2, col3 = st.columns(3)

    with col1:
        thi = st.number_input("Hot inlet temperature, T_h,in (°C)", value=120.0)
        tci = st.number_input("Cold inlet temperature, T_c,in (°C)", value=25.0)
        u = st.number_input("Overall heat transfer coefficient, U (W/m²-K)", min_value=0.0, value=500.0, step=10.0)

    with col2:
        area = st.number_input("Initial heat transfer area, A0 (m²)", min_value=0.0, value=10.0, step=0.1)
        mh = st.number_input("Hot mass flow rate, m_dot_h (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")
        cph = st.number_input("Hot specific heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)

    with col3:
        cpc = st.number_input("Cold specific heat, c_p,c (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)
        if mode.startswith("Known cold-flow rate"):
            mc = st.number_input("Cold mass flow rate, m_dot_c (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
        else:
            q_target_kw = st.number_input("Desired heat duty, Q_target (kW)", min_value=0.001, value=120.0, step=5.0)
            tco_target = st.number_input("Target cold outlet temperature, T_c,out,target (°C)", value=45.0)

    st.markdown("## Cost inputs")
    c1, c2, c3 = st.columns(3)

    with c1:
        cost_scenario = st.selectbox("Costing scenario from paper", list(COST_DATABASE.keys()))

    with c2:
        use_same_conductance = st.checkbox("Use same conductance for hot and cold side", value=True)
        use_ntu_ua_for_alpha = st.checkbox("Use α = U×A from NTU area sweep", value=True)

    with c3:
        use_ntu_ua_for_beta = st.checkbox("Use β = U×A from NTU area sweep", value=True)
        pmax_kw = st.number_input("Optional electrical power output, P_max (kW)", min_value=0.0, value=0.0, step=10.0)

    manual_alpha = st.number_input("Manual hot-side conductance α (W/K), used only if box above is unchecked", min_value=1.0, value=5000.0, step=100.0)
    if use_same_conductance:
        manual_beta = manual_alpha
    else:
        manual_beta = st.number_input("Manual cold-side conductance β (W/K), used only if box above is unchecked", min_value=1.0, value=8000.0, step=100.0)

    submitted = st.form_submit_button("Generate 10 results and plot")

if submitted:
    try:
        if thi <= tci:
            st.error("Hot inlet temperature must be greater than cold inlet temperature.")
        elif u <= 0 or area <= 0:
            st.error("U and initial area must both be greater than zero.")
        else:
            rows = []

            for i in range(10):
                area_i = area * (1.05 ** i)

                if mode.startswith("Known cold-flow rate"):
                    thermal = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area_i)
                else:
                    thermal = solve_from_target_q_tco(
                        thi, tci, mh, cph, cpc, u, area_i, q_target_kw * 1000.0, tco_target
                    )

                alpha_i = thermal["UA"] if use_ntu_ua_for_alpha else manual_alpha
                if use_ntu_ua_for_beta:
                    beta_i = thermal["UA"]
                else:
                    beta_i = manual_beta if not use_same_conductance else alpha_i

                if use_same_conductance and not use_ntu_ua_for_beta:
                    beta_i = alpha_i

                cost = total_exchanger_cost(alpha_i, beta_i, cost_scenario)

                row = {
                    "Case": i + 1,
                    "Area (m²)": area_i,
                    "UA (W/K)": thermal["UA"],
                    "NTU": thermal["NTU"],
                    "Effectiveness": thermal["epsilon"],
                    "Q (kW)": thermal["Q"] / 1000.0,
                    "T_hot_out (°C)": thermal["T_h_out"],
                    "T_cold_out (°C)": thermal["T_c_out"],
                    "alpha (W/K)": alpha_i,
                    "beta (W/K)": beta_i,
                    "Hot cost ($)": cost["hot_cost"],
                    "Cold cost ($)": cost["cold_cost"],
                    "Total cost ($)": cost["total_cost"],
                }

                if "m_c" in thermal:
                    row["Estimated m_dot_c (kg/s)"] = thermal["m_c"]
                    row["Q error (%)"] = thermal["Q_error_pct"]

                if pmax_kw > 0:
                    row["C_hx ($/W)"] = cost["total_cost"] / (pmax_kw * 1000.0)

                rows.append(row)

            df = pd.DataFrame(rows)

            st.subheader("10 calculated results")
            st.dataframe(df, use_container_width=True)

            fig = px.line(
                df,
                x="Area (m²)",
                y="Total cost ($)",
                markers=True,
                title="Area vs Total Heat Exchanger Cost"
            )
            fig.update_layout(
                xaxis_title="Area (m²)",
                yaxis_title="Total cost ($)",
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)

            min_idx = df["Total cost ($)"].idxmin()
            min_row = df.loc[min_idx]

            st.subheader("Minimum cost result")
            m1, m2, m3 = st.columns(3)
            m1.metric("Minimum total cost ($)", f"{min_row['Total cost ($)']:,.2f}")
            m2.metric("Area at minimum cost (m²)", f"{min_row['Area (m²)']:.4f}")
            m3.metric("Case number", f"{int(min_row['Case'])}")

            st.markdown("### Minimum-cost case details")
            detail_cols = st.columns(4)
            detail_cols[0].metric("UA (W/K)", f"{min_row['UA (W/K)']:.2f}")
            detail_cols[1].metric("NTU", f"{min_row['NTU']:.4f}")
            detail_cols[2].metric("Cold outlet (°C)", f"{min_row['T_cold_out (°C)']:.2f}")
            detail_cols[3].metric("Hot outlet (°C)", f"{min_row['T_hot_out (°C)']:.2f}")

            if "Estimated m_dot_c (kg/s)" in df.columns:
                extra_cols = st.columns(2)
                extra_cols[0].metric("Estimated m_dot_c (kg/s)", f"{min_row['Estimated m_dot_c (kg/s)']:.4f}")
                extra_cols[1].metric("Q error (%)", f"{min_row['Q error (%)']:.2f}")

            st.caption(
                "This sweep uses 10 area values starting from the initial area and increasing each step by 5%."
            )

    except Exception as e:
        st.error(str(e))
