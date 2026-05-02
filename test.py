import streamlit as st
import pandas as pd
import numpy as np
import requests
import time

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
        st.session_state.user_lat = lat
        st.session_state.user_lon = lon
        # Clear params to avoid re-processing on next run
        st.query_params.clear()
        # Fetch weather for these coordinates
        with st.spinner("Fetching live wind data for your location..."):
            speed, direction = get_weather(lat, lon)
            if speed is not None:
                st.session_state.wind_speed = speed
                st.session_state.wind_dir = direction
                st.session_state.location_fetched = True
                st.success(f"✅ Location detected! Wind: {speed} km/h from {direction}°")
            else:
                st.warning("Weather data not available for these coordinates.")
                st.session_state.location_fetched = False
    except Exception as e:
        st.error(f"Error processing coordinates: {e}")

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

# Hidden input that JS will write coordinates into
coords_raw = st.sidebar.text_input(
    "GPS Coordinates (auto-filled)",
    key="gps_coords",
    label_visibility="collapsed",
    placeholder="waiting for GPS…",
)

# Process coordinates if JS has written them
if coords_raw and "," in coords_raw:
    try:
        lat_str, lon_str = coords_raw.strip().split(",", 1)
        lat, lon = float(lat_str), float(lon_str)
        if st.session_state.user_lat != lat or st.session_state.user_lon != lon:
            st.session_state.user_lat = lat
            st.session_state.user_lon = lon
            with st.spinner("Fetching live wind data…"):
                speed, direction = get_weather(lat, lon)
            if speed is not None:
                st.session_state.wind_speed = speed
                st.session_state.wind_dir = direction
                st.session_state.location_fetched = True
                st.sidebar.success(f"✅ Wind: {speed} km/h from {direction}°")
            else:
                st.sidebar.warning("Weather data unavailable for these coordinates.")
    except Exception as e:
        st.sidebar.error(f"Could not parse coordinates: {e}")

# Geolocation button — JS fills the hidden input directly (no page reload)
geo_html = """
<div id="geo-status" style="margin-bottom:8px;font-size:0.85rem;font-weight:500;color:#ccc;min-height:20px;"></div>
<button id="geo-btn"
  style="padding:10px 20px;background:#0066cc;color:white;border:none;border-radius:4px;cursor:pointer;width:100%;font-size:0.9rem;">
  📍 Use My Current Location (GPS)
</button>
<script>
(function() {
  const btn    = document.getElementById('geo-btn');
  const status = document.getElementById('geo-status');

  function setStreamlitInput(value) {
    // Walk up to the Streamlit parent document and find our hidden input
    const doc = window.parent.document;
    // The input rendered by st.text_input with key="gps_coords"
    const inputs = doc.querySelectorAll('input[type="text"]');
    let target = null;
    for (const inp of inputs) {
      if (inp.placeholder === 'waiting for GPS…') { target = inp; break; }
    }
    if (!target) {
      status.innerHTML = '❌ Could not find coordinate input. Please refresh and try again.';
      return;
    }
    // Set value and fire React synthetic events so Streamlit picks up the change
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(target, value);
    target.dispatchEvent(new Event('input',  { bubbles: true }));
    target.dispatchEvent(new Event('change', { bubbles: true }));
    status.innerHTML = '✅ Coordinates sent. Fetching weather…';
  }

  btn.onclick = function() {
    if (!navigator.geolocation) {
      status.innerHTML = '❌ Geolocation not supported by this browser.';
      return;
    }
    btn.disabled = true;
    status.innerHTML = '⏳ Requesting GPS permission…';
    navigator.geolocation.getCurrentPosition(
      function(pos) {
        const lat = pos.coords.latitude.toFixed(6);
        const lon = pos.coords.longitude.toFixed(6);
        status.innerHTML = `📍 Got location: ${lat}, ${lon}`;
        setStreamlitInput(lat + ',' + lon);
        btn.disabled = false;
      },
      function(err) {
        const msgs = {
          1: 'Permission denied — allow location in browser settings.',
          2: 'Position unavailable — move outdoors or enable GPS.',
          3: 'Request timed out — try again.',
        };
        status.innerHTML = '❌ ' + (msgs[err.code] || err.message);
        btn.disabled = false;
      },
      { timeout: 12000, enableHighAccuracy: true }
    );
  };
})();
</script>
"""
with st.sidebar:
    st.components.v1.html(geo_html, height=140)
    st.caption("📱 Click the button, allow GPS. No page reload needed.")

# Show current location status
if st.session_state.user_lat:
    st.sidebar.success(f"📍 {st.session_state.user_lat:.4f}, {st.session_state.user_lon:.4f}")
else:
    st.sidebar.info("No location yet. Click the button above.")

# Manual coordinates entry (fallback)
st.sidebar.markdown("---")
st.sidebar.subheader("✍️ Manual Coordinates (Fallback)")
manual_lat = st.sidebar.number_input("Latitude", -90.0, 90.0, -27.4679, step=0.01, format="%.4f")
manual_lon = st.sidebar.number_input("Longitude", -180.0, 180.0, 153.0281, step=0.01, format="%.4f")
if st.sidebar.button("Set Manual Location & Fetch Weather"):
    with st.spinner("Fetching weather for manual coordinates..."):
        speed, direction = get_weather(manual_lat, manual_lon)
        if speed is not None:
            st.session_state.wind_speed = speed
            st.session_state.wind_dir = direction
            st.session_state.user_lat = manual_lat
            st.session_state.user_lon = manual_lon
            st.session_state.location_fetched = True
            st.sidebar.success(f"Manually set wind: {speed} km/h from {direction}°")
        else:
            st.sidebar.error("Could not fetch weather for these coordinates.")

# Manual wind/heading override (always works)
st.sidebar.markdown("---")
st.sidebar.subheader("🌬️ Manual Wind Override (for testing)")
use_manual = st.sidebar.checkbox("Override wind/heading values", value=False)
if use_manual:
    manual_speed = st.sidebar.number_input("Wind speed (km/h)", 0, 100, st.session_state.wind_speed)
    manual_dir = st.sidebar.number_input("Wind direction (deg)", 0, 360, st.session_state.wind_dir)
    manual_heading = st.sidebar.number_input("Your heading (deg, 0=N)", 0, 360, st.session_state.user_heading)
    st.session_state.wind_speed = manual_speed
    st.session_state.wind_dir = manual_dir
    st.session_state.user_heading = manual_heading
    st.sidebar.info("Using manual values (override active).")

# Display current wind and heading (where they come from)
st.sidebar.markdown("---")
st.sidebar.metric("🌬️ Current wind", f"{st.session_state.wind_speed} km/h from {st.session_state.wind_dir}°",
                  help="From GPS+weather or manual override")
st.sidebar.metric("🧭 Your heading", f"{st.session_state.user_heading}° (0=N)",
                  help="Enter below or use manual override")

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
st.header("🎯 Azimuth Offset (Primary Result)")
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

st.caption("📍 **How it works:** Click 'Use My Current Location' – your browser asks permission – page reloads with your actual GPS coordinates (works on phone or laptop). Then weather is fetched live. If geolocation still fails, use the **Manual Coordinates** or **Manual Wind Override** sections – they always work.")