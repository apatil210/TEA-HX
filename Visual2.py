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
        "Source 1": 110,
        "Source 2": 260,
        "Source 3": 410,
        "Source 4": 560,
    }
    sink_y = {
        "Sink 1": 110,
        "Sink 2": 260,
        "Sink 3": 410,
        "Sink 4": 560,
    }

    width = 1100
    height = 680
    left_x = 135
    right_x = 965
    rx = 128
    ry = 58

    bg_color = "#ececec"
    node_fill = "#2f6690"
    node_stroke = "#17384f"
    title_color = "#243746"
    hx_text_color = "#314654"

    link_colors = [
        "#69b3d7",
        "#5ec2c4",
        "#8eb8e5",
        "#7aa6d1",
        "#62c6a6",
        "#a08fd5",
    ]

    lane_xs = [390, 445, 500, 555]

    line_parts = []
    label_parts = []
    shadow_parts = []

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

        x_start = left_x + rx
        x_end = right_x - rx

        mid_y = (y1 + y2) / 2
        label_y = mid_y - 10 if abs(y1 - y2) > 30 else mid_y - 18

        shadow_parts.append(f"""
        <path d="M {x_start} {y1}
                 C {x_start + 70} {y1}, {lane_x - 20} {y1}, {lane_x} {y1}
                 L {lane_x} {y2}
                 C {lane_x + 20} {y2}, {x_end - 70} {y2}, {x_end} {y2}"
              fill="none"
              stroke="rgba(255,255,255,0.38)"
              stroke-width="9"
              stroke-linecap="round"
              stroke-linejoin="round"/>
        """)

        line_parts.append(f"""
        <path d="M {x_start} {y1}
                 C {x_start + 70} {y1}, {lane_x - 20} {y1}, {lane_x} {y1}
                 L {lane_x} {y2}
                 C {lane_x + 20} {y2}, {x_end - 70} {y2}, {x_end} {y2}"
              fill="none"
              stroke="{color}"
              stroke-width="5"
              stroke-linecap="round"
              stroke-linejoin="round"/>
        """)

        if hx:
            label_parts.append(
                f"""
                <g>
                    <rect x="{lane_x - 2}" y="{label_y - 16}" rx="10" ry="10"
                          width="58" height="24"
                          fill="white" fill-opacity="0.75"/>
                    <text x="{lane_x + 27}" y="{label_y}"
                          text-anchor="middle"
                          font-size="13"
                          fill="{hx_text_color}"
                          font-weight="600">{hx}</text>
                </g>
                """
            )

    node_parts = []
    for i in range(1, 5):
        sy = source_y[f"Source {i}"]
        ty = sink_y[f"Sink {i}"]

        node_parts.append(f"""
        <ellipse cx="{left_x}" cy="{sy}" rx="{rx}" ry="{ry}"
                 fill="{node_fill}" stroke="{node_stroke}" stroke-width="2.5"/>
        <text x="{left_x}" y="{sy - 18}" text-anchor="middle"
              font-size="19" fill="white" font-weight="500">Heat</text>
        <text x="{left_x}" y="{sy + 10}" text-anchor="middle"
              font-size="19" fill="white" font-weight="500">Source</text>
        <text x="{left_x}" y="{sy + 38}" text-anchor="middle"
              font-size="19" fill="white" font-weight="500">{i}</text>
        """)

        node_parts.append(f"""
        <ellipse cx="{right_x}" cy="{ty}" rx="{rx}" ry="{ry}"
                 fill="{node_fill}" stroke="{node_stroke}" stroke-width="2.5"/>
        <text x="{right_x}" y="{ty - 4}" text-anchor="middle"
              font-size="19" fill="white" font-weight="500">Heat Sink</text>
        <text x="{right_x}" y="{ty + 28}" text-anchor="middle"
              font-size="19" fill="white" font-weight="500">{i}</text>
        """)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <style>
        body {{
          margin: 0;
          padding: 0;
          background: {bg_color};
          font-family: Arial, Helvetica, sans-serif;
        }}
        .wrap {{
          width: 100%;
          overflow-x: auto;
          background: {bg_color};
          border-radius: 14px;
          padding: 10px 8px 12px 8px;
        }}
        svg {{
          display: block;
          width: 100%;
          max-width: 1100px;
          height: auto;
          background: {bg_color};
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
          <text x="36" y="42" font-size="28" font-weight="700" fill="{title_color}">{title}</text>
          {''.join(shadow_parts)}
          {''.join(line_parts)}
          {''.join(label_parts)}
          {''.join(node_parts)}
        </svg>
      </div>
    </body>
    </html>
    """

    components.html(html, height=700, scrolling=False)


def build_composite_curve_segments(streams, stream_type, delta_t_min=10.0):
    shifted_streams = []

    for stream in streams:
        if stream_type == "hot":
            tin = stream["Tin"] - delta_t_min / 2.0
            tout = stream["Tout"] - delta_t_min / 2.0
        else:
            tin = stream["Tin"] + delta_t_min / 2.0
            tout = stream["Tout"] + delta_t_min / 2.0

        cp = stream["mcp"]

        if cp <= 0 or abs(tin - tout) < 1e-12:
            continue

        shifted_streams.append({
            "Tin": tin,
            "Tout": tout,
            "mcp": cp
        })

    if not shifted_streams:
        return pd.DataFrame(columns=["Q_kW", "Shifted_T_C"])

    temp_levels = sorted(
        {s["Tin"] for s in shifted_streams} | {s["Tout"] for s in shifted_streams},
        reverse=True
    )

    rows = []
    q = 0.0
    rows.append({"Q_kW": q, "Shifted_T_C": temp_levels[0]})

    for i in range(len(temp_levels) - 1):
        t_upper = temp_levels[i]
        t_lower = temp_levels[i + 1]

        active_cp = 0.0
        for s in shifted_streams:
            s_high = max(s["Tin"], s["Tout"])
            s_low = min(s["Tin"], s["Tout"])
            if s_high >= t_upper and s_low <= t_lower:
                active_cp += s["mcp"]

        dq = active_cp * (t_upper - t_lower) / 1000.0
        q += dq
        rows.append({"Q_kW": q, "Shifted_T_C": t_lower})

    return pd.DataFrame(rows)


def extract_streams_for_pinch(df_pairs, sources, sinks):
    hot_streams = []
    cold_streams = []

    source_index_map = {f"Source {i}": i - 1 for i in range(1, 5)}
    sink_index_map = {f"Sink {i}": i - 1 for i in range(1, 5)}

    for _, row in df_pairs.iterrows():
        src_name = row.get("Source")
        sink_name = row.get("Sink")

        if src_name not in source_index_map or sink_name not in sink_index_map:
            continue

        src = sources[source_index_map[src_name]]
        snk = sinks[sink_index_map[sink_name]]

        try:
            hot_out = float(str(row.get("Hot outlet temp (°C)", src["thi"])).replace(",", ""))
        except Exception:
            hot_out = src["thi"]

        try:
            cold_out = float(str(row.get("Cold outlet temp (°C)", snk["tci"])).replace(",", ""))
        except Exception:
            cold_out = snk["tci"]

        hot_streams.append({
            "name": src_name,
            "Tin": src["thi"],
            "Tout": hot_out,
            "mcp": src["mh"] * src["cph"],
        })

        cold_streams.append({
            "name": sink_name,
            "Tin": snk["tci"],
            "Tout": cold_out,
            "mcp": snk["mc"] * snk["cpc"],
        })

    return hot_streams, cold_streams


def interpolate_temperature(curve_df, q_value):
    curve_df = curve_df.sort_values("Q_kW").reset_index(drop=True)

    if q_value <= curve_df.loc[0, "Q_kW"]:
        return curve_df.loc[0, "Shifted_T_C"]

    if q_value >= curve_df.loc[len(curve_df) - 1, "Q_kW"]:
        return curve_df.loc[len(curve_df) - 1, "Shifted_T_C"]

    for i in range(len(curve_df) - 1):
        q1 = curve_df.loc[i, "Q_kW"]
        q2 = curve_df.loc[i + 1, "Q_kW"]
        t1 = curve_df.loc[i, "Shifted_T_C"]
        t2 = curve_df.loc[i + 1, "Shifted_T_C"]

        if q1 <= q_value <= q2:
            if abs(q2 - q1) < 1e-12:
                return t1
            frac = (q_value - q1) / (q2 - q1)
            return t1 + frac * (t2 - t1)

    return curve_df.loc[len(curve_df) - 1, "Shifted_T_C"]


def find_required_cold_shift(hot_curve, cold_curve):
    q_candidates = sorted(set(hot_curve["Q_kW"].tolist() + cold_curve["Q_kW"].tolist()))
    max_hot_q = hot_curve["Q_kW"].max()
    max_cold_q = cold_curve["Q_kW"].max()

    best_shift = None
    best_min_gap = None

    shift_grid = [i * max(max_hot_q, max_cold_q) / 800.0 for i in range(801)]

    for shift in shift_grid:
        overlap_q = [q for q in q_candidates if 0 <= q - shift <= max_cold_q and 0 <= q <= max_hot_q]
        if not overlap_q:
            continue

        gaps = []
        for q in overlap_q:
            th = interpolate_temperature(hot_curve, q)
            tc = interpolate_temperature(cold_curve, q - shift)
            gaps.append(th - tc)

        min_gap = min(gaps)

        if min_gap >= -1e-6:
            best_shift = shift
            best_min_gap = min_gap
            break

    if best_shift is None:
        best_shift = 0.0
        best_min_gap = None

    return best_shift, best_min_gap


def find_pinch_point(hot_curve, cold_curve, cold_shift):
    q_candidates = sorted(
        set(hot_curve["Q_kW"].tolist() + [q + cold_shift for q in cold_curve["Q_kW"].tolist()])
    )

    max_hot_q = hot_curve["Q_kW"].max()
    max_cold_q = cold_curve["Q_kW"].max()

    overlap_q = [q for q in q_candidates if 0 <= q <= max_hot_q and 0 <= q - cold_shift <= max_cold_q]

    if not overlap_q:
        return None

    best = None
    best_gap = None

    for q in overlap_q:
        th = interpolate_temperature(hot_curve, q)
        tc = interpolate_temperature(cold_curve, q - cold_shift)
        gap = th - tc

        if best is None or gap < best_gap:
            best = {
                "Q_kW": q,
                "Hot_T": th,
                "Cold_T": tc,
                "Gap": gap
            }
            best_gap = gap

    return best


def render_pinch_curves(df_pairs, title, sources, sinks, delta_t_min=10.0):
    if df_pairs is None or df_pairs.empty:
        st.info("No valid source-sink pairs available to visualize.")
        return

    hot_streams, cold_streams = extract_streams_for_pinch(df_pairs, sources, sinks)

    if not hot_streams or not cold_streams:
        st.info("Insufficient stream data to build composite curves.")
        return

    hot_curve = build_composite_curve_segments(hot_streams, "hot", delta_t_min=delta_t_min)
    cold_curve = build_composite_curve_segments(cold_streams, "cold", delta_t_min=delta_t_min)

    if hot_curve.empty or cold_curve.empty:
        st.info("Unable to construct composite curves for the selected streams.")
        return

    cold_shift, min_gap = find_required_cold_shift(hot_curve, cold_curve)
    pinch = find_pinch_point(hot_curve, cold_curve, cold_shift)

    hot_plot = hot_curve.copy()
    cold_plot = cold_curve.copy()

    hot_plot["Q_plot"] = hot_plot["Q_kW"] / 1000.0
    cold_plot["Q_plot"] = (cold_plot["Q_kW"] + cold_shift) / 1000.0

    hot_plot["Curve"] = "Hot composite curve"
    cold_plot["Curve"] = "Cold composite curve"

    combined = pd.concat([hot_plot, cold_plot], ignore_index=True)

    base = alt.Chart(combined).encode(
        x=alt.X(
            "Q_plot:Q",
            title="Duty (MW)",
            axis=alt.Axis(
                grid=True,
                gridColor="#d9d9d9",
                gridDash=[6, 6],
                tickColor="black",
                domainColor="black",
                labelColor="black",
                titleColor="black",
                labelFontSize=12,
                titleFontSize=16
            )
        ),
        y=alt.Y(
            "Shifted_T_C:Q",
            title="Shifted Temperature (°C)",
            axis=alt.Axis(
                grid=True,
                gridColor="#d9d9d9",
                gridDash=[6, 6],
                tickColor="black",
                domainColor="black",
                labelColor="black",
                titleColor="black",
                labelFontSize=12,
                titleFontSize=16
            )
        ),
        color=alt.Color(
            "Curve:N",
            scale=alt.Scale(
                domain=["Cold composite curve", "Hot composite curve"],
                range=["#3b1fb3", "#ff1f1f"]
            ),
            legend=alt.Legend(
                title=None,
                orient="bottom",
                direction="horizontal",
                labelFontSize=13,
                symbolSize=140
            )
        ),
        shape=alt.Shape(
            "Curve:N",
            scale=alt.Scale(
                domain=["Cold composite curve", "Hot composite curve"],
                range=["triangle", "circle"]
            ),
            legend=None
        )
    )

    lines = base.mark_line(strokeWidth=1.6).encode(detail="Curve:N")

    points = base.mark_point(filled=True, size=70).encode(
        detail="Curve:N",
        tooltip=[
            alt.Tooltip("Curve:N"),
            alt.Tooltip("Q_plot:Q", format=".4f", title="Duty (MW)"),
            alt.Tooltip("Shifted_T_C:Q", format=".2f", title="Shifted Temperature (°C)")
        ]
    )

    layers = [lines, points]

    if pinch is not None:
        pinch_df = pd.DataFrame([{
            "Q_plot": pinch["Q_kW"] / 1000.0,
            "Shifted_T_C": pinch["Hot_T"],
            "Label": f"Pinch, gap ≈ {pinch['Gap']:.2f} °C"
        }])

        pinch_marker = alt.Chart(pinch_df).mark_point(
            shape="diamond",
            size=120,
            filled=True,
            color="black"
        ).encode(
            x="Q_plot:Q",
            y="Shifted_T_C:Q",
            tooltip=[
                "Label:N",
                alt.Tooltip("Q_plot:Q", format=".4f", title="Duty (MW)")
            ]
        )

        pinch_text = alt.Chart(pinch_df).mark_text(
            dx=10,
            dy=-10,
            fontSize=12,
            color="black",
            fontWeight="bold",
            align="left"
        ).encode(
            x="Q_plot:Q",
            y="Shifted_T_C:Q",
            text=alt.value("Pinch")
        )

        layers.extend([pinch_marker, pinch_text])

    chart = alt.layer(*layers).properties(
        title=title,
        height=560
    ).configure_view(
        stroke="black",
        strokeWidth=1,
        fill="white"
    ).configure_title(
        anchor="middle",
        fontSize=18,
        color="black"
    ).configure_legend(
        orient="bottom",
        direction="horizontal"
    ).configure(
        background="white"
    )

    st.altair_chart(chart, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("ΔTmin used", f"{delta_t_min:.1f} °C")
    with c2:
        st.metric("Hot composite load", f"{hot_curve['Q_kW'].max() / 1000.0:.4f} MW")
    with c3:
        st.metric("Cold composite load", f"{cold_curve['Q_kW'].max() / 1000.0:.4f} MW")
    with c4:
        if pinch is not None:
            st.metric("Pinch approach", f"{pinch['Gap']:.2f} °C")
        else:
            st.metric("Pinch approach", "N/A")

    st.caption(
        "Literature-style shifted composite curves: the cold composite curve is horizontally shifted until it touches the hot composite curve at the pinch."
    )

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
