import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

st.set_page_config(page_title="ASLS Australia – Azimuth Offset Planner", layout="wide")

# ========== Title & Description ==========
st.title("ASLS– Wind‑Based Azimuth Offset Calculator")
st.markdown(
    "Enter your location (or choose a city) to get the **crosswind‑compensated azimuth offset** "
    "for your ASLS pneumatic launcher. The azimuth offset tells you **how many degrees to rotate "
    "the bipod upwind** before each launch."
)

# ========== Constants ==========
g = 9.81                    # m/s²
DISTANCE_TO_FAR_SIDE = 7.0  # metres (from launch point to far‑side landing)
Kd = 0.045                  # drift coefficient
GYRO_REDUCTION = 0.65       # 35% reduction from helical rifling
AZIMUTH_OFFSET_COEFF = 0.02425   # metres per km/h (for reference)
REGULATED_PSI = 50          # default, can be overridden
ANGLE_DEG = 65              # default launch angle
KV = 0.24                   # optimised helical barrel

# ========== Functions ==========
def fetch_openmeteo_weather(lat, lon):
    """Returns current wind speed (km/h) and direction (degrees) using Open-Meteo."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        current = data.get("current_weather", {})
        wind_speed = current.get("windspeed", 0)
        wind_direction = current.get("winddirection", 0)
        return wind_speed, wind_direction
    except Exception as e:
        st.error(f"Could not fetch weather data: {e}")
        return None, None

def get_my_location():
    """Get user's approximate location via ip-api.com (no API key)."""
    try:
        response = requests.get("http://ip-api.com/json/", timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            lat = data.get("lat")
            lon = data.get("lon")
            country = data.get("countryCode")
            city = data.get("city")
            return lat, lon, country, city
    except Exception:
        pass
    return None, None, None, None

# def get_my_location():
#     """Simulate a successful API response for a Melbourne IP address."""
#     # Return data for a known Australian IP address: 119.17.136.36
#     test_latitude = -37.8136
#     test_longitude = 144.9631
#     test_country_code = "AU"
#     test_city = "Melbourne (via Test IP)"

#     # Simulate the data structure you would get from ip-api.com
#     return test_latitude, test_longitude, test_country_code, test_city

def flight_time(v0, theta_deg):
    rad = np.radians(theta_deg)
    t_up = v0 * np.sin(rad) / g
    return 2 * t_up

def raw_lateral_drift(wind_m_s, t_flight):
    return Kd * wind_m_s * t_flight

def net_drift(wind_kmh, t_flight, gyro=True, azimuth_corr=True):
    wind_m_s = wind_kmh / 3.6
    raw = raw_lateral_drift(wind_m_s, t_flight)
    after_gyro = raw * GYRO_REDUCTION if gyro else raw
    if azimuth_corr:
        offset = AZIMUTH_OFFSET_COEFF * min(wind_kmh, 40)
        return max(0, after_gyro - offset)
    return after_gyro

def muzzle_velocity(psi, kv):
    return kv * psi

def apex_height(v0, theta_deg):
    rad = np.radians(theta_deg)
    return (v0 * np.sin(rad))**2 / (2 * g)

# ========== Session state ==========
if "wind_speed" not in st.session_state:
    st.session_state.wind_speed = 0
if "wind_dir" not in st.session_state:
    st.session_state.wind_dir = 0
if "selected_location" not in st.session_state:
    st.session_state.selected_location = None

# ========== Sidebar – Location Selection ==========
st.sidebar.header("📍 Choose Your Location")

location_option = st.sidebar.radio(
    "Location source",
    ["Brisbane", "Adelaide", "Sydney", "Perth", "Use my current location (Australia only)"]
)

city_coords = {
    "Brisbane": (-27.4679, 153.0281),
    "Adelaide": (-34.9287, 138.5986),
    "Sydney": (-33.8651, 151.2099),
    "Perth": (-31.9505, 115.8605)
}

if location_option in city_coords:
    lat, lon = city_coords[location_option]
    st.session_state.selected_location = location_option
    with st.spinner(f"Fetching live wind data for {location_option} ..."):
        wind_speed, wind_dir = fetch_openmeteo_weather(lat, lon)
    if wind_speed is not None:
        st.session_state.wind_speed = wind_speed
        st.session_state.wind_dir = wind_dir
        st.sidebar.success(f"✅ {location_option}: {wind_speed:.1f} km/h, direction {wind_dir:.0f}°")
    else:
        st.sidebar.error("Could not fetch wind data. Try again later.")

else:  # Use my location
    with st.spinner("Detecting your location ..."):
        lat, lon, country, city = get_my_location()
    if lat is not None:
        if country == "AU":
            st.session_state.selected_location = city or "your location"
            with st.spinner(f"Fetching live wind data for {city or 'your area'} ..."):
                wind_speed, wind_dir = fetch_openmeteo_weather(lat, lon)
            if wind_speed is not None:
                st.session_state.wind_speed = wind_speed
                st.session_state.wind_dir = wind_dir
                st.sidebar.success(f" {city or 'Your location'}: {wind_speed:.1f} km/h, direction {wind_dir:.0f}°")
            else:
                st.sidebar.error("Could not fetch wind data.")
        else:
            st.sidebar.error("❌ You are not in Australia. This planner is designed for Australian users only.")
            st.session_state.wind_speed = 0
            st.session_state.wind_dir = 0
    else:
        st.sidebar.error("Could not detect your location. Please choose a city instead.")
        st.session_state.wind_speed = 0
        st.session_state.wind_dir = 0

# ========== Advanced Settings ==========
with st.expander("⚙️ Advanced Settings (override default values)"):
    pressure_psi = st.slider("Regulated Pressure (PSI)", 35, 70, REGULATED_PSI)
    barrel_type = st.radio("Barrel Type", 
                           ["Optimised Helical (Kv = 0.24)", "Standard (Kv = 0.20)"])
    kv = 0.24 if "Optimised" in barrel_type else 0.20
    angle_deg = st.slider("Launch Angle (degrees)", 55, 75, ANGLE_DEG)
    rain = st.checkbox("Rain (2% velocity penalty)")
    load_height = st.number_input("Load Height (m)", 3.0, 6.0, 4.3, step=0.1)

# ========== Crosswind & Azimuth Offset Calculation ==========
# Determine crosswind component (assuming user faces north‑south)
# Wind coming directly from east or west → full crosswind.
# For simplicity, we take the perpendicular component:
# crosswind = wind_speed * sin(wind_dir - 90°) in absolute value.
if st.session_state.wind_speed > 0:
    # Convert wind direction to crosswind component (sin of angle relative to east‑west)
    # If user faces north (0°), a fully east wind (90°) is pure crosswind.
    rad_dir = np.radians(st.session_state.wind_dir)
    crosswind_kmh = abs(st.session_state.wind_speed * np.sin(rad_dir))
else:
    crosswind_kmh = 0

# Performance calculations
v0 = muzzle_velocity(pressure_psi, kv)
if rain:
    v0 *= 0.98
t_flight = flight_time(v0, angle_deg)
apex = apex_height(v0, angle_deg)
range_m = v0**2 * np.sin(2 * np.radians(angle_deg)) / g

# Azimuth offset (main result)
if crosswind_kmh > 0:
    raw = raw_lateral_drift(crosswind_kmh / 3.6, t_flight)
    gyro_drift = raw * GYRO_REDUCTION
    azimuth_offset_m = AZIMUTH_OFFSET_COEFF * min(crosswind_kmh, 40)
    # Actual azimuth angle to rotate the bipod
    azimuth_angle_deg = np.degrees(np.arctan(azimuth_offset_m / DISTANCE_TO_FAR_SIDE))
    net_drift = max(0, gyro_drift - azimuth_offset_m)
else:
    raw = gyro_drift = azimuth_offset_m = azimuth_angle_deg = net_drift = 0

# ========== Main Output ==========
st.header("🎯 Azimuth Offset (Main Result)")
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    if crosswind_kmh > 0:
        st.metric("🌬️ Crosswind Component", f"{crosswind_kmh:.1f} km/h",
                  help="Wind blowing perpendicular to the trailer (east‑west component)")
        st.metric("🌀 Rotate Bipod UPWIND by", f"{azimuth_angle_deg:.1f}°",
                  delta=f"-> Compensates {gyro_drift:.2f} m drift",
                  delta_color="normal")
    else:
        st.info("No crosswind detected. No azimuth offset needed.")

with col2:
    st.metric("📏 Raw Lateral Drift (no compensation)", f"{raw:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric("⚙️ After Gyro Stabilisation (35% reduction)", f"{gyro_drift:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric("🎯 Net Drift After Azimuth Offset", f"{net_drift:.2f} m", 
              delta="✅ Cancelled" if net_drift < 0.1 else "⚠️ Residual")

with col3:
    st.metric("Apex Height", f"{apex:.2f} m", 
              delta="PASS" if apex >= load_height + 0.4 else "FAIL")
    st.metric("Horizontal Range", f"{range_m:.1f} m", 
              delta="PASS" if range_m >= 2.4 else "FAIL")

if crosswind_kmh > 0:
    st.success(f"**👉 Instruction:** Rotate the bipod **{azimuth_angle_deg:.1f} degrees upwind** "
               "before launching. This cancels the crosswind drift.")
else:
    st.success("✅ No crosswind – aim straight across the trailer.")

# ========== Optional Full Mission Simulation ==========
st.divider()
st.subheader("📋 Full Load Mission Check (optional)")
num_straps = st.slider("Number of straps", 6, 13, 10)
if st.button("▶️ Run Mission Check"):
    cylinder = 60.0
    drop_per_shot = (60 - 35) / 12
    swaps = 0
    rows = []
    progress = st.progress(0)
    status = st.empty()
    for i in range(1, num_straps + 1):
        reg = pressure_psi if cylinder >= pressure_psi else cylinder
        if reg < 46:
            status.warning(f"Strap {i}: pressure low. Swapping cylinder...")
            time.sleep(0.3)
            cylinder = 60.0
            reg = pressure_psi
            swaps += 1
            status.info("Cylinder swapped.")
            time.sleep(0.3)
        v = muzzle_velocity(reg, kv)
        if rain: v *= 0.98
        a = apex_height(v, angle_deg)
        r = v**2 * np.sin(2 * np.radians(angle_deg)) / g
        t = flight_time(v, angle_deg)
        d = net_drift(crosswind_kmh, t)
        apex_ok = a >= load_height + 0.4
        success = apex_ok and (d < 0.3 or crosswind_kmh == 0)
        rows.append({
            "Strap": i,
            "Reg (PSI)": f"{reg:.0f}",
            "v₀ (m/s)": f"{v:.1f}",
            "Apex (m)": f"{a:.2f}",
            "Range (m)": f"{r:.1f}",
            "Drift (m)": f"{d:.2f}",
            "Success": "✅" if success else "❌"
        })
        progress.progress(i / num_straps)
        status.info(f"Strap {i}/{num_straps}: {a:.2f}m – {'✅ PASS' if success else '❌ FAIL'}")
        time.sleep(0.15)
        if i < num_straps:
            cylinder = max(35, cylinder - drop_per_shot)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.success(f"Completed {df[df['Success']=='✅'].shape[0]}/{num_straps} straps. Cylinder swaps: {swaps}")

st.caption("Data source: Open‑Meteo (free, no API key). Australian location check via ip-api.com.")