import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from streamlit_geolocation import streamlit_geolocation


st.set_page_config(page_title="ASLS – Azimuth Offset Planner", layout="wide")

st.title("ASLS – Wind‑Based Azimuth Offset Planner")
st.markdown(
    "Get the **azimuth offset** (degrees to rotate bipod upwind) for your pneumatic strap launcher. "
    "Works anywhere in the world."
)

# ========== Constants ==========
g = 9.81
DISTANCE_TO_FAR_SIDE = 7.0
Kd = 0.045
GYRO_REDUCTION = 0.65
AZIMUTH_OFFSET_COEFF = 0.02425
REGULATED_PSI = 50
ANGLE_DEG = 65
KV = 0.24

# ========== Helper functions ==========
def fetch_openmeteo_weather(lat, lon):
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
        st.error(f"Weather fetch error: {e}")
        return None, None

def get_my_location():
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
for key in ["wind_speed", "wind_dir", "selected_location", "user_heading"]:
    if key not in st.session_state:
        st.session_state[key] = None if key == "user_heading" else (0 if "wind" in key else None)

# ========== Sidebar – Location (reordered) ==========
st.sidebar.header("Choose Your Location")
location_option = st.sidebar.radio(
    "Location source",
    ["Use my current location (global)", "Brisbane", "Adelaide", "Sydney", "Perth"]
)

city_coords = {
    "Brisbane": (-27.4679, 153.0281),
    "Adelaide": (-34.9287, 138.5986),
    "Sydney": (-33.8651, 151.2099),
    "Perth": (-31.9505, 115.8605)
}

if location_option == "🔴 Use my current location (global)":
    with st.sidebar:
        location_data = streamlit_geolocation()
    if location_data:
        lat = location_data.get("latitude")
        lon = location_data.get("longitude")
        accuracy = location_data.get("accuracy")     

        if lat and lon:
            # Optionally show accuracy to the user
            if accuracy:
                st.sidebar.caption(f"📍 Location accuracy: ~{accuracy:.0f} meters")

            with st.spinner(f"Fetching live wind data for your location (Lat: {lat:.3f}, Lon: {lon:.3f})..."):
                wind_speed, wind_dir = fetch_openmeteo_weather(lat, lon)
                if wind_speed is not None:
                    st.session_state.wind_speed = wind_speed
                    st.session_state.wind_dir = wind_dir
                    st.sidebar.success(f"✅ Your location: {wind_speed:.1f} km/h, direction {wind_dir:.0f}°")
                else:
                    st.sidebar.error("Weather fetch failed.")
                    st.session_state.wind_speed = 0
                    st.session_state.wind_dir = 0
        else:
            st.sidebar.error("Could not get coordinates. Check browser permissions.")
    else:
        st.sidebar.warning("Location not available. Please choose a city or ensure browser location is enabled.")
        st.session_state.wind_speed = 0
        st.session_state.wind_dir = 0

# ========== Compass / Heading Input ==========
st.sidebar.subheader("Your Facing Direction")

compass_html = """
<div style="text-align:center; padding:10px;">
    <div id="compass-heading" style="font-size:2rem; font-weight:bold;">--°</div>
    <div id="compass-status" style="font-size:0.8rem; color:gray;"></div>
    <button id="compass-btn" style="margin-top:8px; padding:6px 12px;">Request Compass Permission</button>
</div>
<script>
    const headingDiv = document.getElementById('compass-heading');
    const statusDiv = document.getElementById('compass-status');
    const btn = document.getElementById('compass-btn');

    function updateHeading(value) {
        let h = Math.round(value);
        headingDiv.innerText = h + '°';
        statusDiv.innerText = 'Heading updated. Enter this value below.';
        sessionStorage.setItem('asls_heading', h);
    }

    function handleOrientation(event) {
        let alpha = event.alpha;
        let compassHeading = event.webkitCompassHeading || alpha;
        if (compassHeading !== null && compassHeading !== undefined) {
            updateHeading(compassHeading);
        } else {
            statusDiv.innerText = 'Waiting for sensor...';
        }
    }

    if (window.DeviceOrientationEvent) {
        if (typeof DeviceOrientationEvent.requestPermission === 'function') {
            btn.style.display = 'inline-block';
            btn.onclick = async () => {
                try {
                    const perm = await DeviceOrientationEvent.requestPermission();
                    if (perm === 'granted') {
                        window.addEventListener('deviceorientation', handleOrientation);
                        btn.style.display = 'none';
                        statusDiv.innerText = 'Permission granted. Move device slightly.';
                    } else {
                        statusDiv.innerText = 'Permission denied. Use manual input.';
                    }
                } catch(e) {
                    statusDiv.innerText = 'Error requesting permission.';
                }
            };
        } else {
            window.addEventListener('deviceorientation', handleOrientation);
            btn.style.display = 'none';
            statusDiv.innerText = 'Compass active – move device.';
        }
    } else {
        statusDiv.innerText = 'Compass not supported. Use manual input.';
        btn.style.display = 'none';
        headingDiv.innerText = 'N/A';
    }
</script>
"""

with st.sidebar:
    st.components.v1.html(compass_html, height=180)
    st.caption("On phones, tap the button and allow permission. Then copy the heading below. On Laptops, open your phone and use the inbuilt compass to get the direction or just open this website on your phone")

manual_heading = st.sidebar.number_input(
    "Enter your facing direction (degrees, 0‑360)",
    min_value=0, max_value=360, value=0, step=1,
    help="0° = North, 90° = East, 180° = South, 270° = West."
)
st.session_state.user_heading = manual_heading

# ========== Advanced Settings ==========
with st.expander("Advanced Settings (override defaults)"):
    pressure_psi = st.slider("Regulated Pressure (PSI)", 35, 70, REGULATED_PSI)
    barrel_type = st.radio("Barrel Type", ["Optimised Helical (Kv = 0.24)", "Standard (Kv = 0.20)"])
    kv = 0.24 if "Optimised" in barrel_type else 0.20
    angle_deg = st.slider("Launch Angle (degrees)", 55, 75, ANGLE_DEG)
    rain = st.checkbox("Rain (2% velocity penalty)")
    load_height = st.number_input("Load Height (m)", 3.0, 6.0, 4.3, step=0.1)

# ========== Crosswind & Azimuth Offset ==========
if st.session_state.wind_speed and st.session_state.wind_speed > 0 and st.session_state.user_heading is not None:
    rel_angle_rad = np.radians(st.session_state.wind_dir - st.session_state.user_heading)
    crosswind_kmh = abs(st.session_state.wind_speed * np.sin(rel_angle_rad))
else:
    crosswind_kmh = 0

v0 = muzzle_velocity(pressure_psi, kv)
if rain:
    v0 *= 0.98
t_flight = flight_time(v0, angle_deg)
apex = apex_height(v0, angle_deg)
range_m = v0**2 * np.sin(2 * np.radians(angle_deg)) / g

if crosswind_kmh > 0:
    raw = raw_lateral_drift(crosswind_kmh / 3.6, t_flight)
    gyro_drift = raw * GYRO_REDUCTION
    azimuth_offset_m = AZIMUTH_OFFSET_COEFF * min(crosswind_kmh, 40)
    azimuth_angle_deg = np.degrees(np.arctan(azimuth_offset_m / DISTANCE_TO_FAR_SIDE))
    net_drift_val = max(0, gyro_drift - azimuth_offset_m)
else:
    raw = gyro_drift = azimuth_offset_m = azimuth_angle_deg = net_drift_val = 0

# ========== Main Output ==========
st.header("Azimuth Offset")
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    if crosswind_kmh > 0:
        st.metric("Crosswind Component", f"{crosswind_kmh:.1f} km/h",
                  help="Wind perpendicular to your facing direction")
        st.metric("Rotate Bipod UPWIND by", f"{azimuth_angle_deg:.1f}°",
                  delta=f"→ Compensates {gyro_drift:.2f} m drift", delta_color="normal")
    else:
        st.info("No crosswind component – no azimuth offset needed.")
with col2:
    st.metric("Raw Lateral Drift", f"{raw:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric("After Gyro (-35%)", f"{gyro_drift:.2f} m" if crosswind_kmh > 0 else "0 m")
    st.metric(" Net Drift", f"{net_drift_val:.2f} m", 
              delta="Cancelled" if net_drift_val < 0.1 else "⚠️ Residual")
with col3:
    st.metric("Apex Height", f"{apex:.2f} m", 
              delta="PASS" if apex >= load_height + 0.4 else "FAIL")
    st.metric("Horizontal Range", f"{range_m:.1f} m",
              delta="PASS" if range_m >= 2.4 else "FAIL")

if crosswind_kmh > 0:
    st.success(f"**Instruction:** Rotate the bipod **{azimuth_angle_deg:.1f} degrees upwind** before launching.")
else:
    st.success("Aim straight across the trailer (no crosswind).")

# ========== Mission Simulation ==========
st.divider()
st.subheader("Full Load Mission Check (optional)")
num_straps = st.slider("Number of straps", 6, 13, 10)
if st.button("Run Mission Check"):
    cylinder = 60.0
    drop_per_shot = (60 - 35) / 12
    swaps = 0
    rows = []
    progress = st.progress(0)
    status = st.empty()
    for i in range(1, num_straps + 1):
        reg = pressure_psi if cylinder >= pressure_psi else cylinder
        if reg < 46:
            status.warning(f"Strap {i}: low pressure ({reg:.0f} PSI). Swapping cylinder...")
            time.sleep(0.3)
            cylinder = 60.0
            reg = pressure_psi
            swaps += 1
            status.info("Cylinder swapped.")
            time.sleep(0.3)
        v = muzzle_velocity(reg, kv)
        if rain:
            v *= 0.98
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
            "Net Drift (m)": f"{d:.2f}",
            "Success": "✅" if success else "❌"
        })
        progress.progress(i / num_straps)
        status.info(f"Strap {i}/{num_straps}: apex {a:.2f} m – {'✅' if success else '❌'}")
        time.sleep(0.15)
        if i < num_straps:
            cylinder = max(35, cylinder - drop_per_shot)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.success(f"**Completed {df[df['Success']=='✅'].shape[0]}/{num_straps} straps.** Cylinder swaps: {swaps}")

st.caption("Data sources: Open‑Meteo (weather), ip-api.com (location). Compass uses DeviceOrientationEvent.")