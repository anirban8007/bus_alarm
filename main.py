import streamlit as st
import streamlit.components.v1 as components
import json
import math

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Train Track Detector",
    page_icon="🚂",
    layout="wide"
)

SEARCH_RADIUS_M = 400
API_KEY = "AIzaSyC4Z68k-NGy2PT1pUwBrncSZGdYW7uliMY"

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

# ── UI ────────────────────────────────────────────────────────
st.title("🚂 Train Track Detector")
st.write("Checks for train tracks within 400m of entered coordinates")

col1, col2 = st.columns(2)

with col1:
    lat = st.number_input("📍 Latitude",
                          value=22.5726,
                          format="%.6f",
                          min_value=-90.0,
                          max_value=90.0)
with col2:
    lng = st.number_input("📍 Longitude",
                          value=88.3639,
                          format="%.6f",
                          min_value=-180.0,
                          max_value=180.0)

detect = st.button("🔍 Detect Train Tracks")

if detect:
    if lat == 0.0 and lng == 0.0:
        st.warning("⚠️ Please enter valid coordinates!")
    else:
        col_map, col_result = st.columns([2, 1])

        with col_map:
            st.subheader("🗺️ Map View")
            map_url = f"https://www.google.com/maps/embed/v1/place?key={API_KEY}&q={lat},{lng}&zoom=18"
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

            with st.spinner("Checking 400m radius..."):
                features = load_railways()
                nearby = check_railway_nearby(lat, lng, features)

            if nearby:
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
                st.metric("Closest Railway", f"{closest['distance']}m", f"Type: {closest['type']}")

            else:
                st.error("❌ NO — No train tracks within 400m")