import math
import itertools
import pandas as pd
import streamlit as st
import altair as alt

# --- Berkeley Lab–inspired brand colors (dark blue, teal, grays) ---
LAB_DARK_BLUE = "#00313C"   # primary dark blue[web:3]
LAB_TEAL = "#007681"        # primary teal accent[web:3]
LAB_LIGHT_GRAY = "#B1B3B3"  # light gray[web:3]
LAB_DARK_GRAY = "#63666A"   # dark gray[web:3]

# --- Global physical / economic constants ---
ELECTRICITY_COST_PER_KWH = 0.0866
MOTOR_EFFICIENCY = 0.95
PUMP_HEAD_M = 1.0
HX_LIFE_YEARS = 10.0
WATER_DENSITY = 1000.0
G_ACCEL = 9.81

# --- Page config ---
st.set_page_config(
    page_title="Heat Exchanger Tools – Berkeley Lab Style",
    page_icon="♨️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS to bring in Berkeley Lab look-and-feel ---
CUSTOM_CSS = f"""
<style>
/* General page background and typography */
html, body, [class*="css"] {{
    font-family: "Arial", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

.main {{
    background: linear-gradient(135deg, {LAB_LIGHT_GRAY} 0%, #F5F6F7 40%, #FFFFFF 100%);
}}

.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 2.5rem;
    max-width: 1200px;
}}

h1, h2, h3, h4 {{
    color: {LAB_DARK_BLUE};
}}

/* Hero header */
.berkeley-hero {{
    padding: 1.2rem 1.5rem;
    border-radius: 0.75rem;
    background: linear-gradient(135deg, {LAB_DARK_BLUE} 0%, {LAB_TEAL} 55%, #0099A8 100%);
    color: #FFFFFF;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.16);
    margin-bottom: 1.5rem;
}}
.berkeley-hero h1 {{
    margin: 0;
    font-size: 2.0rem;
    letter-spacing: 0.02em;
}}
.berkeley-hero p {{
    margin-top: 0.4rem;
    max-width: 54rem;
    font-size: 0.98rem;
    opacity: 0.96;
}}

/* Section cards */
.berkeley-card {{
    background-color: #FFFFFF;
    border-radius: 0.75rem;
    border: 1px solid rgba(0, 0, 0, 0.04);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
    padding: 1.0rem 1.1rem;
    margin-bottom: 1.2rem;
}}

.berkeley-card-header {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.6rem;
}}
.berkeley-card-header h3 {{
    margin: 0;
    font-size: 1.10rem;
    color: {LAB_DARK_BLUE};
}}
.berkeley-card-header span.small-label {{
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {LAB_DARK_GRAY};
}}

/* Metrics strip */
.berkeley-metrics-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 0.6rem;
}}
.berkeley-metric {{
    flex: 1 1 180px;
    border-radius: 0.5rem;
    border: 1px solid rgba(0, 0, 0, 0.04);
    background-color: #F8FAFB;
    padding: 0.6rem 0.7rem;
}}
.berkeley-metric-label {{
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {LAB_DARK_GRAY};
    margin-bottom: 0.1rem;
}}
.berkeley-metric-value {{
    font-size: 1.02rem;
    font-weight: 600;
    color: {LAB_DARK_BLUE};
}}

/* Tabs styling (keep subtle) */
.stTabs [role="tablist"] button[role="tab"] {{
    padding: 0.45rem 0.9rem;
    border-radius: 999px;
}}
.stTabs [role="tablist"] button[aria-selected="true"] {{
    background-color: {LAB_DARK_BLUE};
    color: #FFFFFF;
}}
.stTabs [role="tablist"] button[aria-selected="false"] {{
    background-color: #E5EAED;
    color: #1F2933;
}}

/* Form fields labels */
.berkeley-form-help {{
    font-size: 0.82rem;
    color: {LAB_DARK_GRAY};
    margin-bottom: 0.3rem;
}}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- Streamlit Altair theme (colors matching LBNL palette) ---
alt.themes.register(
    "berkeley_lab_theme",
    lambda: {
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {
                "labelColor": LAB_DARK_GRAY,
                "titleColor": LAB_DARK_BLUE,
                "gridColor": "#E2E6EA",
            },
            "legend": {"labelColor": LAB_DARK_GRAY, "titleColor": LAB_DARK_BLUE},
            "range": {
                "category": [
                    LAB_TEAL,
                    LAB_DARK_BLUE,
                    "#7C3AED",
                    "#EA580C",
                    "#22C55E",
                    "#EAB308",
                ]
            },
        }
    },
)
alt.themes.enable("berkeley_lab_theme")


# --- Core heat-exchanger physics / economics functions (from your original logic) ---

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


def pumping_power_kw(mc, pump_eff, density=WATER_DENSITY, g=G_ACCEL):
    if mc <= 0 or pump_eff <= 0 or MOTOR_EFFICIENCY <= 0:
        return 0.0
    p_hydraulic_w = mc * g * PUMP_HEAD_M / density
    p_shaft_w = p_hydraulic_w / pump_eff
    p_elec_w = p_shaft_w / MOTOR_EFFICIENCY
    return p_elec_w / 1000.0


def pumping_cost_per_year(mc, pump_eff, hours_per_year, density=WATER_DENSITY, g=G_ACCEL, elec_cost=ELECTRICITY_COST_PER_KWH):
    p_kw = pumping_power_kw(mc, pump_eff, density=density, g=g)
    energy_kwh = p_kw * hours_per_year
    return energy_kwh * elec_cost


def annualized_hx_cost(hx_cost):
    return hx_cost / HX_LIFE_YEARS


def total_annual_cost(hx_cost, pump_cost_year):
    return annualized_hx_cost(hx_cost) + pump_cost_year


def style_temperature_cells(df_in, min_hot_outlet_temp, max_cold_outlet_temp):
    styles = pd.DataFrame("", index=df_in.index, columns=df_in.columns)
    hot_col = "Hot Outlet Temp (°C)"
    cold_col = "Cold Outlet Temp (°C)"
    styles.loc[df_in[hot_col] < min_hot_outlet_temp, hot_col] = "background-color: #ff4d4f; color: white;"
    styles.loc[df_in[cold_col] > max_cold_outlet_temp, cold_col] = "background-color: #ff4d4f; color: white;"
    return styles


# --- Helper renderers for integration tool ---

def render_source_inputs(source_num, defaults):
    st.markdown(f"#### Heat Source {source_num}")
    c1, c2 = st.columns(2)
    with c1:
        thi = st.number_input(
            f"Hot inlet temperature (°C) – Source {source_num}",
            value=defaults.get("thi", 120.0),
            key=f"src_thi_{source_num}",
        )
        mh = st.number_input(
            f"Hot mass flow (kg/s) – Source {source_num}",
            min_value=0.0001,
            value=defaults.get("mh", 2.0),
            step=0.1,
            format="%.4f",
            key=f"src_mh_{source_num}",
        )
    with c2:
        cph = st.number_input(
            f"Hot specific heat cₚ,h (J/kg·K) – Source {source_num}",
            min_value=1.0,
            value=defaults.get("cph", 4180.0),
            step=10.0,
            key=f"src_cph_{source_num}",
        )
        h_hot = st.number_input(
            f"h_hot (W/m²·K) – Source {source_num}",
            min_value=0.0001,
            value=defaults.get("h_hot", 1500.0),
            step=10.0,
            key=f"src_h_hot_{source_num}",
        )
    return {"thi": thi, "mh": mh, "cph": cph, "h_hot": h_hot}


def render_sink_inputs(sink_num, defaults):
    st.markdown(f"#### Heat Sink {sink_num}")
    c1, c2, c3 = st.columns(3)
    with c1:
        tci = st.number_input(
            f"Cold inlet temperature (°C) – Sink {sink_num}",
            value=defaults.get("tci", 25.0),
            key=f"snk_tci_{sink_num}",
        )
        mc = st.number_input(
            f"Cold mass flow (kg/s) – Sink {sink_num}",
            min_value=0.0001,
            value=defaults.get("mc", 3.0),
            step=0.1,
            format="%.4f",
            key=f"snk_mc_{sink_num}",
        )
    with c2:
        cpc = st.number_input(
            f"Cold specific heat cₚ,c (J/kg·K) – Sink {sink_num}",
            min_value=1.0,
            value=defaults.get("cpc", 4180.0),
            step=10.0,
            key=f"snk_cpc_{sink_num}",
        )
        h_cold = st.number_input(
            f"h_cold (W/m²·K) – Sink {sink_num}",
            min_value=0.0001,
            value=defaults.get("h_cold", 1000.0),
            step=10.0,
            key=f"snk_h_cold_{sink_num}",
        )
    with c3:
        pump_eff = st.number_input(
            f"Pump efficiency (0–1, head = {PUMP_HEAD_M:.1f} m) – Sink {sink_num}",
            min_value=0.01,
            max_value=1.0,
            value=defaults.get("pump_eff", 0.75),
            step=0.01,
            key=f"snk_pump_eff_{sink_num}",
        )
        st.caption(f"Motor efficiency fixed at {MOTOR_EFFICIENCY:.2f}")
    return {"tci": tci, "mc": mc, "cpc": cpc, "h_cold": h_cold, "pump_eff": pump_eff}


def render_exchanger_inputs(hx_num, defaults):
    st.markdown(f"#### Heat Exchanger {hx_num}")
    c1, c2, c3 = st.columns(3)
    with c1:
        area = st.number_input(
            f"HX area (m²) – HX {hx_num}",
            min_value=0.0001,
            value=defaults.get("area", 50.0),
            step=0.5,
            key=f"hx_area_{hx_num}",
        )
        tube_thickness = st.number_input(
            f"Tube thickness t (m) – HX {hx_num}",
            min_value=0.000001,
            value=defaults.get("tube_thickness", 0.002),
            step=0.0001,
            format="%.6f",
            key=f"hx_tube_thickness_{hx_num}",
        )
        tube_k = st.number_input(
            f"Tube thermal conductivity k (W/m·K) – HX {hx_num}",
            min_value=0.0001,
            value=defaults.get("tube_k", 16.0),
            step=0.5,
            key=f"hx_tube_k_{hx_num}",
        )
    with c2:
        exchanger_type = st.selectbox(
            f"Exchanger type – HX {hx_num}",
            ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            key=f"hx_exchanger_type_{hx_num}",
        )
        material = st.selectbox(
            f"Material – HX {hx_num}",
            [
                "Carbon steel (base)",
                "SS304",
                "SS316",
                "SS347",
                "Nickel 200",
                "Monel 400",
                "Inconel 600",
                "Incoloy 825",
                "Titanium",
                "Hastelloy",
            ],
            key=f"hx_material_{hx_num}",
        )
    with c3:
        pressure_band = st.selectbox(
            f"Pressure band – HX {hx_num}",
            [
                "Up to 700 kPag (base)",
                "700–2100 kPag",
                "2100–4200 kPag",
                "4200–6200 kPag",
            ],
            key=f"hx_pressure_band_{hx_num}",
        )
        ci_base = st.number_input(
            f"Base cost index – HX {hx_num}",
            min_value=0.0001,
            value=defaults.get("ci_base", 500.0),
            step=1.0,
            key=f"hx_ci_base_{hx_num}",
        )
        ci_calc = st.number_input(
            f"Calculation-year cost index – HX {hx_num}",
            min_value=0.0001,
            value=defaults.get("ci_calc", 750.0),
            step=1.0,
            key=f"hx_ci_calc_{hx_num}",
        )
    return {
        "area": area,
        "tube_thickness": tube_thickness,
        "tube_k": tube_k,
        "exchanger_type": exchanger_type,
        "material": material,
        "pressure_band": pressure_band,
        "ci_base": ci_base,
        "ci_calc": ci_calc,
    }


# --- Global sidebar for economic assumptions ---
with st.sidebar:
    st.markdown("### Global Operating Assumptions")
    hours_per_year = st.number_input(
        "Operating hours per year",
        min_value=1,
        max_value=8760,
        value=8000,
        step=100,
        help="Used for pumping energy and annual costs.",
    )
    elec_cost_user = st.number_input(
        "Electricity price (USD/kWh)",
        min_value=0.0,
        value=ELECTRICITY_COST_PER_KWH,
        step=0.01,
        format="%.4f",
    )
    st.markdown("---")
    st.markdown(
        "<span class='berkeley-form-help'>This tool implements standard counterflow NTU–effectiveness relations and shell-and-tube cost correlations, wrapped in a Berkeley Lab–style interface.</span>",
        unsafe_allow_html=True,
    )

# --- Hero header ---
st.markdown(
    """
<div class="berkeley-hero">
  <h1>Heat Exchanger Tools</h1>
  <p>
    Two tools in one Streamlit app: a single shell-and-tube heat-exchanger design/cost calculator
    and a compact heat-integration matching optimizer, wrapped in a visual style inspired by
    Berkeley Lab’s dark-blue/teal brand palette.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

st.caption(
    "Designed for live demonstration at conferences and safe public release — inputs are grouped, outputs are clearly labeled, and charts use an accessible, science-forward color palette.[web:3]"
)

# --- Tabs for the two tools ---
tab1, tab2 = st.tabs(
    [
        "Single Exchanger Design & Cost",
        "Heat Integration Matching Optimizer",
    ]
)


# --- Tab 1: Single exchanger tool ---

with tab1:
    st.markdown(
        "<div class='berkeley-card'>"
        "<div class='berkeley-card-header'>"
        "<h3>Design & Cost Calculator</h3>"
        "<span class='small-label'>Shell-and-tube, counterflow</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("single_exchanger_form"):
        st.markdown(
            "<div class='berkeley-form-help'>Specify hot and cold stream properties, exchanger geometry, and materials. "
            "On submit, the tool computes UA, NTU, effectiveness, outlet temperatures, heat duty, and annualized cost.</div>",
            unsafe_allow_html=True,
        )

        c_hot, c_cold = st.columns(2)

        with c_hot:
            st.subheader("Hot stream")
            thi = st.number_input(
                "Hot inlet temperature (°C)",
                value=140.0,
                step=1.0,
            )
            mh = st.number_input(
                "Hot mass flow (kg/s)",
                min_value=0.0001,
                value=2.0,
                step=0.1,
                format="%.4f",
            )
            cph = st.number_input(
                "Hot specific heat cₚ,h (J/kg·K)",
                min_value=1.0,
                value=4180.0,
                step=10.0,
            )
            h_hot = st.number_input(
                "h_hot (W/m²·K)",
                min_value=0.0001,
                value=1500.0,
                step=50.0,
            )

        with c_cold:
            st.subheader("Cold stream")
            tci = st.number_input(
                "Cold inlet temperature (°C)",
                value=30.0,
                step=1.0,
            )
            mc = st.number_input(
                "Cold mass flow (kg/s)",
                min_value=0.0001,
                value=3.0,
                step=0.1,
                format="%.4f",
            )
            cpc = st.number_input(
                "Cold specific heat cₚ,c (J/kg·K)",
                min_value=1.0,
                value=4180.0,
                step=10.0,
            )
            h_cold = st.number_input(
                "h_cold (W/m²·K)",
                min_value=0.0001,
                value=1000.0,
                step=50.0,
            )
            pump_eff = st.number_input(
                "Pump efficiency (0–1)",
                min_value=0.01,
                max_value=1.0,
                value=0.75,
                step=0.01,
            )

        st.markdown("---")

        c_geom, c_cost = st.columns(2)

        with c_geom:
            st.subheader("Geometry & thermal resistance")
            area = st.number_input(
                "Heat-transfer area (m²)",
                min_value=0.0001,
                value=50.0,
                step=0.5,
            )
            tube_thickness = st.number_input(
                "Tube thickness t (m)",
                min_value=0.000001,
                value=0.002,
                step=0.0001,
                format="%.6f",
            )
            tube_k = st.number_input(
                "Tube thermal conductivity k (W/m·K)",
                min_value=0.0001,
                value=16.0,
                step=0.5,
            )

        with c_cost:
            st.subheader("Mechanical design & cost indices")
            exchanger_type = st.selectbox(
                "Exchanger type",
                ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            )
            material = st.selectbox(
                "Material",
                [
                    "Carbon steel (base)",
                    "SS304",
                    "SS316",
                    "SS347",
                    "Nickel 200",
                    "Monel 400",
                    "Inconel 600",
                    "Incoloy 825",
                    "Titanium",
                    "Hastelloy",
                ],
            )
            pressure_band = st.selectbox(
                "Pressure band",
                [
                    "Up to 700 kPag (base)",
                    "700–2100 kPag",
                    "2100–4200 kPag",
                    "4200–6200 kPag",
                ],
            )
            ci_base = st.number_input(
                "Base cost index (reference year)",
                min_value=0.0001,
                value=500.0,
                step=1.0,
            )
            ci_calc = st.number_input(
                "Calculation-year cost index",
                min_value=0.0001,
                value=750.0,
                step=1.0,
            )

        submitted = st.form_submit_button("Run single-exchanger design", type="primary")

    st.markdown("</div>", unsafe_allow_html=True)  # close berkeley-card

    if submitted:
        try:
            # Thermal calculations
            u = calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k)
            result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, area)

            # Cost calculations
            hx_cost_data = calculate_shell_tube_cost(area, exchanger_type, pressure_band, material, ci_base, ci_calc)
            pump_cost_year = pumping_cost_per_year(mc, pump_eff, hours_per_year, elec_cost=elec_cost_user)
            annualized_hx = annualized_hx_cost(hx_cost_data["updated_cost"])
            total_cost_year = total_annual_cost(hx_cost_data["updated_cost"], pump_cost_year)

            # Metrics strip
            st.markdown(
                "<div class='berkeley-card'>"
                "<div class='berkeley-card-header'>"
                "<h3>Key results</h3>"
                "<span class='small-label'>Thermal performance & economics</span>"
                "</div>"
                "<div class='berkeley-metrics-row'>",
                unsafe_allow_html=True,
            )

            metric_items = [
                ("UA (W/K)", f"{result['UA']:.2f}"),
                ("NTU", f"{result['NTU']:.3f}"),
                ("Effectiveness", f"{result['Effectiveness']:.3f}"),
                ("Heat duty (kW)", f"{result['Q_kW']:.2f}"),
                ("Hot outlet (°C)", f"{result['T_h_out']:.2f}"),
                ("Cold outlet (°C)", f"{result['T_c_out']:.2f}"),
                ("Purchased HX cost (USD)", f"{hx_cost_data['purchased_cost']:.0f}"),
                ("Updated HX cost (USD)", f"{hx_cost_data['updated_cost']:.0f}"),
                ("Annualized HX cost (USD/yr)", f"{annualized_hx:.0f}"),
                ("Annual pump cost (USD/yr)", f"{pump_cost_year:.0f}"),
                ("Total annual cost (USD/yr)", f"{total_cost_year:.0f}"),
            ]

            for label, value in metric_items:
                st.markdown(
                    f"<div class='berkeley-metric'>"
                    f"<div class='berkeley-metric-label'>{label}</div>"
                    f"<div class='berkeley-metric-value'>{value}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("</div></div>", unsafe_allow_html=True)

            # Temperature profile chart (inlet/outlet for both streams)
            data_temp = pd.DataFrame(
                [
                    {"Stream": "Hot", "Location": "Inlet", "T": thi},
                    {"Stream": "Hot", "Location": "Outlet", "T": result["T_h_out"]},
                    {"Stream": "Cold", "Location": "Inlet", "T": tci},
                    {"Stream": "Cold", "Location": "Outlet", "T": result["T_c_out"]},
                ]
            )

            chart_temp = (
                alt.Chart(data_temp)
                .mark_line(point=True, strokeWidth=3)
                .encode(
                    x=alt.X("Location:N", title="Position"),
                    y=alt.Y("T:Q", title="Temperature (°C)"),
                    color=alt.Color("Stream:N", title="Stream"),
                )
                .properties(
                    width=600,
                    height=300,
                    title="Inlet and outlet temperatures for hot and cold streams",
                )
            )

            st.altair_chart(chart_temp, use_container_width=True)

        except Exception as e:
            st.error(f"Error in calculation: {e}")


# --- Tab 2: Heat integration matching optimizer ---

with tab2:
    st.markdown(
        "<div class='berkeley-card'>"
        "<div class='berkeley-card-header'>"
        "<h3>Heat Integration Matching</h3>"
        "<span class='small-label'>Source–sink pairing overview</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='berkeley-form-help'>Define multiple hot sources and cold sinks. "
        "The optimizer evaluates all source–sink combinations for a common exchanger design, "
        "computes heat duties and annualized costs, and presents an ordered list of attractive matches.</div>",
        unsafe_allow_html=True,
    )

    n_sources = st.slider("Number of heat sources", 1, 4, 2)
    n_sinks = st.slider("Number of heat sinks", 1, 4, 2)

    st.markdown("#### Heat sources")
    source_defaults = {
        1: {"thi": 140.0, "mh": 2.0, "cph": 4180.0, "h_hot": 1500.0},
        2: {"thi": 120.0, "mh": 1.5, "cph": 4180.0, "h_hot": 1800.0},
        3: {"thi": 110.0, "mh": 1.0, "cph": 4180.0, "h_hot": 1500.0},
        4: {"thi": 90.0, "mh": 1.0, "cph": 4180.0, "h_hot": 1300.0},
    }

    sources = []
    for i in range(1, n_sources + 1):
        sources.append(render_source_inputs(i, source_defaults.get(i, source_defaults[1])))

    st.markdown("---")

    st.markdown("#### Heat sinks")
    sink_defaults = {
        1: {"tci": 30.0, "mc": 3.0, "cpc": 4180.0, "h_cold": 1000.0, "pump_eff": 0.75},
        2: {"tci": 35.0, "mc": 2.5, "cpc": 4180.0, "h_cold": 900.0, "pump_eff": 0.75},
        3: {"tci": 40.0, "mc": 2.0, "cpc": 4180.0, "h_cold": 900.0, "pump_eff": 0.8},
        4: {"tci": 45.0, "mc": 2.0, "cpc": 4180.0, "h_cold": 850.0, "pump_eff": 0.8},
    }

    sinks = []
    for j in range(1, n_sinks + 1):
        sinks.append(render_sink_inputs(j, sink_defaults.get(j, sink_defaults[1])))

    st.markdown("---")

    st.markdown("#### Common exchanger design for integration study")
    hx_defaults = {
        "area": 60.0,
        "tube_thickness": 0.002,
        "tube_k": 16.0,
        "exchanger_type": "Floating head",
        "material": "Carbon steel (base)",
        "pressure_band": "Up to 700 kPag (base)",
        "ci_base": 500.0,
        "ci_calc": 750.0,
    }
    hx_design = render_exchanger_inputs(1, hx_defaults)

    min_hot_outlet_temp = st.number_input(
        "Minimum acceptable hot outlet temperature (°C)",
        value=80.0,
        step=1.0,
        help="Pairs that cool the hot stream below this will be flagged.",
    )
    max_cold_outlet_temp = st.number_input(
        "Maximum acceptable cold outlet temperature (°C)",
        value=80.0,
        step=1.0,
        help="Pairs that heat the cold stream beyond this will be flagged.",
    )

    run_pairs = st.button("Evaluate all source–sink pairs", type="primary")

    st.markdown("</div>", unsafe_allow_html=True)  # close berkeley-card

    if run_pairs:
        try:
            pairs = []
            for i, src in enumerate(sources, start=1):
                for j, snk in enumerate(sinks, start=1):
                    u_pair = calculate_overall_u(src["h_hot"], snk["h_cold"], hx_design["tube_thickness"], hx_design["tube_k"])
                    res = solve_known_mc(
                        src["thi"],
                        snk["tci"],
                        src["mh"],
                        snk["mc"],
                        src["cph"],
                        snk["cpc"],
                        u_pair,
                        hx_design["area"],
                    )
                    hx_cost_data = calculate_shell_tube_cost(
                        hx_design["area"],
                        hx_design["exchanger_type"],
                        hx_design["pressure_band"],
                        hx_design["material"],
                        hx_design["ci_base"],
                        hx_design["ci_calc"],
                    )
                    pump_cost_year_pair = pumping_cost_per_year(
                        snk["mc"],
                        snk["pump_eff"],
                        hours_per_year,
                        elec_cost=elec_cost_user,
                    )
                    total_cost_year_pair = total_annual_cost(hx_cost_data["updated_cost"], pump_cost_year_pair)

                    pairs.append(
                        {
                            "Source": f"Source {i}",
                            "Sink": f"Sink {j}",
                            "Q_kW": res["Q_kW"],
                            "Hot Outlet Temp (°C)": res["T_h_out"],
                            "Cold Outlet Temp (°C)": res["T_c_out"],
                            "Effectiveness": res["Effectiveness"],
                            "NTU": res["NTU"],
                            "UA (W/K)": res["UA"],
                            "HX Updated Cost (USD)": hx_cost_data["updated_cost"],
                            "Pump Cost (USD/yr)": pump_cost_year_pair,
                            "Total Annual Cost (USD/yr)": total_cost_year_pair,
                            "Cost per kW (USD/(kW·yr))": total_cost_year_pair / res["Q_kW"] if res["Q_kW"] > 0 else float("inf"),
                        }
                    )

            df_pairs = pd.DataFrame(pairs)
            df_pairs_sorted = df_pairs.sort_values("Cost per kW (USD/(kW·yr))")

            st.markdown(
                "<div class='berkeley-card'>"
                "<div class='berkeley-card-header'>"
                "<h3>Source–sink pair ranking</h3>"
                "<span class='small-label'>Ordered by cost per kW of recovered heat</span>"
                "</div>",
                unsafe_allow_html=True,
            )

            styles = style_temperature_cells(df_pairs_sorted, min_hot_outlet_temp, max_cold_outlet_temp)
            st.dataframe(df_pairs_sorted.style.apply(lambda _: styles, axis=None), use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)

            # Visualization: matrix of Q_kW with cost encoded by color
            chart_pairs = (
                alt.Chart(df_pairs_sorted)
                .mark_rect()
                .encode(
                    x=alt.X("Source:N", title="Heat source"),
                    y=alt.Y("Sink:N", title="Heat sink"),
                    color=alt.Color(
                        "Q_kW:Q",
                        title="Heat duty (kW)",
                        scale=alt.Scale(scheme="tealblues"),
                    ),
                    tooltip=[
                        "Source",
                        "Sink",
                        alt.Tooltip("Q_kW:Q", title="Heat duty (kW)", format=".2f"),
                        alt.Tooltip("Total Annual Cost (USD/yr):Q", title="Total annual cost", format=".0f"),
                        alt.Tooltip("Cost per kW (USD/(kW·yr)):Q", title="Cost per kW", format=".1f"),
                        alt.Tooltip("Hot Outlet Temp (°C):Q", format=".1f"),
                        alt.Tooltip("Cold Outlet Temp (°C):Q", format=".1f"),
                    ],
                )
                .properties(
                    width=600,
                    height=260,
                    title="Heat duty matrix for all source–sink pairs",
                )
            )

            st.altair_chart(chart_pairs, use_container_width=True)

        except Exception as e:
            st.error(f"Error while evaluating pairs: {e}")
