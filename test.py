import streamlit as st
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="ASLS Pneumatic Launcher – Design Review", layout="wide")
st.title("ASLS Pneumatic Launcher – Detail Design Simulator")
st.caption("Based on Group 10's mathematical models: v₀ = Kv × P_reg | H = (v₀ sinθ)²/(2g) | R = v₀² sin(2θ)/g")

# ---------- Scenario definitions ----------
scenarios = {
    "Normal": {"wind": 10, "load_height": 4.3, "angle": 65, "pressure": 50, "rain": False, "barrel": "Optimised Helical (Kv = 0.24)"},
    "Rain + 40 km/h Wind": {"wind": 40, "load_height": 4.3, "angle": 65, "pressure": 50, "rain": True, "barrel": "Optimised Helical (Kv = 0.24)"},
    "Tall Load (5.0 m)": {"wind": 0, "load_height": 5.0, "angle": 70, "pressure": 50, "rain": False, "barrel": "Optimised Helical (Kv = 0.24)"},
    "Failure Demo (Standard Barrel)": {"wind": 10, "load_height": 4.3, "angle": 65, "pressure": 50, "rain": False, "barrel": "Standard (Kv = 0.20)"}
}

if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = "Normal"

st.header("Quick Scenario Selector")
cols = st.columns(4)
for i, (name, params) in enumerate(scenarios.items()):
    if cols[i].button(name, use_container_width=True):
        st.session_state.current_scenario = name
        st.rerun()

st.markdown(f"**Selected scenario:** {st.session_state.current_scenario}")
current = scenarios[st.session_state.current_scenario]

# ---------- Advanced settings (override) ----------
with st.expander("Advanced Settings (override scenario values)"):
    pressure_psi = st.slider("Regulated Pressure (PSI)", 35, 70, current["pressure"])
    barrel_opts = ["Standard (Kv = 0.20)", "Optimised Helical (Kv = 0.24)"]
    default_idx = 0 if current["barrel"] == barrel_opts[0] else 1
    barrel_type = st.radio("Barrel Type", barrel_opts, index=default_idx)
    kv = 0.20 if "Standard" in barrel_type else 0.24
    angle_deg = st.slider("Launch Angle (degrees)", 55, 75, current["angle"])
    wind_kmh = st.slider("Crosswind (km/h)", 0, 50, current["wind"])
    rain = st.checkbox("Rain", value=current["rain"])
    load_height = st.number_input("Load Height (m)", 3.0, 6.0, current["load_height"], 0.1)

# ---------- Constants and functions ----------
g = 9.81
REG_MIN_PSI = 46
AZIMUTH_OFFSET_COEFF = 0.02425   # metres lateral offset per km/h (0.97 m at 40 km/h)
Kd = 0.045

def muzzle_velocity(psi, kv): return kv * psi
def apex_height(v0, theta_deg): return (v0 * np.sin(np.radians(theta_deg)))**2 / (2 * g)
def horizontal_range(v0, theta_deg): return (v0**2 * np.sin(2 * np.radians(theta_deg))) / g
def flight_time(v0, theta_deg): return 2 * v0 * np.sin(np.radians(theta_deg)) / g
def raw_drift(wind_kmh, t_flight): return Kd * (wind_kmh / 3.6) * t_flight
def net_drift(wind_kmh, t_flight):
    if wind_kmh <= 0: return 0.0
    raw = raw_drift(wind_kmh, t_flight)
    after_gyro = raw * 0.65
    offset = AZIMUTH_OFFSET_COEFF * min(wind_kmh, 40)
    return max(0, after_gyro - offset)

# ---------- Live single-launch calculator ----------
st.header("Single‑Launch Performance (Current Settings)")

v0 = muzzle_velocity(pressure_psi, kv)
if rain: v0 *= 0.98
apex = apex_height(v0, angle_deg)
range_m = horizontal_range(v0, angle_deg)
t_flight = flight_time(v0, angle_deg)
raw = raw_drift(wind_kmh, t_flight)
gyro_drift = raw * 0.65
azimuth_offset_m = AZIMUTH_OFFSET_COEFF * min(wind_kmh, 40) if wind_kmh > 0 else 0.0
drift_net = net_drift(wind_kmh, t_flight)
# Convert offset to angle (degrees)
approx_distance = 7.0
azimuth_angle_deg = np.degrees(np.arctan(azimuth_offset_m / approx_distance)) if azimuth_offset_m > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("Muzzle Velocity", f"{v0:.1f} m/s")
apex_ok = apex >= load_height + 0.4
col2.metric("Apex Height", f"{apex:.2f} m", delta="PASS" if apex_ok else "FAIL",
            delta_color="normal" if apex_ok else "inverse")
range_ok = range_m >= 2.4
col3.metric("Horizontal Range", f"{range_m:.1f} m", delta="PASS" if range_ok else "FAIL",
            delta_color="normal" if range_ok else "inverse")

if wind_kmh > 0:
    st.subheader("Crosswind Compensation")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Raw Drift", f"{raw:.2f} m")
    c2.metric("After Gyro (-35%)", f"{gyro_drift:.2f} m")
    c3.metric("Azimuth Offset", f"{azimuth_angle_deg:.1f}°", delta=f"({azimuth_offset_m:.2f} m lateral)")
    c4.metric("Net Drift", f"{drift_net:.2f} m", delta="Cancelled" if drift_net < 0.3 else "❌")
else:
    st.info("No crosswind – gyro stabilisation active but no drift.")

st.markdown(f"**Clearance margin:** {apex - load_height:.2f} m above {load_height} m load  →  {'Satisfies SR‑04' if apex_ok else 'Fails'}")

# ---------- Mission simulation (fixed) ----------
st.divider()
st.subheader("Full Load Mission Simulation")
num_straps = st.slider("Number of straps", 6, 13, 10)
if st.button("Run Simulation"):
    cylinder = 60.0
    drop_per_shot = (60 - 35) / 12
    swaps = 0
    rows = []
    progress = st.progress(0)
    status = st.empty()
    gauge = st.empty()
    for strap in range(1, num_straps + 1):
        # Regulated output
        reg = pressure_psi if cylinder >= pressure_psi else cylinder
        if reg < REG_MIN_PSI:
            status.warning(f"Strap {strap}: reg {reg:.0f} PSI < {REG_MIN_PSI}. Swapping cylinder...")
            time.sleep(0.3)
            cylinder = 60.0
            reg = pressure_psi
            swaps += 1
            status.info(f"Cylinder swapped. Regulated output {reg:.0f} PSI")
            time.sleep(0.3)
        # Compute performance with same functions and parameters
        v = muzzle_velocity(reg, kv)
        if rain: v *= 0.98
        a = apex_height(v, angle_deg)
        r = horizontal_range(v, angle_deg)
        t = flight_time(v, angle_deg)
        d = net_drift(wind_kmh, t)
        apex_ok_mission = a >= load_height + 0.4
        drift_ok_mission = d < 0.3 or wind_kmh == 0
        success = apex_ok_mission and drift_ok_mission
        rows.append({
            "Strap": strap,
            "Reg (PSI)": f"{reg:.0f}",
            "v₀ (m/s)": f"{v:.1f}",
            "Apex (m)": f"{a:.2f}",
            "Range (m)": f"{r:.1f}",
            "Drift (m)": f"{d:.2f}",
            "Success": "✅" if success else "❌"
        })
        gauge.progress(int(cylinder), text=f"Cylinder: {cylinder:.0f} PSI | Regulated: {reg:.0f} PSI")
        progress.progress(strap / num_straps)
        status.info(f"Strap {strap}/{num_straps}: apex {a:.2f} m → {'PASS' if success else 'FAIL'}")
        time.sleep(0.15)
        if strap < num_straps:
            cylinder = max(35, cylinder - drop_per_shot)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    success_count = df[df["Success"] == "✅"].shape[0]
    st.success(f"**Mission complete:** {success_count}/{num_straps} straps secured. Cylinder swaps: {swaps}")

st.caption("Traces to: UR‑02, UR‑04, UR‑10, UR‑11, SR‑03, SR‑04, SR‑06, SR‑11, SR‑12, SR‑13.")