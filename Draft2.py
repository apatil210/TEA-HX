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
### Overall heat transfer coefficient
- \( \frac{1}{U} = \frac{1}{h_h} + \frac{t}{k} + \frac{1}{h_c} \)

Where:
- \(h_h\) = hot fluid heat transfer coefficient
- \(h_c\) = cold fluid heat transfer coefficient
- \(t\) = tube thickness
- \(k\) = tube thermal conductivity

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

with st.form("ntu_single_case_form"):
    st.markdown("## Input values")
    col1, col2 = st.columns(2)

    with col1:
        thi = st.number_input("Hot Fluid Inlet Temperature (°C)", value=120.0)
        tci = st.number_input("Initial Cold Fluid Temp (avg T of return water) (°C)", value=25.0)
        mh = st.number_input("Mass Flow of Hot Fluid (kg/s)", min_value=0.0001, value=1.2, step=0.1, format="%.4f")
        mc = st.number_input("Mass Flow of Cold Fluid (kg/s)", min_value=0.0001, value=1.0, step=0.1, format="%.4f")

    with col2:
        area = st.number_input("Value of HX area (m²)", min_value=0.0001, value=10.0, step=0.1)
        h_hot = st.number_input("HT Coeff of Hot Fluid, h_hot (W/m²-K)", min_value=0.0001, value=1000.0, step=10.0)
        h_cold = st.number_input("HT Coeff of Cold Fluid, h_cold (W/m²-K)", min_value=0.0001, value=1500.0, step=10.0)

    st.markdown("## Tube properties")
    t1, t2 = st.columns(2)

    with t1:
        tube_thickness = st.number_input("Tube Thickness, t (m)", min_value=0.000001, value=0.001, step=0.0001, format="%.6f")

    with t2:
        tube_k = st.number_input("Tube Therm Cond, k (W/m-K)", min_value=0.0001, value=15.0, step=0.5)

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
        elif area <= 0:
            st.error("Heat exchanger area must be greater than zero.")
        elif h_hot <= 0 or h_cold <= 0 or tube_thickness <= 0 or tube_k <= 0:
            st.error("Heat transfer coefficients, tube thickness, and tube thermal conductivity must be greater than zero.")
        else:
            u = calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k)
            result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area)

            st.subheader("Calculated result")

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("HX Area (m²)", f"{area:.4f}")
            r2.metric("Calculated U (W/m²-K)", f"{u:.2f}")
            r3.metric("UA (W/K)", f"{result['UA']:.2f}")
            r4.metric("NTU", f"{result['NTU']:.4f}")

            r5, r6, r7 = st.columns(3)
            r5.metric("Effectiveness", f"{result['Effectiveness']:.4f}")
            r6.metric("Heat Duty Q (kW)", f"{result['Q_kW']:.4f}")
            r7.metric("Capacity Ratio C_r", f"{result['C_r']:.4f}")

            r8, r9 = st.columns(2)
            r8.metric("Hot Outlet Temp (°C)", f"{result['T_h_out']:.2f}")
            r9.metric("Cold Outlet Temp (°C)", f"{result['T_c_out']:.2f}")

            st.markdown("## Detailed results")
            st.table({
                "Parameter": [
                    "HT Coeff of Hot Fluid (W/m²-K)",
                    "HT Coeff of Cold Fluid (W/m²-K)",
                    "Tube Thickness (m)",
                    "Tube Therm Cond (W/m-K)",
                    "Calculated U (W/m²-K)",
                    "C_h (W/K)",
                    "C_c (W/K)",
                    "C_min (W/K)",
                    "C_max (W/K)"
                ],
                "Value": [
                    f"{h_hot:.2f}",
                    f"{h_cold:.2f}",
                    f"{tube_thickness:.6f}",
                    f"{tube_k:.2f}",
                    f"{u:.2f}",
                    f"{result['C_h']:.2f}",
                    f"{result['C_c']:.2f}",
                    f"{result['C_min']:.2f}",
                    f"{result['C_max']:.2f}"
                ]
            })

    except Exception as e:
        st.error(str(e))
