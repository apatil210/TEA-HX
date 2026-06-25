import math
import streamlit as st

st.set_page_config(page_title='NTU Heat Exchanger Calculator', page_icon='♨️', layout='wide')

st.title('NTU Heat Exchanger Calculator')
st.write('Compute cold outlet temperature, hot outlet temperature, and optional cold-side mass flow using the effectiveness-NTU method for a counter-flow heat exchanger.')

with st.expander('Equations used', expanded=False):
    st.markdown(r'''
- Heat capacity rates: \(C_h = \dot m_h c_{p,h}\), \(C_c = \dot m_c c_{p,c}\)
- Capacity ratio: \(C_r = C_{min}/C_{max}\)
- NTU: \(NTU = UA/C_{min}\)
- Counter-flow effectiveness:
  - for \(C_r \neq 1\): \(\varepsilon = \frac{1-e^{-NTU(1-C_r)}}{1-C_r e^{-NTU(1-C_r)}}\)
  - for \(C_r = 1\): \(\varepsilon = \frac{NTU}{1+NTU}\)
- Heat transfer: \(Q = \varepsilon C_{min}(T_{h,i}-T_{c,i})\)
- Outlet temperatures:
  - \(T_{h,o}=T_{h,i}-Q/C_h\)
  - \(T_{c,o}=T_{c,i}+Q/C_c\)
- If \(Q\) and target \(T_{c,o}\) are known, cold-flow rate:
  - \(\dot m_c = Q/[c_{p,c}(T_{c,o}-T_{c,i})]\)
''')

def counterflow_effectiveness(ntu: float, cr: float) -> float:
    if ntu <= 0:
        return 0.0
    if abs(cr - 1.0) < 1e-9:
        return ntu / (1.0 + ntu)
    e = math.exp(-ntu * (1.0 - cr))
    return (1.0 - e) / (1.0 - cr * e)

def solve_known_mc(thi, tci, mh, mc, cph, cpc, ua):
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
        'C_h': ch, 'C_c': cc, 'C_min': cmin, 'C_max': cmax,
        'C_r': cr, 'NTU': ntu, 'epsilon': eps, 'Q': q,
        'T_h_out': tho, 'T_c_out': tco
    }

def solve_from_target_q_tco(thi, tci, mh, cph, cpc, ua, q_target, tco_target):
    delta_tc = tco_target - tci
    if delta_tc <= 0:
        raise ValueError('Target cold outlet temperature must be greater than cold inlet temperature.')
    mc = q_target / (cpc * delta_tc)
    results = solve_known_mc(thi, tci, mh, mc, cph, cpc, ua)
    results['m_c'] = mc
    results['Q_target'] = q_target
    results['T_c_out_target'] = tco_target
    results['Q_error_pct'] = ((results['Q'] - q_target) / q_target * 100.0) if q_target != 0 else 0.0
    return results

mode = st.radio(
    'Choose calculation mode',
    ['Known cold-flow rate → find outlet temperatures', 'Known duty and target cold outlet → estimate cold-flow rate'],
    horizontal=True
)

col1, col2, col3 = st.columns(3)
with col1:
    thi = st.number_input('Hot inlet temperature, T_h,in (°C)', value=120.0)
    tci = st.number_input('Cold inlet temperature, T_c,in (°C)', value=25.0)
    ua = st.number_input('UA (W/K)', min_value=0.0, value=5000.0, step=100.0)

with col2:
    mh = st.number_input('Hot mass flow rate, m_dot_h (kg/s)', min_value=0.0001, value=1.2, step=0.1, format='%.4f')
    cph = st.number_input('Hot specific heat, c_p,h (J/kg-K)', min_value=1.0, value=2200.0, step=10.0)
    cpc = st.number_input('Cold specific heat, c_p,c (J/kg-K)', min_value=1.0, value=4180.0, step=10.0)

try:
    if thi <= tci:
        st.error('Hot inlet temperature must be greater than cold inlet temperature for heat to flow to the cold side.')
    else:
        if mode.startswith('Known cold-flow rate'):
            with col3:
                mc = st.number_input('Cold mass flow rate, m_dot_c (kg/s)', min_value=0.0001, value=1.0, step=0.1, format='%.4f')
            r = solve_known_mc(thi, tci, mh, mc, cph, cpc, ua)

            a, b, c = st.columns(3)
            a.metric('Cold outlet temperature (°C)', f"{r['T_c_out']:.2f}")
            b.metric('Hot outlet temperature (°C)', f"{r['T_h_out']:.2f}")
            c.metric('Heat transfer rate Q (kW)', f"{r['Q']/1000:.2f}")

        else:
            with col3:
                q_target_kw = st.number_input('Desired heat duty, Q_target (kW)', min_value=0.001, value=120.0, step=5.0)
                tco_target = st.number_input('Target cold outlet temperature, T_c,out,target (°C)', value=45.0)
            r = solve_from_target_q_tco(thi, tci, mh, cph, cpc, ua, q_target_kw * 1000.0, tco_target)

            a, b, c = st.columns(3)
            a.metric('Estimated cold mass flow rate (kg/s)', f"{r['m_c']:.4f}")
            b.metric('Predicted cold outlet temperature (°C)', f"{r['T_c_out']:.2f}")
            c.metric('Predicted hot outlet temperature (°C)', f"{r['T_h_out']:.2f}")
            st.info(f"Model-predicted duty = {r['Q']/1000:.2f} kW; difference from target = {r['Q_error_pct']:.2f}%")

        st.subheader('Intermediate values')
        d1, d2, d3, d4 = st.columns(4)
        d1.metric('C_h (W/K)', f"{r['C_h']:.2f}")
        d2.metric('C_c (W/K)', f"{r['C_c']:.2f}")
        d3.metric('NTU', f"{r['NTU']:.4f}")
        d4.metric('Effectiveness ε', f"{r['epsilon']:.4f}")

        st.caption('Assumptions: steady-state operation, constant specific heats, no heat loss to surroundings, counter-flow exchanger, and known UA.')

except Exception as e:
    st.error(str(e))
