import math
import streamlit as st

st.set_page_config(
    page_title="NTU Heat Exchanger + Cost Calculator",
    page_icon="♨️",
    layout="wide"
)

st.title("NTU Heat Exchanger + Cost Calculator")
st.write(
    "Calculate outlet temperatures, optional cold-side flow rate, and heat-exchanger cost "
    "using the effectiveness-NTU method and conductance-based cost correlations."
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

### Flow estimation mode
- If \(Q\) and target \(T_{c,o}\) are known:
  - \(\dot m_c = Q/[c_{p,c}(T_{c,o}-T_{c,i})]\)

### Cost model from the paper
- Thermal conductance on each side is represented as:
  - Hot side: \(\alpha = U_h A_h\)
  - Cold side: \(\beta = U_c A_c\)
- Cost per unit conductance is fit as:
  - \(C(\alpha) = a\alpha^b + c\)
- Side cost is then:
  - \(\text{Cost}_{hot} = \alpha \, (a_h \alpha^{b_h} + c_h)\)
  - \(\text{Cost}_{cold} = \beta \, (a_c \beta^{b_c} + c_c)\)
- Total exchanger cost:
  - \(\text{Cost}_{HX,total} = \text{Cost}_{hot} + \text{Cost}_{cold}\)
- If electrical power output is known:
  - \(C_{hx} = \text{Cost}_{HX,total} / P_{max}\)
""")

# Table 2 coefficients from the attached paper
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

st.subheader("Inputs")

mode = st.radio(
    "Choose NTU calculation mode",
    [
        "Known cold-flow rate → find outlet temperatures",
        "Known duty and target cold outlet → estimate cold-flow rate",
    ],
    horizontal=True
)

with st.form("ntu_cost_form"):
    st.markdown("### Thermal inputs")
    col1, col2, col3 = st.columns(3)

    with col1:
        thi = st.number_input("Hot inlet temperature, T_h,in (°C)", value=120.0)
        tci = st.number_input("Cold inlet temperature, T_c,in (°C)", value=25.0)
        u = st.number_input("Overall heat transfer coefficient, U (W/m²-K)", min_value=0.0, value=500.0, step=10.0)

    with col2:
        area = st.number_input("Heat transfer area, A (m²)", min_value=0.0, value=10.0, step=0.1)
        mh = st.number_input("Hot mass flow rate, m_dot_h (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")
        cph = st.number_input("Hot specific heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)

    with col3:
        cpc = st.number_input("Cold specific heat, c_p,c (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)
        if mode.startswith("Known cold-flow rate"):
            mc = st.number_input("Cold mass flow rate, m_dot_c (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
        else:
            q_target_kw = st.number_input("Desired heat duty, Q_target (kW)", min_value=0.001, value=120.0, step=5.0)
            tco_target = st.number_input("Target cold outlet temperature, T_c,out,target (°C)", value=45.0)

    st.markdown("### Cost inputs")
    cost_col1, cost_col2, cost_col3 = st.columns(3)

    with cost_col1:
        cost_scenario = st.selectbox("Costing scenario from paper", list(COST_DATABASE.keys()))
        use_same_conductance = st.checkbox("Use same conductance for hot and cold side", value=True)

    with cost_col2:
        alpha = st.number_input("Hot-side conductance, α = U_h×A_h (W/K)", min_value=1.0, value=5000.0, step=100.0)
        if use_same_conductance:
            beta = alpha
            st.number_input("Cold-side conductance, β = U_c×A_c (W/K)", min_value=1.0, value=float(beta), step=100.0, disabled=True)
        else:
            beta = st.number_input("Cold-side conductance, β = U_c×A_c (W/K)", min_value=1.0, value=8000.0, step=100.0)

    with cost_col3:
        pmax_kw = st.number_input("Optional electrical power output, P_max (kW)", min_value=0.0, value=0.0, step=10.0)
        use_ntu_ua_for_alpha = st.checkbox("Set α = current NTU UA", value=False)
        use_ntu_ua_for_beta = st.checkbox("Set β = current NTU UA", value=False)

    submitted = st.form_submit_button("Generate outputs")

if submitted:
    try:
        if thi <= tci:
            st.error("Hot inlet temperature must be greater than cold inlet temperature.")
        elif u <= 0 or area <= 0:
            st.error("U and Area must both be greater than zero.")
        else:
            # NTU section
            if mode.startswith("Known cold-flow rate"):
                r = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area)
            else:
                r = solve_from_target_q_tco(thi, tci, mh, cph, cpc, u, area, q_target_kw * 1000.0, tco_target)

            if use_ntu_ua_for_alpha:
                alpha = r["UA"]
            if use_ntu_ua_for_beta:
                beta = r["UA"]

            st.subheader("Thermal results")
            t1, t2, t3 = st.columns(3)

            if mode.startswith("Known cold-flow rate"):
                t1.metric("Cold outlet temperature (°C)", f"{r['T_c_out']:.2f}")
                t2.metric("Hot outlet temperature (°C)", f"{r['T_h_out']:.2f}")
                t3.metric("Heat transfer rate Q (kW)", f"{r['Q']/1000:.2f}")
            else:
                t1.metric("Estimated cold mass flow rate (kg/s)", f"{r['m_c']:.4f}")
                t2.metric("Predicted cold outlet temperature (°C)", f"{r['T_c_out']:.2f}")
                t3.metric("Predicted hot outlet temperature (°C)", f"{r['T_h_out']:.2f}")
                st.info(
                    f"Model-predicted duty = {r['Q']/1000:.2f} kW; "
                    f"difference from target = {r['Q_error_pct']:.2f}%"
                )

            i1, i2, i3, i4, i5, i6 = st.columns(6)
            i1.metric("UA (W/K)", f"{r['UA']:.2f}")
            i2.metric("C_h (W/K)", f"{r['C_h']:.2f}")
            i3.metric("C_c (W/K)", f"{r['C_c']:.2f}")
            i4.metric("NTU", f"{r['NTU']:.4f}")
            i5.metric("Capacity ratio, C_r", f"{r['C_r']:.4f}")
            i6.metric("Effectiveness ε", f"{r['epsilon']:.4f}")

            # Cost section
            st.subheader("Heat exchanger cost results")
            scenario = COST_DATABASE[cost_scenario]
            hot = scenario["hot"]
            cold = scenario["cold"]

            hot_unit_cost = unit_cost_from_conductance(alpha, hot["a"], hot["b"], hot["c"])
            cold_unit_cost = unit_cost_from_conductance(beta, cold["a"], cold["b"], cold["c"])

            hot_cost = side_exchanger_cost(alpha, hot["a"], hot["b"], hot["c"])
            cold_cost = side_exchanger_cost(beta, cold["a"], cold["b"], cold["c"])
            total_hx_cost = hot_cost + cold_cost

            c1, c2, c3 = st.columns(3)
            c1.metric("Hot-side exchanger cost ($)", f"{hot_cost:,.2f}")
            c2.metric("Cold-side exchanger cost ($)", f"{cold_cost:,.2f}")
            c3.metric("Total exchanger cost ($)", f"{total_hx_cost:,.2f}")

            c4, c5, c6 = st.columns(3)
            c4.metric("Hot-side unit cost ($/(W/K))", f"{hot_unit_cost:.4f}")
            c5.metric("Cold-side unit cost ($/(W/K))", f"{cold_unit_cost:.4f}")
            if pmax_kw > 0:
                chx = total_hx_cost / (pmax_kw * 1000.0)
                c6.metric("Normalized exchanger cost, C_hx ($/W)", f"{chx:.4f}")
            else:
                c6.metric("Normalized exchanger cost, C_hx ($/W)", "Enter P_max")

            st.markdown("### Cost details")
            st.write(f"Hot-side model: **{hot['label']}**")
            st.write(f"Cold-side model: **{cold['label']}**")
            st.write(
                f"Hot-side correlation coefficients: a = {hot['a']}, b = {hot['b']}, c = {hot['c']}"
            )
            st.write(
                f"Cold-side correlation coefficients: a = {cold['a']}, b = {cold['b']}, c = {cold['c']}"
            )
            st.write(
                f"Conductances used in cost model: α = {alpha:.2f} W/K, β = {beta:.2f} W/K"
            )

            st.caption(
                "Assumptions: steady-state operation, constant specific heats, no heat loss, "
                "counter-flow heat exchanger for the NTU model, and conductance-based cost correlations "
                "for the cost model from the attached paper."
            )

    except Exception as e:
        st.error(str(e))
