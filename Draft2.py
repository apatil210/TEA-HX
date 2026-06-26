import math
import streamlit as st

st.set_page_config(
    page_title="NTU Heat Exchanger Design",
    page_icon="♨️",
    layout="wide"
)

st.title("NTU Heat Exchanger Design")
st.write("Calculate one heat exchanger case using the NTU / effectiveness method.") 

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

with st.form("ntu_single_case_form"):
    st.markdown("## Input values")
    col1, col2 = st.columns(2)

    with col1:
        thi = st.number_input("Hot Fluid Inlet Temperature (°C)", value=120.0)
        tci = st.number_input("Initial Cold Fluid Temp (avg T of return water) (°C)", value=25.0)
        mh = st.number_input("Mass Flow of Hot Fluid (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")

    with col2:
        area = st.number_input("Value of HX area (m²)", min_value=0.0001, value=10.0, step=0.1)
        mc = st.number_input("Mass Flow of Cold Fluid (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")
        u = st.number_input("Overall Heat Transfer Coefficient, U (W/m²-K)", min_value=0.0001, value=500.0, step=10.0)

    st.markdown("## Fluid properties")
    p1, p2 = st.columns(2)

    with p1:
        cph = st.number_input("Hot Fluid Specific Heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)

    with p2:
        cpc = st.number_input("Cold Fluid Specific Heat, c_p,c (Water) (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)

    submitted = st.form_submit_button("Calculate")

if submitted:
    try:
        if thi <= tci:
            st.error("Hot inlet temperature must be greater than cold inlet temperature.")
        elif u <= 0 or area <= 0:
            st.error("U and heat exchanger area must both be greater than zero.")
        else:
            result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area)

            st.subheader("Calculated result")

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("HX Area (m²)", f"{area:.4f}")
            r2.metric("UA (W/K)", f"{result['UA']:.2f}")
            r3.metric("NTU", f"{result['NTU']:.4f}")
            r4.metric("Effectiveness", f"{result['Effectiveness']:.4f}")

            r5, r6, r7 = st.columns(3)
            r5.metric("Heat Duty Q (kW)", f"{result['Q_kW']:.4f}")
            r6.metric("Hot Outlet Temp (°C)", f"{result['T_h_out']:.2f}")
            r7.metric("Cold Outlet Temp (°C)", f"{result['T_c_out']:.2f}")

            st.markdown("## Detailed results")
            st.table({
                "Parameter": [
                    "C_h (W/K)",
                    "C_c (W/K)",
                    "C_min (W/K)",
                    "C_max (W/K)",
                    "C_r",
                ],
                "Value": [
                    f"{result['C_h']:.2f}",
                    f"{result['C_c']:.2f}",
                    f"{result['C_min']:.2f}",
                    f"{result['C_max']:.2f}",
                    f"{result['C_r']:.4f}",
                ]
            })

    except Exception as e:
        st.error(str(e))
