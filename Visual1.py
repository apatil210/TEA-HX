import math
import itertools
import pandas as pd
import streamlit as st
import altair as alt
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Heat Exchanger Tools",
    page_icon="♨️",
    layout="wide"
)

st.title("Heat Exchanger Tools")
st.caption("Two tools in one Streamlit app: single heat-exchanger design/cost and heat-integration matching optimization.")

ELECTRICITY_COST_PER_KWH = 0.0866
MOTOR_EFFICIENCY = 0.95
PUMP_HEAD_M = 1.0
HX_LIFE_YEARS = 10.0
WATER_DENSITY = 1000.0
G_ACCEL = 9.81


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


def pumping_cost_per_year(mc, pump_eff, hours_per_year, density=WATER_DENSITY, g=G_ACCEL):
    p_kw = pumping_power_kw(mc, pump_eff, density=density, g=g)
    energy_kwh = p_kw * hours_per_year
    return energy_kwh * ELECTRICITY_COST_PER_KWH


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


def adjust_cold_mass_flow_to_constraints(
    thi, tci, mh, cph, cpc, u, area,
    target_hot_outlet_temp,
    max_cold_mass_flow,
    tol=1e-3,
    max_iter=100
):
    if target_hot_outlet_temp >= thi:
        raise ValueError("Minimum hot outlet target must be less than hot inlet temperature.")
    if max_cold_mass_flow <= 0:
        raise ValueError("Maximum cold fluid flowrate must be greater than zero.")

    low_mc = 1e-6
    high_mc = max_cold_mass_flow
    low_result = solve_known_mc(thi, tci, mh, low_mc, cph, cpc, u, area)
    high_result = solve_known_mc(thi, tci, mh, high_mc, cph, cpc, u, area)

    if low_result["T_h_out"] < target_hot_outlet_temp:
        raise ValueError("Target hot outlet temperature cannot be achieved even at near-zero cold-side mass flow.")
    if high_result["T_h_out"] > target_hot_outlet_temp:
        raise ValueError("Target hot outlet temperature is not reached within the allowed maximum cold-side flowrate.")

    best_mc = low_mc
    best_result = low_result

    for _ in range(max_iter):
        mid_mc = 0.5 * (low_mc + high_mc)
        mid_result = solve_known_mc(thi, tci, mh, mid_mc, cph, cpc, u, area)
        tho_mid = mid_result["T_h_out"]
        best_mc = mid_mc
        best_result = mid_result

        if abs(tho_mid - target_hot_outlet_temp) <= tol:
            return best_mc, best_result, True

        if tho_mid > target_hot_outlet_temp:
            low_mc = mid_mc
        else:
            high_mc = mid_mc

    return best_mc, best_result, True


def render_source_inputs(source_num, defaults):
    st.markdown(f"### Heat Source {source_num}")
    c1, c2 = st.columns(2)

    with c1:
        thi = st.number_input(
            f"Hot inlet temperature (°C) - Source {source_num}",
            value=defaults["thi"],
            key=f"src_thi_{source_num}"
        )
        mh = st.number_input(
            f"Hot mass flow (kg/s) - Source {source_num}",
            min_value=0.0001,
            value=defaults["mh"],
            step=0.1,
            format="%.4f",
            key=f"src_mh_{source_num}"
        )

    with c2:
        cph = st.number_input(
            f"Hot specific heat, c_p,h (J/kg-K) - Source {source_num}",
            min_value=1.0,
            value=defaults["cph"],
            step=10.0,
            key=f"src_cph_{source_num}"
        )
        h_hot = st.number_input(
            f"h_hot (W/m²-K) - Source {source_num}",
            min_value=0.0001,
            value=defaults["h_hot"],
            step=10.0,
            key=f"src_h_hot_{source_num}"
        )

    return {"thi": thi, "mh": mh, "cph": cph, "h_hot": h_hot}


def render_sink_inputs(sink_num, defaults):
    st.markdown(f"### Heat Sink {sink_num}")
    c1, c2, c3 = st.columns(3)

    with c1:
        tci = st.number_input(
            f"Cold inlet temperature (°C) - Sink {sink_num}",
            value=defaults["tci"],
            key=f"snk_tci_{sink_num}"
        )
        mc = st.number_input(
            f"Cold mass flow (kg/s) - Sink {sink_num}",
            min_value=0.0001,
            value=defaults["mc"],
            step=0.1,
            format="%.4f",
            key=f"snk_mc_{sink_num}"
        )

    with c2:
        cpc = st.number_input(
            f"Cold specific heat, c_p,c (J/kg-K) - Sink {sink_num}",
            min_value=1.0,
            value=defaults["cpc"],
            step=10.0,
            key=f"snk_cpc_{sink_num}"
        )
        h_cold = st.number_input(
            f"h_cold (W/m²-K) - Sink {sink_num}",
            min_value=0.0001,
            value=defaults["h_cold"],
            step=10.0,
            key=f"snk_h_cold_{sink_num}"
        )

    with c3:
        pump_eff = st.number_input(
            f"Pump efficiency (0–1, head = 1 m) - Sink {sink_num}",
            min_value=0.01,
            max_value=1.0,
            value=defaults["pump_eff"],
            step=0.01,
            key=f"snk_pump_eff_{sink_num}"
        )

    st.caption(f"Head fixed at {PUMP_HEAD_M:.1f} m, motor efficiency fixed at {MOTOR_EFFICIENCY:.2f}")
    return {"tci": tci, "mc": mc, "cpc": cpc, "h_cold": h_cold, "pump_eff": pump_eff}


def render_exchanger_inputs(hx_num, defaults):
    st.markdown(f"### Heat Exchanger {hx_num}")
    c1, c2, c3 = st.columns(3)

    with c1:
        area = st.number_input(
            f"HX area (m²) - HX {hx_num}",
            min_value=0.0001,
            value=defaults["area"],
            step=0.1,
            key=f"hx_area_{hx_num}"
        )
        tube_thickness = st.number_input(
            f"Tube thickness, t (m) - HX {hx_num}",
            min_value=0.000001,
            value=defaults["tube_thickness"],
            step=0.0001,
            format="%.6f",
            key=f"hx_tube_thickness_{hx_num}"
        )
        tube_k = st.number_input(
            f"Tube thermal conductivity, k (W/m-K) - HX {hx_num}",
            min_value=0.0001,
            value=defaults["tube_k"],
            step=0.5,
            key=f"hx_tube_k_{hx_num}"
        )

    with c2:
        exchanger_type = st.selectbox(
            f"Exchanger type - HX {hx_num}",
            ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"],
            key=f"hx_exchanger_type_{hx_num}"
        )
        material = st.selectbox(
            f"Material - HX {hx_num}",
            [
                "Carbon steel (base)", "SS304", "SS316", "SS347",
                "Nickel 200", "Monel 400", "Inconel 600",
                "Incoloy 825", "Titanium", "Hastelloy"
            ],
            key=f"hx_material_{hx_num}"
        )

    with c3:
        pressure_band = st.selectbox(
            f"Pressure band - HX {hx_num}",
            ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"],
            key=f"hx_pressure_band_{hx_num}"
        )
        ci_base = st.number_input(
            f"Base cost index - HX {hx_num}",
            min_value=0.0001,
            value=defaults["ci_base"],
            step=1.0,
            key=f"hx_ci_base_{hx_num}"
        )
        ci_calc = st.number_input(
            f"Calculation-year cost index - HX {hx_num}",
            min_value=0.0001,
            value=defaults["ci_calc"],
            step=1.0,
            key=f"hx_ci_calc_{hx_num}"
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


def render_pairing_diagram(df_pairs, title):
    if df_pairs is None or df_pairs.empty:
        st.info("No valid source-sink pairs available to visualize.")
        return

    source_y = {
        "Source 1": 120,
        "Source 2": 250,
        "Source 3": 380,
        "Source 4": 510,
    }

    sink_y = {
        "Sink 1": 120,
        "Sink 2": 250,
        "Sink 3": 380,
        "Sink 4": 510,
    }

    width = 1180
    height = 660

    left_x = 120
    right_x = 1060
    card_w = 184
    card_h = 76
    lane_xs = [435, 505, 575, 645]

    bg = "#f4f7fb"
    board_bg = "#f8fbfd"
    panel = "#ffffff"
    lane_fill = "#f1f6fb"
    grid = "#e9f0f6"
    border = "#d6e0ea"
    text = "#14202b"
    muted = "#607284"
    source_accent = "#0f766e"
    sink_accent = "#2563eb"

    link_colors = [
        "#0f766e",
        "#2563eb",
        "#7c3aed",
        "#ea580c",
        "#0891b2",
        "#be185d",
    ]

    def draw_card(x, y, eyebrow, label, number, accent_color, stroke_color):
        top_y = y - card_h / 2
        left = x - card_w / 2
        return f"""
        <g>
            <rect x="{left}" y="{top_y}" width="{card_w}" height="{card_h}"
                  rx="22" fill="{panel}" stroke="{stroke_color}" stroke-width="1.4"/>
            <rect x="{left + 12}" y="{top_y + 12}" width="8" height="{card_h - 24}"
                  rx="4" fill="{accent_color}"/>
            <text x="{left + 34}" y="{top_y + 28}"
                  font-size="12" font-weight="700" letter-spacing="0.12em"
                  fill="{muted}">{eyebrow.upper()}</text>
            <text x="{left + 34}" y="{top_y + 54}"
                  font-size="22" font-weight="800" fill="{text}">{label} {number}</text>
        </g>
        """

    grid_lines = []
    for gx in range(70, width, 80):
        grid_lines.append(
            f'<line x1="{gx}" y1="70" x2="{gx}" y2="{height - 40}" stroke="{grid}" stroke-width="1"/>'
        )
    for gy in range(80, height, 80):
        grid_lines.append(
            f'<line x1="50" y1="{gy}" x2="{width - 50}" y2="{gy}" stroke="{grid}" stroke-width="1"/>'
        )

    glow_parts = []
    connector_parts = []
    badge_parts = []

    pairs = list(df_pairs.iterrows())

    for idx, (_, row) in enumerate(pairs):
        src = row.get("Source")
        snk = row.get("Sink")
        hx = row.get("Exchanger", "")

        if src not in source_y or snk not in sink_y:
            continue

        y1 = source_y[src]
        y2 = sink_y[snk]
        lane_x = lane_xs[idx % len(lane_xs)]
        color = link_colors[idx % len(link_colors)]

        x_start = left_x + card_w / 2
        x_end = right_x - card_w / 2

        path_d = (
            f"M {x_start} {y1} "
            f"C {x_start + 72} {y1}, {lane_x - 44} {y1}, {lane_x} {y1} "
            f"L {lane_x} {y2} "
            f"C {lane_x + 44} {y2}, {x_end - 72} {y2}, {x_end} {y2}"
        )

        mid_y = (y1 + y2) / 2
        badge_y = mid_y - 18 if abs(y1 - y2) > 24 else mid_y - 28

        glow_parts.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-opacity="0.12" '
            f'stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>'
        )

        connector_parts.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="4.5" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )

        if hx:
            badge_parts.append(
                f"""
                <g>
                    <rect x="{lane_x - 38}" y="{badge_y - 12}" width="76" height="28"
                          rx="14" fill="{panel}" stroke="{border}" stroke-width="1.2"/>
                    <text x="{lane_x}" y="{badge_y + 6}" text-anchor="middle"
                          font-size="13" font-weight="800" fill="{text}">{hx}</text>
                </g>
                """
            )

    source_cards = []
    sink_cards = []

    for i in range(1, 5):
        source_cards.append(
            draw_card(
                left_x,
                source_y[f"Source {i}"],
                "Heat",
                "Source",
                str(i),
                source_accent,
                "#b9d8d3",
            )
        )
        sink_cards.append(
            draw_card(
                right_x,
                sink_y[f"Sink {i}"],
                "Heat",
                "Sink",
                str(i),
                sink_accent,
                "#c9d8fb",
            )
        )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            html, body {{
                margin: 0;
                padding: 0;
                background: {bg};
                font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }}

            * {{
                box-sizing: border-box;
            }}

            .frame {{
                width: 100%;
                padding: 14px;
                background: {bg};
            }}

            .board {{
                width: 100%;
                max-width: 1160px;
                margin: 0 auto;
                background: linear-gradient(180deg, #fbfdff 0%, {board_bg} 100%);
                border: 1px solid {border};
                border-radius: 28px;
                overflow: hidden;
                box-shadow:
                    0 1px 2px rgba(16, 24, 40, 0.03),
                    0 16px 40px rgba(16, 24, 40, 0.08);
            }}

            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                padding: 18px 24px 16px 24px;
                border-bottom: 1px solid #e7eef5;
                background: rgba(255, 255, 255, 0.80);
                backdrop-filter: blur(6px);
            }}

            .title-wrap {{
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}

            .eyebrow {{
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                color: {muted};
            }}

            .title {{
                font-size: 22px;
                line-height: 1.1;
                font-weight: 800;
                color: {text};
            }}

            .legend {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: flex-end;
            }}

            .pill {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                border-radius: 999px;
                background: {panel};
                border: 1px solid #e4ebf3;
                color: {muted};
                font-size: 12px;
                font-weight: 700;
            }}

            .dot {{
                width: 10px;
                height: 10px;
                border-radius: 999px;
                flex: 0 0 10px;
            }}

            svg {{
                display: block;
                width: 100%;
                height: auto;
            }}

            .section-label {{
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                fill: {muted};
            }}

            .lane-label {{
                font-size: 13px;
                font-weight: 700;
                fill: #6c7d8d;
            }}

            @media (max-width: 900px) {{
                .header {{
                    flex-direction: column;
                    align-items: flex-start;
                }}

                .legend {{
                    justify-content: flex-start;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="frame">
            <div class="board">
                <div class="header">
                    <div class="title-wrap">
                        <div class="eyebrow">Network overview</div>
                        <div class="title">{title}</div>
                    </div>

                    <div class="legend">
                        <div class="pill">
                            <span class="dot" style="background:{source_accent};"></span>
                            Heat sources
                        </div>
                        <div class="pill">
                            <span class="dot" style="background:{sink_accent};"></span>
                            Heat sinks
                        </div>
                        <div class="pill">
                            <span class="dot" style="background:#7c3aed;"></span>
                            Exchange paths
                        </div>
                    </div>
                </div>

                <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
                    <rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>

                    {''.join(grid_lines)}

                    <text x="72" y="45" class="section-label">Sources</text>
                    <text x="{width / 2 - 68}" y="45" class="section-label">Heat exchange paths</text>
                    <text x="{width - 122}" y="45" class="section-label">Sinks</text>

                    <rect x="{width / 2 - 95}" y="70" width="190" height="{height - 130}"
                          rx="28" fill="{lane_fill}" stroke="#e3ebf3" stroke-width="1.2"/>

                    <text x="{width / 2}" y="98" text-anchor="middle" class="lane-label">Exchanger routing zone</text>

                    {''.join(glow_parts)}
                    {''.join(connector_parts)}
                    {''.join(badge_parts)}
                    {''.join(source_cards)}
                    {''.join(sink_cards)}
                </svg>
            </div>
        </div>
    </body>
    </html>
    """

    components.html(html, height=780, scrolling=False)


def reset_invalid_choice(widget_key, valid_options):
    if widget_key in st.session_state and st.session_state[widget_key] not in valid_options:
        del st.session_state[widget_key]


tab1, tab2 = st.tabs(["Single HX Design + Cost", "Heat Integration Matching"])

with tab1:
    st.header("Heat Exchanger Design + Cost")

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
            tube_thickness = st.number_input("Tube Thickness, t (m)", min_value=0.000001, value=0.001, step=0.0001, format="%.6f")
        with t2:
            tube_k = st.number_input("Tube Therm Cond, k (W/m-K)", min_value=0.0001, value=15.0, step=0.5)

        st.markdown("## Fluid properties")
        p1, p2 = st.columns(2)

        with p1:
            cph = st.number_input("Hot Fluid Specific Heat, c_p,h (J/kg-K)", min_value=1.0, value=2200.0, step=10.0)
        with p2:
            cpc = st.number_input("Cold Fluid Specific Heat, c_p,c (Water) (J/kg-K)", min_value=1.0, value=4180.0, step=10.0)

        st.markdown("## Cold-side pumping inputs")
        pp1, pp2 = st.columns(2)

        with pp1:
            cold_pump_eff = st.number_input("Cold-side pump efficiency (0–1, head = 1 m)", min_value=0.01, max_value=1.0, value=0.70, step=0.01)
        with pp2:
            hours_per_year = st.number_input("Operating hours per year (h/yr)", min_value=0.0, value=8000.0, step=100.0)

        st.caption(
            f"Electricity cost fixed at ${ELECTRICITY_COST_PER_KWH:.4f}/kWh, "
            f"motor efficiency fixed at {MOTOR_EFFICIENCY:.2f}, "
            f"pump head fixed at {PUMP_HEAD_M:.1f} m, "
            f"HX life fixed at {int(HX_LIFE_YEARS)} years."
        )

        st.markdown("## Shell-and-tube cost inputs")
        c1, c2, c3 = st.columns(3)

        with c1:
            exchanger_type = st.selectbox("Exchanger type", ["Floating head", "Fixed head", "U-tube", "Kettle reboiler"])
            material = st.selectbox(
                "Material of construction",
                ["Carbon steel (base)", "SS304", "SS316", "SS347", "Nickel 200", "Monel 400", "Inconel 600", "Incoloy 825", "Titanium", "Hastelloy"]
            )

        with c2:
            pressure_band = st.selectbox("Design pressure band", ["Up to 700 kPag (base)", "700–2100 kPag", "2100–4200 kPag", "4200–6200 kPag"])
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
                elif cold_pump_eff <= 0:
                    st.error("Pump efficiency must be greater than zero.")
                else:
                    u = calculate_overall_u(h_hot, h_cold, tube_thickness, tube_k)
                    rows = []

                    for i in range(10):
                        iter_area = area * (1.2 ** i)
                        result = solve_known_mc(thi, tci, mh, mc, cph, cpc, u, iter_area)
                        cost = calculate_shell_tube_cost(iter_area, exchanger_type, pressure_band, material, ci_base, ci_calc)
                        hx_capital = cost["updated_cost"]
                        pump_cost_year = pumping_cost_per_year(mc=mc, pump_eff=cold_pump_eff, hours_per_year=hours_per_year)
                        hx_annual = annualized_hx_cost(hx_capital)
                        tac = total_annual_cost(hx_capital, pump_cost_year)

                        rows.append({
                            "Iteration": i + 1,
                            "Area_m2": iter_area,
                            "T_h_in_C": thi,
                            "T_h_out_C": result["T_h_out"],
                            "T_c_in_C": tci,
                            "T_c_out_C": result["T_c_out"],
                            "U_W_m2K": u,
                            "UA_W_K": result["UA"],
                            "NTU": result["NTU"],
                            "Effectiveness": result["Effectiveness"],
                            "Q_kW": result["Q_kW"],
                            "HX_Cost_USD": hx_capital,
                            "Pump_Cost_USD_per_year": pump_cost_year,
                            "HX_Annualized_Cost_USD_per_year": hx_annual,
                            "Total_Annual_Cost_USD_per_year": tac,
                        })

                    df = pd.DataFrame(rows)

                    st.subheader("Iteration table")
                    df_display = df[[
                        "Area_m2", "T_h_in_C", "T_h_out_C", "T_c_in_C", "T_c_out_C", "Q_kW",
                        "HX_Cost_USD", "Pump_Cost_USD_per_year", "HX_Annualized_Cost_USD_per_year", "Total_Annual_Cost_USD_per_year"
                    ]].rename(columns={
                        "Area_m2": "Area (m²)",
                        "T_h_in_C": "Hot Inlet Temp (°C)",
                        "T_h_out_C": "Hot Outlet Temp (°C)",
                        "T_c_in_C": "Cold Inlet Temp (°C)",
                        "T_c_out_C": "Cold Outlet Temp (°C)",
                        "Q_kW": "Heat Duty (kW)",
                        "HX_Cost_USD": "HX Capital Cost ($)",
                        "Pump_Cost_USD_per_year": "Pump Operating Cost ($/yr)",
                        "HX_Annualized_Cost_USD_per_year": "HX Annualized Cost ($/yr)",
                        "Total_Annual_Cost_USD_per_year": "Total Annual Cost ($/yr)",
                    })

                    styled_df = (
                        df_display.style
                        .apply(style_temperature_cells, axis=None, min_hot_outlet_temp=min_hot_outlet_temp, max_cold_outlet_temp=max_cold_outlet_temp)
                        .format({
                            "Area (m²)": "{:.4f}",
                            "Hot Inlet Temp (°C)": "{:.2f}",
                            "Hot Outlet Temp (°C)": "{:.2f}",
                            "Cold Inlet Temp (°C)": "{:.2f}",
                            "Cold Outlet Temp (°C)": "{:.2f}",
                            "Heat Duty (kW)": "{:.4f}",
                            "HX Capital Cost ($)": "${:,.2f}",
                            "Pump Operating Cost ($/yr)": "${:,.2f}",
                            "HX Annualized Cost ($/yr)": "${:,.2f}",
                            "Total Annual Cost ($/yr)": "${:,.2f}",
                        })
                    )
                    st.dataframe(styled_df, use_container_width=True)

                    st.subheader("Minimum Cost Heat Exchanger Configuration")
                    valid_mask = (df["T_h_out_C"] >= min_hot_outlet_temp) & (df["T_c_out_C"] <= max_cold_outlet_temp)
                    valid_rows = df[valid_mask]

                    if not valid_rows.empty:
                        best_row = valid_rows.loc[valid_rows["Total_Annual_Cost_USD_per_year"].idxmin()]
                        result_data = pd.DataFrame({
                            "Parameter": [
                                "Hot fluid inlet temperature (°C)",
                                "Hot fluid outlet temperature (°C)",
                                "Cold fluid inlet temperature (°C)",
                                "Cold fluid outlet temperature (°C)",
                                "Heat Exchanger (HX) duty (kW)",
                                "Heat Exchanger capital cost ($)",
                                "Pump operating cost ($/yr)",
                                "HX annualized cost ($/yr)",
                                "Total annual cost of heat integration ($/yr)"
                            ],
                            "Value": [
                                f"{best_row['T_h_in_C']:.2f}",
                                f"{best_row['T_h_out_C']:.2f}",
                                f"{best_row['T_c_in_C']:.2f}",
                                f"{best_row['T_c_out_C']:.2f}",
                                f"{best_row['Q_kW']:.4f}",
                                f"${best_row['HX_Cost_USD']:,.2f}",
                                f"${best_row['Pump_Cost_USD_per_year']:,.2f}",
                                f"${best_row['HX_Annualized_Cost_USD_per_year']:,.2f}",
                                f"${best_row['Total_Annual_Cost_USD_per_year']:,.2f}"
                            ]
                        })
                        st.table(result_data)
                    else:
                        st.info("No feasible configuration satisfies the outlet-temperature constraints.")

                    st.subheader("Heat Exchanger Capital Cost vs Heat Duty")
                    base = alt.Chart(df).encode(
                        x=alt.X("Q_kW:Q", title="Heat Duty (kW)"),
                        y=alt.Y("HX_Cost_USD:Q", title="HX Capital Cost ($)")
                    )
                    st.altair_chart((base.mark_line() + base.mark_point(filled=True, size=80)).interactive(), use_container_width=True)

                    st.subheader("Total Annual Cost vs Heat Duty")
                    base_tac = alt.Chart(df).encode(
                        x=alt.X("Q_kW:Q", title="Heat Duty (kW)"),
                        y=alt.Y("Total_Annual_Cost_USD_per_year:Q", title="Total Annual Cost ($/yr)")
                    )
                    st.altair_chart((base_tac.mark_line(color="#2E86AB") + base_tac.mark_point(filled=True, size=80, color="#2E86AB")).interactive(), use_container_width=True)

            except Exception as e:
                st.error(str(e))

with tab2:
    st.header("Heat Integration Cost Optimization")
    st.caption("Enter 4 heat sources, 4 heat sinks, and 4 heat exchangers, then assign each source to one unique sink and one unique exchanger.")

    st.markdown("## Global operating assumptions")
    go1, go2, go3, go4 = st.columns(4)

    with go1:
        hours_per_year_global = st.number_input("Operating hours per year (h/yr)", min_value=0.0, value=8000.0, step=100.0, key="global_hours_per_year")
    with go2:
        min_hot_outlet_temp_global = st.number_input("Minimum hot outlet temperature target (°C)", value=60.0, step=1.0, key="global_min_hot_outlet_temp")
    with go3:
        max_cold_mass_flow_global = st.number_input("Maximum cold fluid flowrate (kg/s)", min_value=0.0001, value=5.0, step=0.1, format="%.4f", key="global_max_cold_mass_flow")
    with go4:
        st.caption(
            f"Electricity cost fixed at ${ELECTRICITY_COST_PER_KWH:.4f}/kWh, "
            f"motor efficiency fixed at {MOTOR_EFFICIENCY:.2f}, "
            f"pump head fixed at {PUMP_HEAD_M:.1f} m, "
            f"HX life fixed at {int(HX_LIFE_YEARS)} years."
        )

    source_defaults = {"thi": 120.0, "mh": 1.2, "cph": 2200.0, "h_hot": 1000.0}
    sink_defaults = {"tci": 25.0, "mc": 1.0, "cpc": 4180.0, "h_cold": 1500.0, "pump_eff": 0.70}
    hx_defaults = {"area": 20.0, "tube_thickness": 0.001, "tube_k": 15.0, "ci_base": 500.0, "ci_calc": 800.0}

    if "matched_results_df" not in st.session_state:
        st.session_state.matched_results_df = None
    if "matched_total_capital" not in st.session_state:
        st.session_state.matched_total_capital = None
    if "matched_total_heat_duty" not in st.session_state:
        st.session_state.matched_total_heat_duty = None
    if "matched_total_pump_cost" not in st.session_state:
        st.session_state.matched_total_pump_cost = None
    if "matched_total_annual_cost" not in st.session_state:
        st.session_state.matched_total_annual_cost = None

    if "optimized_results_df" not in st.session_state:
        st.session_state.optimized_results_df = None
    if "optimized_total_capital" not in st.session_state:
        st.session_state.optimized_total_capital = None
    if "optimized_total_pump_cost" not in st.session_state:
        st.session_state.optimized_total_pump_cost = None
    if "optimized_total_annual_cost" not in st.session_state:
        st.session_state.optimized_total_annual_cost = None
    if "optimized_total_q" not in st.session_state:
        st.session_state.optimized_total_q = None
    if "optimized_feasible_count" not in st.session_state:
        st.session_state.optimized_feasible_count = None

    st.markdown("## Inputs for Heat sources")
    source_tabs = st.tabs([f"Source {i}" for i in range(1, 5)])
    sources = []
    for i, tab in enumerate(source_tabs, start=1):
        with tab:
            sources.append(render_source_inputs(i, source_defaults))

    st.markdown("## Inputs for Heat sinks")
    sink_tabs = st.tabs([f"Sink {i}" for i in range(1, 5)])
    sinks = []
    for i, tab in enumerate(sink_tabs, start=1):
        with tab:
            sinks.append(render_sink_inputs(i, sink_defaults))

    st.markdown("## Inputs for Heat exchangers")
    hx_tabs = st.tabs([f"HX {i}" for i in range(1, 5)])
    exchangers = []
    for i, tab in enumerate(hx_tabs, start=1):
        with tab:
            exchangers.append(render_exchanger_inputs(i, hx_defaults))

    st.markdown("## Assign sinks and exchangers to each source")
    sink_labels = [f"Sink {i}" for i in range(1, 5)]
    hx_labels = [f"HX {i}" for i in range(1, 5)]
    selected_sinks = []
    selected_hx = []

    for i in range(1, 5):
        st.markdown(f"### Matching for Source {i}")
        c1, c2 = st.columns(2)

        remaining_sinks = [s for s in sink_labels if s not in selected_sinks]
        remaining_hx = [h for h in hx_labels if h not in selected_hx]

        sink_key = f"match_sink_{i}"
        hx_key = f"match_hx_{i}"

        reset_invalid_choice(sink_key, remaining_sinks)
        reset_invalid_choice(hx_key, remaining_hx)

        with c1:
            sink_choice = st.selectbox(f"Choose sink for Source {i}", options=remaining_sinks, key=sink_key)
            selected_sinks.append(sink_choice)

        remaining_hx = [h for h in hx_labels if h not in selected_hx]
        reset_invalid_choice(hx_key, remaining_hx)

        with c2:
            hx_choice = st.selectbox(f"Choose exchanger for Source {i}", options=remaining_hx, key=hx_key)
            selected_hx.append(hx_choice)

    calculate = st.button("Click to calculate results for selected pairs")

    if calculate:
        results_rows = []
        sink_index_map = {f"Sink {i}": i - 1 for i in range(1, 5)}
        hx_index_map = {f"HX {i}": i - 1 for i in range(1, 5)}

        if len(set(selected_sinks)) != 4:
            st.error("Each source must be assigned to a unique sink.")
        elif len(set(selected_hx)) != 4:
            st.error("Each source must be assigned to a unique heat exchanger.")
        else:
            for i in range(1, 5):
                source = sources[i - 1]
                sink = sinks[sink_index_map[selected_sinks[i - 1]]]
                hx = exchangers[hx_index_map[selected_hx[i - 1]]]

                try:
                    if source["thi"] <= sink["tci"]:
                        st.error(f"Source {i}: hot inlet temperature must be greater than the selected sink cold inlet temperature.")
                        continue

                    if hx["area"] <= 0:
                        st.error(f"Source {i}: exchanger area must be greater than zero.")
                        continue

                    if (
                        source["h_hot"] <= 0
                        or sink["h_cold"] <= 0
                        or hx["tube_thickness"] <= 0
                        or hx["tube_k"] <= 0
                        or sink["pump_eff"] <= 0
                    ):
                        st.error(f"Source {i}: invalid heat-transfer, tube-property, or pump input.")
                        continue

                    u = calculate_overall_u(source["h_hot"], sink["h_cold"], hx["tube_thickness"], hx["tube_k"])
                    result = solve_known_mc(
                        source["thi"], sink["tci"],
                        source["mh"], sink["mc"],
                        source["cph"], sink["cpc"],
                        u, hx["area"]
                    )
                    cost = calculate_shell_tube_cost(
                        hx["area"],
                        hx["exchanger_type"],
                        hx["pressure_band"],
                        hx["material"],
                        hx["ci_base"],
                        hx["ci_calc"]
                    )

                    hx_capital = cost["updated_cost"]
                    pump_cost_year = pumping_cost_per_year(mc=sink["mc"], pump_eff=sink["pump_eff"], hours_per_year=hours_per_year_global)
                    hx_annual = annualized_hx_cost(hx_capital)
                    tac = total_annual_cost(hx_capital, pump_cost_year)

                    results_rows.append({
                        "Source": f"Source {i}",
                        "Sink": selected_sinks[i - 1],
                        "Exchanger": selected_hx[i - 1],
                        "Hot outlet temp (°C)": f"{result['T_h_out']:.2f}",
                        "Cold outlet temp (°C)": f"{result['T_c_out']:.2f}",
                        "Heat duty (kW)": f"{result['Q_kW']:.4f}",
                        "Overall U (W/m²-K)": f"{u:.2f}",
                        "NTU": f"{result['NTU']:.4f}",
                        "Effectiveness": f"{result['Effectiveness']:.4f}",
                        "HX Capital Cost ($)": f"${hx_capital:,.2f}",
                        "Pump Operating Cost ($/yr)": f"${pump_cost_year:,.2f}",
                        "HX Annualized Cost ($/yr)": f"${hx_annual:,.2f}",
                        "Total Annual Cost ($/yr)": f"${tac:,.2f}",
                        "HX capital numeric": hx_capital,
                        "Heat duty numeric": result["Q_kW"],
                        "Pump cost numeric": pump_cost_year,
                        "HX annual numeric": hx_annual,
                        "Total annual numeric": tac,
                    })

                except Exception as e:
                    st.error(f"Source {i}: {str(e)}")

            if results_rows:
                results_df = pd.DataFrame(results_rows)
                st.session_state.matched_total_capital = results_df["HX capital numeric"].sum()
                st.session_state.matched_total_heat_duty = results_df["Heat duty numeric"].sum()
                st.session_state.matched_total_pump_cost = results_df["Pump cost numeric"].sum()
                st.session_state.matched_total_annual_cost = results_df["Total annual numeric"].sum()
                st.session_state.matched_results_df = results_df.drop(
                    columns=["HX capital numeric", "Heat duty numeric", "Pump cost numeric", "HX annual numeric", "Total annual numeric"]
                )

    optimize = st.button("Click to optimize pairs for maximum heat integration", type="secondary")

    st.markdown("## Results")

    if optimize:
        best_solution = None
        best_total_capital = None
        best_total_pump_cost = None
        best_total_annual_cost = None
        best_total_q = None
        best_sink_perm = None
        best_hx_perm = None
        feasible_count = 0

        sink_permutations = list(itertools.permutations(range(4)))
        hx_permutations = list(itertools.permutations(range(4)))

        for sink_perm in sink_permutations:
            for hx_perm in hx_permutations:
                current_total_capital = 0.0
                current_total_pump_cost = 0.0
                current_total_annual_cost = 0.0
                current_total_q = 0.0
                feasible = True

                for i in range(4):
                    source = sources[i]
                    sink = sinks[sink_perm[i]]
                    hx = exchangers[hx_perm[i]]

                    try:
                        if source["thi"] <= sink["tci"]:
                            feasible = False
                            break
                        if hx["area"] <= 0:
                            feasible = False
                            break
                        if (
                            source["h_hot"] <= 0
                            or sink["h_cold"] <= 0
                            or hx["tube_thickness"] <= 0
                            or hx["tube_k"] <= 0
                            or sink["pump_eff"] <= 0
                        ):
                            feasible = False
                            break

                        u = calculate_overall_u(source["h_hot"], sink["h_cold"], hx["tube_thickness"], hx["tube_k"])
                        result = solve_known_mc(
                            source["thi"], sink["tci"],
                            source["mh"], sink["mc"],
                            source["cph"], sink["cpc"],
                            u, hx["area"]
                        )
                        cost = calculate_shell_tube_cost(
                            hx["area"],
                            hx["exchanger_type"],
                            hx["pressure_band"],
                            hx["material"],
                            hx["ci_base"],
                            hx["ci_calc"]
                        )

                        hx_capital = cost["updated_cost"]
                        pump_cost_year = pumping_cost_per_year(mc=sink["mc"], pump_eff=sink["pump_eff"], hours_per_year=hours_per_year_global)
                        tac = total_annual_cost(hx_capital, pump_cost_year)

                        current_total_capital += hx_capital
                        current_total_pump_cost += pump_cost_year
                        current_total_annual_cost += tac
                        current_total_q += result["Q_kW"]

                    except Exception:
                        feasible = False
                        break

                if feasible:
                    feasible_count += 1

                    if (
                        best_solution is None
                        or current_total_q > best_total_q
                        or (
                            abs(current_total_q - best_total_q) < 1e-9
                            and current_total_annual_cost < best_total_annual_cost
                        )
                    ):
                        best_solution = True
                        best_total_capital = current_total_capital
                        best_total_pump_cost = current_total_pump_cost
                        best_total_annual_cost = current_total_annual_cost
                        best_total_q = current_total_q
                        best_sink_perm = sink_perm
                        best_hx_perm = hx_perm

        if best_solution is not None:
            adjusted_rows = []
            adjusted_total_capital = 0.0
            adjusted_total_pump_cost = 0.0
            adjusted_total_annual_cost = 0.0
            adjusted_total_q = 0.0
            adjustment_possible_for_all = True

            for i in range(4):
                source = sources[i]
                sink = sinks[best_sink_perm[i]]
                hx = exchangers[best_hx_perm[i]]

                try:
                    u = calculate_overall_u(source["h_hot"], sink["h_cold"], hx["tube_thickness"], hx["tube_k"])

                    adjusted_mc, adjusted_result, converged = adjust_cold_mass_flow_to_constraints(
                        thi=source["thi"],
                        tci=sink["tci"],
                        mh=source["mh"],
                        cph=source["cph"],
                        cpc=sink["cpc"],
                        u=u,
                        area=hx["area"],
                        target_hot_outlet_temp=min_hot_outlet_temp_global,
                        max_cold_mass_flow=max_cold_mass_flow_global
                    )

                    cost = calculate_shell_tube_cost(
                        hx["area"],
                        hx["exchanger_type"],
                        hx["pressure_band"],
                        hx["material"],
                        hx["ci_base"],
                        hx["ci_calc"]
                    )

                    hx_capital = cost["updated_cost"]
                    pump_cost_year = pumping_cost_per_year(mc=adjusted_mc, pump_eff=sink["pump_eff"], hours_per_year=hours_per_year_global)
                    hx_annual = annualized_hx_cost(hx_capital)
                    tac = total_annual_cost(hx_capital, pump_cost_year)

                    adjusted_total_capital += hx_capital
                    adjusted_total_pump_cost += pump_cost_year
                    adjusted_total_annual_cost += tac
                    adjusted_total_q += adjusted_result["Q_kW"]

                    adjusted_rows.append({
                        "Source": f"Source {i + 1}",
                        "Sink": f"Sink {best_sink_perm[i] + 1}",
                        "Exchanger": f"HX {best_hx_perm[i] + 1}",
                        "Adjusted cold mass flow (kg/s)": f"{adjusted_mc:.4f}",
                        "Maximum allowed cold mass flow (kg/s)": f"{max_cold_mass_flow_global:.4f}",
                        "Hot outlet temp (°C)": f"{adjusted_result['T_h_out']:.2f}",
                        "Cold outlet temp (°C)": f"{adjusted_result['T_c_out']:.2f}",
                        "Heat duty (kW)": f"{adjusted_result['Q_kW']:.4f}",
                        "Overall U (W/m²-K)": f"{u:.2f}",
                        "NTU": f"{adjusted_result['NTU']:.4f}",
                        "Effectiveness": f"{adjusted_result['Effectiveness']:.4f}",
                        "HX Capital Cost ($)": f"${hx_capital:,.2f}",
                        "Pump Operating Cost ($/yr)": f"${pump_cost_year:,.2f}",
                        "HX Annualized Cost ($/yr)": f"${hx_annual:,.2f}",
                        "Total Annual Cost ($/yr)": f"${tac:,.2f}",
                        "Constraint status": "Satisfied" if converged else "Approximate"
                    })

                except Exception as e:
                    adjustment_possible_for_all = False
                    adjusted_rows.append({
                        "Source": f"Source {i + 1}",
                        "Sink": f"Sink {best_sink_perm[i] + 1}",
                        "Exchanger": f"HX {best_hx_perm[i] + 1}",
                        "Adjusted cold mass flow (kg/s)": "N/A",
                        "Maximum allowed cold mass flow (kg/s)": f"{max_cold_mass_flow_global:.4f}",
                        "Hot outlet temp (°C)": "N/A",
                        "Cold outlet temp (°C)": "N/A",
                        "Heat duty (kW)": "N/A",
                        "Overall U (W/m²-K)": "N/A",
                        "NTU": "N/A",
                        "Effectiveness": "N/A",
                        "HX Capital Cost ($)": "N/A",
                        "Pump Operating Cost ($/yr)": "N/A",
                        "HX Annualized Cost ($/yr)": "N/A",
                        "Total Annual Cost ($/yr)": "N/A",
                        "Constraint status": f"Not satisfied: {str(e)}"
                    })

            st.session_state.optimized_results_df = pd.DataFrame(adjusted_rows)
            st.session_state.optimized_total_capital = adjusted_total_capital
            st.session_state.optimized_total_pump_cost = adjusted_total_pump_cost
            st.session_state.optimized_total_annual_cost = adjusted_total_annual_cost
            st.session_state.optimized_total_q = adjusted_total_q
            st.session_state.optimized_feasible_count = feasible_count

            if not adjustment_possible_for_all:
                st.warning("Some optimized pairs could not satisfy both the minimum hot outlet temperature and maximum cold fluid flowrate constraints.")
        else:
            st.session_state.optimized_results_df = None
            st.session_state.optimized_total_capital = None
            st.session_state.optimized_total_pump_cost = None
            st.session_state.optimized_total_annual_cost = None
            st.session_state.optimized_total_q = None
            st.session_state.optimized_feasible_count = 0

    if st.session_state.matched_results_df is not None:
        st.subheader("Matched results")
        st.dataframe(st.session_state.matched_results_df, use_container_width=True)
        render_pairing_diagram(st.session_state.matched_results_df, "Selected source-to-sink matches")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total HX capital for selected pairs", f"${st.session_state.matched_total_capital:,.2f}")
        with c2:
            st.metric("Annual pump operating cost (cold fluid)", f"${st.session_state.matched_total_pump_cost:,.2f}/yr")
        with c3:
            st.metric("Total annual cost of heat Integration", f"${st.session_state.matched_total_annual_cost:,.2f}/yr")
        with c4:
            st.metric("Total heat integration", f"{st.session_state.matched_total_heat_duty:.4f} kW")

    if st.session_state.optimized_results_df is not None:
        st.subheader("Optimal matched results for maximum heat integration")
        st.dataframe(st.session_state.optimized_results_df, use_container_width=True)
        render_pairing_diagram(st.session_state.optimized_results_df, "Optimized source-to-sink matches")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Maximum total heat integration", f"{st.session_state.optimized_total_q:.4f} kW")
        with c2:
            st.metric("Total HX capital", f"${st.session_state.optimized_total_capital:,.2f}")
        with c3:
            st.metric("Annual pump operating cost (cold fluid)", f"${st.session_state.optimized_total_pump_cost:,.2f}/yr")
        with c4:
            st.metric("Total annual cost of heat Integration", f"${st.session_state.optimized_total_annual_cost:,.2f}/yr")

        total_assignments = math.factorial(4) * math.factorial(4)
        st.caption(
            f"Feasible assignments found: {st.session_state.optimized_feasible_count} "
            f"out of {total_assignments} total assignments checked."
        )
    elif optimize:
        st.warning("No feasible one-to-one assignment found for the given inputs.")
