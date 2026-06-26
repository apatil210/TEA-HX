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
            cost = calculate_shell_tube_cost(area, exchanger_type, pressure_band, material, ci_base, ci_calc)

            st.subheader("Thermal design result")

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

            st.subheader("Shell-and-tube cost result")

            c1, c2, c3 = st.columns(3)
            c1.metric("Base cost, C_B ($)", f"{cost['base_cost']:,.2f}")
            c2.metric("Purchased cost, C_E ($)", f"{cost['purchased_cost']:,.2f}")
            c3.metric("Updated cost ($)", f"{cost['updated_cost']:,.2f}")

    except Exception as e:
        st.error(str(e))
