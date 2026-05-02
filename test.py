import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from urllib.parse import urlencode

st.set_page_config(page_title="ASLS – Azimuth Offset Planner", layout="wide")

st.title("🎯 ASLS Azimuth Offset Planner")
st.markdown("Get your location (GPS), live wind, and the exact azimuth offset to rotate the bipod.")

# ========== Constants ==========
g = 9.81
DISTANCE_TO_FAR_SIDE = 7.0
Kd = 0.045
GYRO_REDUCTION = 0.65
AZIMUTH_OFFSET_COEFF = 0.02425
REGULATED_PSI = 50
ANGLE_DEG = 65
KV = 0.24
LOAD_HEIGHT_DEFAULT = 4.3

# ========== Weather API ==========
@st.cache_data(ttl=600)
def get_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        current = data.get("current_weather", {})
        wind_speed = current.get("windspeed")
        wind_dir = current.get("winddirection")
        if wind_speed is not None and wind_dir is not None:
            return float(wind_speed), float(wind_dir)
        return None, None
    except Exception as e:
        st.error(f"Weather API error: {e}")
        return None, None

# ========== Performance functions ==========
def flight_time(v0, theta_deg):
    rad = np.radians(theta_deg)
    return 2 * v0 * np.sin(rad) / g

def raw_lateral_drift(wind_m_s, t_flight):
    return Kd * wind_m_s * t_flight

def net_drift(wind_kmh, t_flight):
    if wind_kmh <= 0:
        return 0.0
    wind_m_s = wind_kmh / 3.6
    raw = raw_lateral_drift(wind_m_s, t_flight)
    after_gyro = raw * GYRO_REDUCTION
    offset_m = AZIMUTH_OFFSET_COEFF * min(wind_kmh, 40)
    return max(0, after_gyro - offset_m)

def muzzle_velocity(psi, kv):
    return kv * psi

def apex_height(v0, theta_deg):
    rad = np.radians(theta_deg)
    return (v0 * np.sin(rad))**2 / (2 * g)

def horizontal_range(v0, theta_deg):
    return (v0**2 * np.sin(2 * np.radians(theta_deg))) / g

# ========== URL parameters ==========
query_params = st.query_params

# Check if we have coordinates from geolocation
if "lat" in query_params and "lon" in query_params:
    try:
        lat = float(query_params["lat"])
        lon = float(query_params["lon"])
        # Store in session state
        st.session_state.user_lat = lat
        st.session_state.user_lon = lon
        # Clear params to avoid re-processing
        st.query_params.clear()
        # Fetch weather for these coordinates
        with st.spinner("Fetching live wind data for your location..."):
            speed, direction = get_weather(lat, lon)
            if speed is not None:
                st.session_state.wind_speed = speed
                st.session_state.wind_dir = direction
                st.session_state.location_fetched = True
                st.success(f"Location detected! Wind: {speed} km/h from {direction}°")
            else:
                st.warning("Weather data not available for these coordinates.")
                st.session_state.location_fetched = False
    except:
        pass

# ========== Session state initialisation ==========
if "wind_speed" not in st.session_state:
    st.session_state.wind_speed = 25
if "wind_dir" not in st.session_state:
    st.session_state.wind_dir = 90
if "user_heading" not in st.session_state:
    st.session_state.user_heading = 0
if "user_lat" not in st.session_state:
    st.session_state.user_lat = None
if "user_lon" not in st.session_state:
    st.session_state.user_lon = None
if "location_fetched" not in st.session_state:
    st.session_state.location_fetched = False
if "pressure" not in st.session_state:
    st.session_state.pressure = REGULATED_PSI
if "barrel" not in st.session_state:
    st.session_state.barrel = "Optimised Helical (Kv = 0.24)"
if "angle" not in st.session_state:
    st.session_state.angle = ANGLE_DEG
if "rain" not in st.session_state:
    st.session_state.rain = False
if "load_height" not in st.session_state:
    st.session_state.load_height = LOAD_HEIGHT_DEFAULT

# ========== Sidebar: Location and Wind ==========
st.sidebar.header("📍 Location & Wind")

# HTML/JS geolocation button (no extra package)
geo_html = """
<div id="geo-status" style="margin-bottom: 10px; font-size:0.9rem; color: #888;"></div>
<button id="geo-btn" style="padding: 8px 16px; background-color: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer;">📍 Get My Current Location (GPS)</button>
<script>
    const btn = document.getElementById('geo-btn');
    const statusDiv = document.getElementById('geo-status');
    btn.onclick = () => {
        if (!navigator.geolocation) {
            statusDiv.innerHTML = "Geolocation not supported by this browser.";
            return;
        }
        statusDiv.innerHTML = "Requesting permission...";
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                statusDiv.innerHTML = "Location obtained. Reloading...";
                const url = new URL(window.location.href);
                url.searchParams.set('lat', lat);
                url.searchParams.set('lon', lon);
                window.location.href = url.toString();
            },
            (error) => {
                statusDiv.innerHTML = "Error: " + error.message + ". Try allowing location in browser settings.";
            }
        );
    };
</script>
"""
with st.sidebar:
    st.components.v1.html(geo_html, height=100)
    st.caption("Click the button, allow location, then the page reloads with your coordinates.")

if st.session_state.user_lat:
    st.sidebar.success(f"✅ Coordinates: {st.session_state.user_lat:.3f}, {st.session_state.user_lon:.3f}")
    st.sidebar.metric("🌬️ Wind used", f"{st.session_state.wind_speed} km/h from {st.session_state.wind_dir}°")
else:
    st.sidebar.info("No location yet. Click the button above (on phone, allow GPS).")

st.sidebar.markdown("---")
st.sidebar.subheader("✍️ Manual Override")
use_manual = st.sidebar.checkbox("Enter wind/heading manually", value=False)
if use_manual:
    manual_speed = st.sidebar.number_input("Wind speed (km/h)", 0, 100, st.session_state.wind_speed)
    manual_dir = st.sidebar.number_input("Wind direction (deg)", 0, 360, st.session_state.wind_dir)
    manual_heading = st.sidebar.number_input("Your heading (deg, 0=N)", 0, 360, st.session_state.user_heading)
    st.session_state.wind_speed = manual_speed
    st.session_state.wind_dir = manual_dir
    st.session_state.user_heading = manual_heading
    st.session_state.location_fetched = True   # treat as ready
else:
    # If manual not active and we have a location, keep that; if no location, keep default values
    pass

# Show current values
st.sidebar.metric("🌬️ Current wind", f"{st.session_state.wind_speed} km/h from {st.session_state.wind_dir}°")
st.sidebar.metric("🧭 Your heading", f"{st.session_state.user_heading}° (0=N)")

# ========== Advanced Launcher Settings ==========
with st.expander("⚙️ Advanced Launcher Settings"):
    pressure_psi = st.slider("Regulated Pressure (PSI)", 35, 70, st.session_state.pressure)
    barrel_type = st.radio("Barrel Type", ["Optimised Helical (Kv = 0.24)", "Standard (Kv = 0.20)"],
                           index=0 if "Optimised" in st.session_state.barrel else 1)
    angle_deg = st.slider("Launch Angle (degrees)", 55, 75, st.session_state.angle)
    rain = st.checkbox("Rain (2% velocity penalty)", st.session_state.rain)
    load_height = st.number_input("Load Height (m)", 3.0, 6.0, st.session_state.load_height, 0.1)
    # Update session
    st.session_state.pressure = pressure_psi
    st.session_state.barrel = barrel_type
    st.session_state.angle = angle_deg
    st.session_state.rain = rain
    st.session_state.load_height = load_height

kv = 0.24 if "Optimised" in st.session_state.barrel else 0.20

# ========== Crosswind & azimuth calculation ==========
wind_speed = st.session_state.wind_speed
wind_dir = st.session_state.wind_dir
heading = st.session_state.user_heading

rel_rad = np.radians(wind_dir - heading)
crosswind_kmh = abs(wind_speed * np.sin(rel_rad))

v0 = muzzle_velocity(st.session_state.pressure, kv)
if st.session_state.rain:
    v0 *= 0.98
t_flight = flight_time(v0, st.session_state.angle)
apex = apex_height(v0, st.session_state.angle)
range_m = horizontal_range(v0, st.session_state.angle)

if crosswind_kmh > 0:
    raw = raw_lateral_drift(crosswind_kmh / 3.6, t_flight)
    gyro_drift = raw * GYRO_REDUCTION
    offset_m = AZIMUTH_OFFSET_COEFF * min(crosswind_kmh, 40)
    azimuth_angle = np.degrees(np.arctan(offset_m / DISTANCE_TO_FAR_SIDE))
    net_d = max(0, gyro_drift - offset_m)
else:
    raw = gyro_drift = offset_m = azimuth_angle = net_d = 0

# ========== Main Results ==========
st.header("🎯 Azimuth Offset (Primary Output)")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    if crosswind_kmh > 0:
        st.metric("🌬️ Crosswind component", f"{crosswind_kmh:.1f} km/h")
        st.metric("🌀 Rotate bipod UPWIND by", f"{azimuth_angle:.1f}°",
                  delta=f"→ cancels {gyro_drift:.2f} m drift", delta_color="normal")
    else:
        st.success("✅ No crosswind component (wind aligned with heading).")
        st.metric("Azimuth offset", "0.0°", delta="No rotation")

with col2:
    st.metric("📏 Raw drift (no gyro)", f"{raw:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric("⚙️ After gyro (helical barrel)", f"{gyro_drift:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric("🎯 Final net drift", f"{net_d:.2f} m", delta="✅ Canceled" if net_d < 0.1 else "⚠️")

with col3:
    required_apex = st.session_state.load_height + 0.4
    st.metric("Apex height / Clear load", f"{apex:.2f} m",
              delta="✅ PASS" if apex >= required_apex else "❌ FAIL")
    st.metric("Horizontal range / Trailer width", f"{range_m:.1f} m",
              delta="✅ PASS" if range_m >= 2.4 else "❌ FAIL")

if crosswind_kmh > 0:
    st.info(f"👉 **Operator instruction:** Rotate bipod **{azimuth_angle:.1f} degrees upwind** (toward the wind) before each launch.")
else:
    st.info("✅ Aim straight across the trailer. No azimuth offset needed.")

# ========== Optional mission simulation ==========
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
        reg = st.session_state.pressure if cylinder >= st.session_state.pressure else cylinder
        if reg < 46:
            status.warning(f"Strap {i}: low pressure ({reg:.0f} PSI). Swapping...")
            time.sleep(0.3)
            cylinder = 60.0
            reg = st.session_state.pressure
            swaps += 1
            status.info("Cylinder swapped.")
            time.sleep(0.3)
        v = muzzle_velocity(reg, kv)
        if st.session_state.rain:
            v *= 0.98
        a = apex_height(v, st.session_state.angle)
        r = horizontal_range(v, st.session_state.angle)
        t = flight_time(v, st.session_state.angle)
        d = net_drift(crosswind_kmh, t)
        apex_ok = a >= st.session_state.load_height + 0.4
        success = apex_ok and (d < 0.3 or crosswind_kmh == 0)
        rows.append({
            "Strap": i,
            "Reg (PSI)": f"{reg:.0f}",
            "v₀": f"{v:.1f}",
            "Apex (m)": f"{a:.2f}",
            "Range (m)": f"{r:.1f}",
            "Drift (m)": f"{d:.2f}",
            "Success": "✅" if success else "❌"
        })
        progress.progress(i / num_straps)
        status.info(f"Strap {i}/{num_straps}: apex {a:.2f}m – {'✅' if success else '❌'}")
        time.sleep(0.15)
        if i < num_straps:
            cylinder = max(35, cylinder - drop_per_shot)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.success(f"Completed {df[df['Success']=='✅'].shape[0]}/{num_straps} straps. Swaps: {swaps}")

st.caption("📍 How it works: Click 'Get My Current Location' – your browser asks for permission – then page reloads with your actual GPS coordinates. Wind is fetched live. If geolocation fails, use Manual Override.")