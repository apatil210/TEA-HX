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
    "Calculate outlet temperatures using the NTU / effectiveness method "
    "with a 10-point sweep based on heat exchanger area."
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
- Area sweep:
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

with st.form("ntu_design_form"):
    st.markdown("## Input values")
    col1, col2 = st.columns(2)

    with col1:
        thi = st.number_input("Hot Fluid Inlet Temperature (°C)", value=120.0)
        tci = st.number_input("Initial Cold Fluid Temp (avg T of return water) (°C)", value=25.0)
        mh = st.number_input("Mass Flow of Hot Fluid (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")

    with col2:
        area = st.number_input("Starting value of HX area (m²)", min_value=0.0001, value=10.0, step=0.1)
        mc = st.number_input("Starting value of Mass Flow of Cold Fluid (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
        u = st.number_input("Overall Heat Transfer Coefficient, U (W/m²-K)", min_value=0.0001, value=500.0, step=10.0)

    st.markdown("## Fluid properties")
    p1, p2 = st.columns(2)

    with p1:
        cph = st.number_input("Hot Fluid Specific Heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)

    with p2:
        cpc = st.number_input("Cold Fluid Specific Heat, c_p,c (Water) (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)

    submitted = st.form_submit_button("Generate 10 design results")

if submitted:
    try:
        if thi <= tci:
            st.error("Hot inlet temperature must be greater than cold inlet temperature.")
        elif u <= 0 or area <= 0:
            st.error("U and heat exchanger area must both be greater than zero.")
        else:
            rows = []

            for i in range(10):
                area_i = area * (1.05 ** i)
                thermal = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area_i)

                row = {
                    "Case": i + 1,
                    "HX Area (m²)": area_i,
                    "UA (W/K)": thermal["UA"],
                    "C_h (W/K)": thermal["C_h"],
                    "C_c (W/K)": thermal["C_c"],
                    "C_min (W/K)": thermal["C_min"],
                    "C_max (W/K)": thermal["C_max"],
                    "C_r": thermal["C_r"],
                    "NTU": thermal["NTU"],
                    "Effectiveness": thermal["epsilon"],
                    "Heat Duty Q (kW)": thermal["Q"] / 1000.0,
                    "Hot Outlet Temp (°C)": thermal["T_h_out"],
                    "Cold Outlet Temp (°C)": thermal["T_c_out"],
                }
                rows.append(row)

            df = pd.DataFrame(rows)

            st.subheader("10 calculated design results")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Summary for final sweep point")
            final_row = df.iloc[-1]

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Final HX Area (m²)", f"{final_row['HX Area (m²)']:.4f}")
            s2.metric("Final UA (W/K)", f"{final_row['UA (W/K)']:.2f}")
            s3.metric("Final NTU", f"{final_row['NTU']:.4f}")
            s4.metric("Final Effectiveness", f"{final_row['Effectiveness']:.4f}")

            o1, o2 = st.columns(2)
            o1.metric("Hot Outlet Temp (°C)", f"{final_row['Hot Outlet Temp (°C)']:.2f}")
            o2.metric("Cold Outlet Temp (°C)", f"{final_row['Cold Outlet Temp (°C)']:.2f}")

            st.caption(
                "This sweep uses 10 area values starting from the initial HX area and increasing each step by 5%."
            )

    except Exception as e:
        st.error(str(e))
