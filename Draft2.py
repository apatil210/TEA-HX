import math
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="NTU Heat Exchanger Design",
    page_icon="♨️",
    layout="wide"
)

st.title("NTU Heat Exchanger Design")
st.write(
    "Calculate outlet temperatures and perform a 10-point area sweep with "
    "5% area increments using the NTU / effectiveness method."
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

### Area sweep
- \(A_n = A_0(1.05)^n\), for \(n = 0,1,\dots,9\)
""")

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

mode = st.radio(
    "Choose NTU calculation mode",
    [
        "Known cold-flow rate → find outlet temperatures",
        "Known duty and target cold outlet → estimate cold-flow rate",
    ],
    horizontal=True
)

with st.form("ntu_design_form"):
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

    submitted = st.form_submit_button("Generate 10 design results")

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

                row = {
                    "Case": i + 1,
                    "Area (m²)": area_i,
                    "UA (W/K)": thermal["UA"],
                    "C_h (W/K)": thermal["C_h"],
                    "C_c (W/K)": thermal["C_c"],
                    "C_min (W/K)": thermal["C_min"],
                    "C_max (W/K)": thermal["C_max"],
                    "C_r": thermal["C_r"],
                    "NTU": thermal["NTU"],
                    "Effectiveness": thermal["epsilon"],
                    "Q (kW)": thermal["Q"] / 1000.0,
                    "T_hot_out (°C)": thermal["T_h_out"],
                    "T_cold_out (°C)": thermal["T_c_out"],
                }

                if "m_c" in thermal:
                    row["Estimated m_dot_c (kg/s)"] = thermal["m_c"]
                    row["Q error (%)"] = thermal["Q_error_pct"]

                rows.append(row)

            df = pd.DataFrame(rows)

            st.subheader("10 calculated design results")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Design summary for final sweep point")
            final_row = df.iloc[-1]

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Final area (m²)", f"{final_row['Area (m²)']:.4f}")
            s2.metric("Final UA (W/K)", f"{final_row['UA (W/K)']:.2f}")
            s3.metric("Final NTU", f"{final_row['NTU']:.4f}")
            s4.metric("Final effectiveness", f"{final_row['Effectiveness']:.4f}")

            o1, o2 = st.columns(2)
            o1.metric("Final hot outlet (°C)", f"{final_row['T_hot_out (°C)']:.2f}")
            o2.metric("Final cold outlet (°C)", f"{final_row['T_cold_out (°C)']:.2f}")

            if "Estimated m_dot_c (kg/s)" in df.columns:
                e1, e2 = st.columns(2)
                e1.metric("Estimated m_dot_c (kg/s)", f"{final_row['Estimated m_dot_c (kg/s)']:.4f}")
                e2.metric("Q error (%)", f"{final_row['Q error (%)']:.2f}")

            st.caption(
                "This sweep uses 10 area values starting from the initial area and increasing each step by 5%."
            )

    except Exception as e:
        st.error(str(e))
