import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import math

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Train Track Detector",
    page_icon="🚂",
    layout="wide"
)

SEARCH_RADIUS_M = 400

# ── Haversine Distance (meters) ───────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
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
    # Approximate bounding box filter first (fast)
    # 400m ≈ 0.0036 degrees latitude, ~0.004 degrees longitude
    lat_margin = 0.004
    lng_margin = 0.005

    nearby = []

    for feature in features:
        geom = feature["geometry"]
        props = feature["properties"]
        railway_type = props.get("railway", "unknown")

        if geom["type"] == "Point":
            plon, plat = geom["coordinates"]

            # Bounding box pre-filter
            if abs(plat - lat) > lat_margin or abs(plon - lng) > lng_margin:
                continue

            dist = haversine(lat, lng, plat, plon)
            if dist <= radius:
                nearby.append({
                    "type": railway_type,
                    "geometry": "Point",
                    "distance": round(dist),
                    "coords": [(plat, plon)]
                })

        elif geom["type"] == "LineString":
            coords = geom["coordinates"]

            # Bounding box pre-filter using line bounds
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            if (min(lats) > lat + lat_margin or max(lats) < lat - lat_margin or
                min(lons) > lng + lng_margin or max(lons) < lng - lng_margin):
                continue

            # Check each point of the line
            min_dist = float("inf")
            closest_coord = None
            for coord in coords:
                plon, plat = coord
                dist = haversine(lat, lng, plat, plon)
                if dist < min_dist:
                    min_dist = dist
                    closest_coord = (plat, plon)

            if min_dist <= radius:
                nearby.append({
                    "type": railway_type,
                    "geometry": "LineString",
                    "distance": round(min_dist),
                    "coords": [(c[1], c[0]) for c in coords]
                })

    return nearby

# ── UI ────────────────────────────────────────────────────────
st.title("🚂 Train Track Detector")
st.write("Checks for train tracks within 400m of entered coordinates — works fully offline")

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
            m = folium.Map(location=[lat, lng], zoom_start=16)

            # Center marker
            folium.Marker(
                [lat, lng],
                popup=f"Lat: {lat}, Lng: {lng}",
                icon=folium.Icon(color="red", icon="train", prefix="fa")
            ).add_to(m)

            # 400m radius circle
            folium.Circle(
                location=[lat, lng],
                radius=SEARCH_RADIUS_M,
                color="blue",
                fill=True,
                fill_opacity=0.1,
                popup="400m search radius"
            ).add_to(m)

            st_folium(m, width=700, height=500, returned_objects=[])

        with col_result:
            st.subheader("🔎 Detection Result")

            with st.spinner("Loading railway data and checking 400m radius..."):
                features = load_railways()
                nearby = check_railway_nearby(lat, lng, features)

            if nearby:
                st.success(f"✅ YES — Train infrastructure found within 400m!")
                st.markdown(f"**Total matches: {len(nearby)}**")
                st.divider()

                # Show breakdown
                tracks = [n for n in nearby if n["geometry"] == "LineString"]
                stations = [n for n in nearby if n["geometry"] == "Point"]

                if tracks:
                    st.markdown(f"**🛤️ Railway Lines: {len(tracks)}**")
                    for t in tracks[:5]:  # show max 5
                        st.write(f"- {t['type']} → {t['distance']}m away")

                if stations:
                    st.markdown(f"**🚉 Stations/Stops: {len(stations)}**")
                    for s in stations[:5]:  # show max 5
                        st.write(f"- {s['type']} → {s['distance']}m away")

                # Closest item
                closest = min(nearby, key=lambda x: x["distance"])
                st.divider()
                st.metric("Closest Railway", f"{closest['distance']}m", f"Type: {closest['type']}")

            else:
                st.error("❌ NO — No train tracks within 400m")