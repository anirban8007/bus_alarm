import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import json
import math
import requests

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Train Track Detector",
    page_icon="🚂",
    layout="wide"
)

SEARCH_RADIUS_M = 400
API_KEY = "AIzaSyC4Z68k-NGy2PT1pUwBrncSZGdYW7uliMY"
REFRESH_INTERVAL_MS = 5000  # refresh every 5 seconds

# ── Auto Refresh only after destination is set ────────────────
if st.session_state.dest_lat is not None:
    st_autorefresh(interval=REFRESH_INTERVAL_MS)

# ── Haversine Distance (meters) ───────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ── Load GeoJSON Once ─────────────────────────────────────────
@st.cache_data
def load_railways():
    with open("india_railways.geojson", "r") as f:
        data = json.load(f)
    return data["features"]

# ── Check Within 400m ─────────────────────────────────────────
def check_railway_nearby(lat, lng, features, radius=SEARCH_RADIUS_M):
    lat_margin = 0.004
    lng_margin = 0.005
    nearby = []

    for feature in features:
        geom = feature["geometry"]
        props = feature["properties"]
        railway_type = props.get("railway", "unknown")

        if geom["type"] == "Point":
            plon, plat = geom["coordinates"]
            if abs(plat - lat) > lat_margin or abs(plon - lng) > lng_margin:
                continue
            dist = haversine(lat, lng, plat, plon)
            if dist <= radius:
                nearby.append({
                    "type": railway_type,
                    "geometry": "Point",
                    "distance": round(dist),
                })

        elif geom["type"] == "LineString":
            coords = geom["coordinates"]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            if (min(lats) > lat + lat_margin or max(lats) < lat - lat_margin or
                min(lons) > lng + lng_margin or max(lons) < lng - lng_margin):
                continue
            min_dist = float("inf")
            for coord in coords:
                plon, plat = coord
                dist = haversine(lat, lng, plat, plon)
                if dist < min_dist:
                    min_dist = dist
            if min_dist <= radius:
                nearby.append({
                    "type": railway_type,
                    "geometry": "LineString",
                    "distance": round(min_dist),
                })

    return nearby

# ── Geocode Place Name → Lat/Lng (Nominatim) ──────────────────
@st.cache_data
def geocode_place(place_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_name + ", India",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "TrainTrackDetector/1.0"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]
    except:
        pass
    return None, None, None

# ── Get Route Distance + Time (OSRM) ─────────────────────────
def get_route_info(orig_lat, orig_lng, dest_lat, dest_lng):
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{orig_lng},{orig_lat};{dest_lng},{dest_lat}"
        f"?overview=false"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data["code"] == "Ok":
            route = data["routes"][0]
            distance_km = round(route["distance"] / 1000, 1)
            duration_min = round(route["duration"] / 60)
            if duration_min >= 60:
                hours = duration_min // 60
                mins = duration_min % 60
                time_str = f"{hours}h {mins}min"
            else:
                time_str = f"{duration_min} min"
            return distance_km, time_str
    except:
        pass
    return None, None

# ── Session State for Destination ─────────────────────────────
# Keeps destination saved across refreshes
if "destination" not in st.session_state:
    st.session_state.destination = ""
if "dest_lat" not in st.session_state:
    st.session_state.dest_lat = None
if "dest_lng" not in st.session_state:
    st.session_state.dest_lng = None
if "dest_name" not in st.session_state:
    st.session_state.dest_name = ""

# ── UI ────────────────────────────────────────────────────────
st.title("🚂 Train Track Detector")

# ── Get GPS Location ──────────────────────────────────────────
with st.spinner("📡 Detecting your location..."):
    location = get_geolocation()

if not location:
    st.info("📡 Waiting for location access... Please allow location when browser asks.")
    st.stop()

try:
    lat = float(location["coords"]["latitude"])
    lng = float(location["coords"]["longitude"])
    accuracy = round(location["coords"]["accuracy"])
except (KeyError, TypeError, ValueError):
    st.error("❌ Could not read location. Please refresh and allow location access.")
    st.stop()

# ── Accuracy Warning ──────────────────────────────────────────
if accuracy > 500:
    st.warning(f"⚠️ Low GPS accuracy ({accuracy}m) — results may be inaccurate on desktop")
else:
    st.success(f"📍 Location detected → Lat: {lat}, Lng: {lng} | Accuracy: {accuracy}m")

# ── Run Railway Detection ─────────────────────────────────────
features = load_railways()
nearby = check_railway_nearby(lat, lng, features)

# ── Case 1: Train Tracks Found ────────────────────────────────
if nearby:
    col_map, col_result = st.columns([2, 1])

    with col_map:
        st.subheader("🗺️ Map View")
        map_url = (
            f"https://www.google.com/maps/embed/v1/place"
            f"?key={API_KEY}&q={lat},{lng}&zoom=18"
        )
        components.html(
            f"""
            <iframe
                width="100%"
                height="550"
                style="border:0; border-radius:12px;"
                loading="lazy"
                allowfullscreen
                src="{map_url}">
            </iframe>
            """,
            height=570
        )

    with col_result:
        st.subheader("🔎 Detection Result")
        st.success("✅ YES — Train infrastructure found within 400m!")
        st.markdown(f"**Total matches: {len(nearby)}**")
        st.divider()

        tracks = [n for n in nearby if n["geometry"] == "LineString"]
        stations = [n for n in nearby if n["geometry"] == "Point"]

        if tracks:
            st.markdown(f"**🛤️ Railway Lines: {len(tracks)}**")
            for t in tracks[:5]:
                st.write(f"- {t['type']} → {t['distance']}m away")

        if stations:
            st.markdown(f"**🚉 Stations/Stops: {len(stations)}**")
            for s in stations[:5]:
                st.write(f"- {s['type']} → {s['distance']}m away")

        closest = min(nearby, key=lambda x: x["distance"])
        st.divider()
        st.metric("Closest Railway", f"{closest['distance']}m",
                  f"Type: {closest['type']}")

# ── Case 2: No Train Tracks → Navigation Mode ─────────────────
else:
    st.error("❌ NO — No train tracks within 400m")
    st.divider()
    st.subheader("🗺️ Navigate to Destination")

    # Destination input — persists across refreshes
    destination_input = st.text_input(
        "📍 Enter your destination",
        value=st.session_state.destination,
        placeholder="e.g. Howrah Station, Kolkata"
    )

    # If destination changed → geocode it
    if destination_input and destination_input != st.session_state.destination:
        st.session_state.destination = destination_input
        with st.spinner(f"Searching for {destination_input}..."):
            d_lat, d_lng, d_name = geocode_place(destination_input)
        if d_lat:
            st.session_state.dest_lat = d_lat
            st.session_state.dest_lng = d_lng
            st.session_state.dest_name = d_name
        else:
            st.error("❌ Destination not found. Try a more specific name.")

    # If destination is set → show route
    if st.session_state.dest_lat:
        dest_lat = st.session_state.dest_lat
        dest_lng = st.session_state.dest_lng
        dest_name = st.session_state.dest_name

        col_map, col_info = st.columns([2, 1])

        with col_map:
            st.subheader("🗺️ Route Map")
            map_url = (
                f"https://www.google.com/maps/embed/v1/directions"
                f"?key={API_KEY}"
                f"&origin={lat},{lng}"
                f"&destination={dest_lat},{dest_lng}"
                f"&mode=driving"
            )
            components.html(
                f"""
                <iframe
                    width="100%"
                    height="550"
                    style="border:0; border-radius:12px;"
                    loading="lazy"
                    allowfullscreen
                    src="{map_url}">
                </iframe>
                """,
                height=570
            )

        with col_info:
            st.subheader("📊 Live Route Info")
            st.caption("Updates every 5 seconds as you move")

            # Recalculate route on every refresh
            distance_km, travel_time = get_route_info(
                lat, lng, dest_lat, dest_lng
            )

            if distance_km and travel_time:
                st.metric("📏 Distance Remaining", f"{distance_km} km")
                st.metric("⏱️ Approx Time", travel_time)
            else:
                straight_dist = round(
                    haversine(lat, lng, dest_lat, dest_lng) / 1000, 1
                )
                st.metric("📏 Straight Distance", f"{straight_dist} km")

            st.divider()
            st.markdown(f"**📍 Your Location:**")
            st.write(f"Lat: {lat}, Lng: {lng}")
            st.markdown(f"**🏁 Destination:**")
            st.write(dest_name)