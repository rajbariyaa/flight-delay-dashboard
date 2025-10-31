import streamlit as st
import pandas as pd
import numpy as np
import pickle
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, time, timezone
import warnings
import math
import requests
import os
from typing import Optional, Tuple, Dict

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Flight Delay Predictor",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.set_option("client.showErrorDetails", True)

st.markdown("""
    <style>
    .main { padding: 0rem 1rem; }
    .stAlert { margin-top: 1rem; }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #c9d3e0;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .risk-low { color: #28a745; font-weight: bold; }
    .risk-medium { color: #ffc107; font-weight: bold; }
    .risk-high { color: #dc3545; font-weight: bold; }
    .chip {
        display:inline-block; padding:2px 8px; border-radius:999px;
        background:#eef3ff; color:#1e40af; font-size:12px; border:1px solid #c7d2fe;
        margin-left:6px;
    }
    </style>
""", unsafe_allow_html=True)
if 'predictions_history' not in st.session_state:
    st.session_state.predictions_history = []

# ──────────────────────────────────────────────────────────────────────────────
# Distances (robust CSV loader)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data
def load_distances() -> Tuple[Optional[pd.DataFrame], Optional[dict]]:
    """
    Load distance CSV and build a symmetric lookup dict:
      lookup[('LAX','JFK')] -> miles
      lookup[('JFK','LAX')] -> miles
    Robust to column names; prefers 'distance/miles', ignores '*seq*' columns.
    """
    df = None
    for path in ("distance.csv", "/mnt/data/distance.csv"):
        try:
            df = pd.read_csv(path)
            break
        except Exception:
            continue
    if df is None:
        return None, None

    lower_to_orig = {c.lower().strip(): c for c in df.columns}
    all_lower = list(lower_to_orig.keys())

    def find_col(candidates_exact, must_contain_any=None, numeric=False, exclude_substrings=None):
        for cand in candidates_exact:
            cl = cand.lower().strip()
            if cl in lower_to_orig:
                colname = lower_to_orig[cl]
                if (not numeric) or pd.api.types.is_numeric_dtype(df[colname]):
                    return colname
        if must_contain_any:
            ranked = []
            for ll in all_lower:
                if exclude_substrings and any(bad in ll for bad in exclude_substrings):
                    continue
                if any(key in ll for key in must_contain_any):
                    colname = lower_to_orig[ll]
                    if (not numeric) or pd.api.types.is_numeric_dtype(df[colname]):
                        score = sum(key in ll for key in must_contain_any)
                        ranked.append((score, colname))
            if ranked:
                ranked.sort(reverse=True)
                return ranked[0][1]
        return None

    origin_col = find_col(
        ["origin", "origin_airport", "from", "src", "source", "origin_iata", "origin_code"],
        must_contain_any=["origin"], exclude_substrings=["seq"], numeric=False
    )
    dest_col = find_col(
        ["dest", "destination", "destination_airport", "to", "dst", "dest_iata", "destination_code"],
        must_contain_any=["dest", "destination"], exclude_substrings=["seq"], numeric=False
    )
    distance_col = find_col(
        ["distance", "distance_miles", "miles", "dist", "distance (miles)", "distance in miles"],
        must_contain_any=["distance", "miles"], exclude_substrings=["seq"], numeric=True
    )

    if not (origin_col and dest_col and distance_col):
        object_cols = [c for c in df.columns if df[c].dtype == 'object' and 'seq' not in c.lower()]
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and 'seq' not in c.lower()]
        if not origin_col and object_cols:
            origin_col = object_cols[0]
        if not dest_col and len(object_cols) >= 2:
            dest_col = object_cols[1]
        if not distance_col:
            preferred = [c for c in numeric_cols if any(k in c.lower() for k in ['distance', 'miles'])]
            distance_col = preferred[0] if preferred else (numeric_cols[0] if numeric_cols else None)

    if not (origin_col and dest_col and distance_col):
        return df, None

    df[origin_col] = df[origin_col].astype(str).str.upper().str.strip()
    df[dest_col]   = df[dest_col].astype(str).str.upper().str.strip()
    df[distance_col] = pd.to_numeric(df[distance_col], errors='coerce')

    df = df[
        df[origin_col].str.fullmatch(r"[A-Z]{3}", na=False) &
        df[dest_col].str.fullmatch(r"[A-Z]{3}", na=False)
    ].copy()
    df = df[(df[distance_col] >= 10) & (df[distance_col] <= 6000)].dropna(subset=[distance_col])

    lookup = {}
    for o, d, m in zip(df[origin_col], df[dest_col], df[distance_col]):
        miles = float(m)
        lookup[(o, d)] = miles
        lookup[(d, o)] = miles

    return df, (lookup if lookup else None)

def get_distance_from_lookup(origin: str, destination: str, lookup: Optional[dict]) -> Optional[float]:
    if not lookup:
        return None
    o = (origin or "").upper().strip()
    d = (destination or "").upper().strip()
    return lookup.get((o, d), None)

# ──────────────────────────────────────────────────────────────────────────────
# Airport coordinates (for Windy point-forecast)
# ──────────────────────────────────────────────────────────────────────────────
BUILTIN_AIRPORTS = {
    # IATA -> (lat, lon, display)
    "LAX": (33.9416, -118.4085, "KLAX / LAX"),
    "JFK": (40.6413,  -73.7781, "KJFK / JFK"),
    "SFO": (37.6213, -122.3790, "KSFO / SFO"),
    "SEA": (47.4502, -122.3088, "KSEA / SEA"),
    "BOS": (42.3656,  -71.0096, "KBOS / BOS"),
    "MIA": (25.7959,  -80.2870, "KMIA / MIA"),
    "DFW": (32.8998,  -97.0403, "KDFW / DFW"),
    "ATL": (33.6407,  -84.4277, "KATL / ATL"),
    "ORD": (41.9742,  -87.9073, "KORD / ORD"),
    "BWI": (39.1754,  -76.6684, "KBWI / BWI"),
    "LGA": (40.7769,  -73.8740, "KLGA / LGA"),
    "EWR": (40.6895,  -74.1745, "KEWR / EWR")
}

@st.cache_data
def load_airports() -> Optional[pd.DataFrame]:
    """
    Load airports.csv with columns containing at least:
    - IATA or ident/code
    - latitude, longitude (any reasonable naming)
    """
    for path in ("airports.csv", "/mnt/data/airports.csv"):
        try:
            df = pd.read_csv(path)
            return df
        except Exception:
            continue
    return None

def resolve_airport_latlon(code: str) -> Optional[Tuple[float, float, str]]:
    """
    Resolve IATA/ICAO to (lat, lon, display_name)
    Tries airports.csv, then BUILTIN_AIRPORTS, else None.
    """
    code = (code or "").upper().strip()
    # built-in first
    if code in BUILTIN_AIRPORTS:
        lat, lon, disp = BUILTIN_AIRPORTS[code]
        return float(lat), float(lon), disp

    df = load_airports()
    if df is not None:
        cols = {c.lower(): c for c in df.columns}
        # Try to find code col
        code_cols_priority = [
            "iata", "iata_code", "iata_code_new", "code", "ident", "airport_code", "iata/icao"
        ]
        lat_candidates = ["lat", "latitude", "lat_deg", "latitude_deg", "airport_latitude"]
        lon_candidates = ["lon", "lng", "longitude", "lon_deg", "longitude_deg", "airport_longitude"]

        def find_col(preferred):
            for k in preferred:
                if k in cols:
                    return cols[k]
            # keyword search fallback
            for k in cols:
                if any(p in k for p in preferred):
                    return cols[k]
            return None

        code_col = find_col(code_cols_priority)
        lat_col = find_col(lat_candidates)
        lon_col = find_col(lon_candidates)

        if code_col and lat_col and lon_col:
            hit = df[df[code_col].astype(str).str.upper().str.strip() == code]
            if not hit.empty:
                lat = float(hit.iloc[0][lat_col])
                lon = float(hit.iloc[0][lon_col])
                return lat, lon, code

    # Try stripping leading 'K' for US ICAOs to IATA (e.g., KLAX -> LAX)
    if len(code) == 4 and code.startswith("K") and code[1:] in BUILTIN_AIRPORTS:
        lat, lon, disp = BUILTIN_AIRPORTS[code[1:]]
        return float(lat), float(lon), f"{code} / {code[1:]}"
    return None


WINDY_ENDPOINT = "https://api.windy.com/api/point-forecast/v2"  # POST

def _ms_to_mph(ms: float) -> float:
    return ms * 2.2369362921

def _k_to_f(k: float) -> float:
    return (k - 273.15) * 9/5 + 32

def _pa_to_mb(pa: float) -> float:
    return pa / 100.0  # Pa -> hPa (mb)

def _m_to_in(m: float) -> float:
    return m * 39.37007874

def _pick_windy_model_for_latlon(lat: float, lon: float) -> str:
    # Rough CONUS bbox for NAM; otherwise GFS
    if 20.0 <= lat <= 55.5 and -130.5 <= lon <= -60.0:
        return "namConus"
    return "gfs"

def _nearest_index_by_ts(ts_list_ms: list, when_dt: datetime) -> int:
    # Windy ts is "local time for given coordinates" (per docs). We’ll use naive comparison to given local datetime.
    if not ts_list_ms:
        return 0
    target = int(pd.Timestamp(when_dt).value // 10**6)  # to ms
    diffs = [abs(t - target) for t in ts_list_ms]
    return int(np.argmin(diffs))

def fetch_windy_features(lat: float, lon: float, when_dt_local: datetime, api_key: str) -> Tuple[dict, str]:
    """
    Query Windy Point Forecast and convert to the feature dict your app uses.
    Returns (features_dict, source_label)
    """
    model = _pick_windy_model_for_latlon(lat, lon)
    body = {
        "lat": float(lat),
        "lon": float(lon),
        "model": model,
        "parameters": [
            "temp", "dewpoint", "rh", "pressure",
            "wind", "windGust",
            "lclouds", "mclouds", "hclouds",
            "precip", "snowPrecip", "convPrecip"
        ],
        "levels": ["surface"],
        "key": api_key
    }
    try:
        r = requests.post(WINDY_ENDPOINT, json=body, timeout=12)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        # Fallback neutral weather
        return ({
            "temperature_f": 72.0, "humidity_pct": 60.0, "pressure_mb": 1013.0,
            "wind_mph": 8.0, "cloudiness_pct": 30, "visibility_mi": 10.0,
            "precip_in": 0.0, "snow_in": 0.0, "_source": "Windy Fallback"
        }, f"Windy ({model}) Fallback")

    ts = data.get("ts", []) or []
    idx = _nearest_index_by_ts(ts, when_dt_local)

    def get1(key, default=None):
        arr = data.get(key)
        try:
            return arr[idx]
        except Exception:
            return default

    # Retrieve units to decide conversions
    units = data.get("units", {})
    # Temperature (K -> F if needed)
    temp_val = get1("temp-surface")
    temp_f = None
    if temp_val is not None:
        if units.get("temp-surface", "").lower().startswith("k"):
            temp_f = _k_to_f(float(temp_val))
        elif units.get("temp-surface", "").lower().startswith("c"):
            temp_f = float(temp_val) * 9/5 + 32
        else:
            # assume already °F
            temp_f = float(temp_val)

    # Relative humidity (%)
    rh_val = get1("rh-surface")
    humidity_pct = float(rh_val) if rh_val is not None else None

    # Pressure (Pa -> mb if needed)
    pres_val = get1("pressure-surface")
    pressure_mb = None
    if pres_val is not None:
        if units.get("pressure-surface", "").lower() in ("pa", "pascal", "pascals"):
            pressure_mb = _pa_to_mb(float(pres_val))
        elif units.get("pressure-surface", "").lower() in ("hpa", "mb"):
            pressure_mb = float(pres_val)
        else:
            pressure_mb = float(pres_val)  # assume mb

    # Wind speed from vector (m/s -> mph)
    u = get1("wind_u-surface", 0.0)
    v = get1("wind_v-surface", 0.0)
    wind_ms = math.sqrt((u or 0.0)**2 + (v or 0.0)**2)
    wind_mph = _ms_to_mph(float(wind_ms))

    # Cloudiness (%). Take the maximum of low/mid/high cover
    lc = get1("lclouds-surface", 0.0) or 0.0
    mc = get1("mclouds-surface", 0.0) or 0.0
    hc = get1("hclouds-surface", 0.0) or 0.0
    cloudiness_pct = float(max(lc, mc, hc))
    # If cloud values are in [0,1], convert to %
    if cloudiness_pct <= 1.0:
        cloudiness_pct *= 100.0

    # Precip totals (last 3h). Convert meters->inches when units are 'm'
    precip = get1("past3hprecip-surface", 0.0) or 0.0
    snow = get1("past3hsnowprecip-surface", 0.0) or 0.0
    conv = get1("past3hconvprecip-surface", 0.0) or 0.0  # not used directly but could inform risk

    def convert_precip(val, unit_key):
        unit = (units.get(unit_key) or "").lower()
        if unit in ("m", "meter", "meters"):
            return _m_to_in(float(val))
        if unit in ("mm",):
            return float(val) / 25.4
        # already inches?
        return float(val)

    precip_in = convert_precip(precip, "past3hprecip-surface")
    snow_in = convert_precip(snow, "past3hsnowprecip-surface")

    # Visibility not exposed in Point Forecast parameters; assume good vis unless precip/clouds indicate otherwise.
    # You can model a heuristic if you want; for now keep 10 mi default.
    visibility_mi = 10.0

    feat = {
        "temperature_f": round(temp_f if temp_f is not None else 72.0, 1),
        "humidity_pct": round(humidity_pct if humidity_pct is not None else 60.0, 0),
        "pressure_mb": round(pressure_mb if pressure_mb is not None else 1013.0, 1),
        "wind_mph": round(wind_mph, 1),
        "cloudiness_pct": int(round(cloudiness_pct)),
        "visibility_mi": round(visibility_mi, 1),
        "precip_in": round(float(precip_in or 0.0), 2),
        "snow_in": round(float(snow_in or 0.0), 2),
        "_source": f"Windy ({model})"
    }
    return feat, f"Windy Point Forecast ({model})"

def get_windy_weather_for_airport(code: str, when_dt_local: datetime, api_key: str) -> Tuple[dict, str, Optional[str]]:
    """
    Resolve airport -> lat/lon, fetch Windy features.
    Returns (features, source_label, station_display)
    """
    resolved = resolve_airport_latlon(code)
    if not resolved:
        # Fallback neutral weather if we cannot resolve coordinates
        return ({
            "temperature_f": 72.0, "humidity_pct": 60.0, "pressure_mb": 1013.0,
            "wind_mph": 8.0, "cloudiness_pct": 30, "visibility_mi": 10.0,
            "precip_in": 0.0, "snow_in": 0.0, "_source": "Windy Fallback"
        }, "Windy Fallback (no coords)", code)
    lat, lon, display = resolved
    feat, src = fetch_windy_features(lat, lon, when_dt_local, api_key)
    return feat, src, display

def weather_chip(ws: dict) -> str:
    return (f"Temp {ws['temperature_f']:.0f}°F • RH {ws['humidity_pct']:.0f}% • "
            f"Pres {ws['pressure_mb']:.0f} mb • Wind {ws['wind_mph']:.0f} mph • "
            f"Vis {ws['visibility_mi']:.1f} mi • Clouds {ws['cloudiness_pct']:.0f}% • "
            f"Rain {ws['precip_in']:.2f} in • Snow {ws['snow_in']:.2f} in")

def weather_icon(ws: dict) -> str:
    return ("⛈️" if ws['wind_mph'] > 20 or ws['precip_in'] > 0.5
            else "🌧️" if ws['precip_in'] > 0
            else "☁️" if ws['cloudiness_pct'] > 50
            else "☀️")


@st.cache_resource
def load_models():
    try:
        with open('flight_delay_models_complete.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def prepare_features(flight_data: pd.DataFrame, preprocessors: dict) -> pd.DataFrame:
    df = flight_data.copy()
    df['HOUR'] = df['SCHEDULED_DEPARTURE'] // 100
    df['MINUTE'] = df['SCHEDULED_DEPARTURE'] % 100
    df['DATE'] = pd.to_datetime(df[['YEAR', 'MONTH', 'DAY']], errors='coerce')
    df['DAY_OF_WEEK'] = df['DATE'].dt.dayofweek.fillna(0).astype(int)
    df['IS_WEEKEND'] = df['DAY_OF_WEEK'].isin([5, 6]).astype(int)
    df['ROUTE'] = df['ORIGIN_AIRPORT'].astype(str) + '_' + df['DESTINATION_AIRPORT'].astype(str)

    df['ROUTE_AVG_DELAY'] = df['ROUTE'].map(preprocessors.get('route_delay_avg', {})).fillna(0)
    df['AIRLINE_AVG_DELAY'] = df['AIRLINE'].map(preprocessors.get('airline_delay_avg', {})).fillna(0)
    df['ORIGIN_AVG_DELAY'] = df['ORIGIN_AIRPORT'].map(preprocessors.get('origin_delay_avg', {})).fillna(0)
    df['HOUR_AVG_DELAY']   = df['HOUR'].map(preprocessors.get('hour_delay_avg', {})).fillna(0)

    df['BAD_WEATHER'] = (
        (df['dest_wind_speed'] > 15) |
        (df['dest_precipitation'] > 0.1) |
        (df['dest_visibility'] < 5)
    ).astype(int)

    numerical_features = [
        'MONTH', 'DAY', 'HOUR', 'MINUTE', 'DAY_OF_WEEK', 'IS_WEEKEND',
        'DISTANCE', 'BAD_WEATHER',
        'ROUTE_AVG_DELAY', 'AIRLINE_AVG_DELAY', 'ORIGIN_AVG_DELAY', 'HOUR_AVG_DELAY',
        'dest_temperature', 'dest_humidity', 'dest_pressure',
        'dest_wind_speed', 'dest_cloudiness', 'dest_visibility',
        'dest_precipitation', 'dest_snow'
    ]
    categorical_features = ['AIRLINE', 'ORIGIN_AIRPORT', 'DESTINATION_AIRPORT']

    feature_medians = preprocessors.get('feature_medians', {})
    for col in numerical_features:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = df[col].fillna(feature_medians.get(col, 0))

    feature_modes = preprocessors.get('feature_modes', {})
    label_encoders = preprocessors.get('label_encoders', {})
    for col in categorical_features:
        if col in label_encoders:
            le = label_encoders[col]
            known = set(le.classes_.tolist())
            fallback = feature_modes.get(col, list(le.classes_)[0])
            df[col] = df[col].astype(str).apply(lambda x: x if x in known else fallback)
            if fallback not in known:
                le.classes_ = np.append(le.classes_, fallback)
            df[col + '_encoded'] = le.transform(df[col])
        else:
            df[col + '_encoded'] = 0

    expected = preprocessors.get('feature_names', None)
    if expected is None:
        expected = numerical_features + [c + '_encoded' for c in categorical_features]

    for col in expected:
        if col not in df.columns:
            df[col] = 0

    return df[expected]

def make_prediction(flight_data: pd.DataFrame, models: dict) -> dict:
    X = prepare_features(flight_data, models['preprocessors'])
    dep_prob = float(models['departure']['classifier'].predict_proba(X)[:, 1][0])
    dep_amount = float(models['departure']['regressor'].predict(X)[0])
    dep_pred = dep_amount if dep_prob > 0.2 else 0.0

    arr_prob = float(models['arrival']['classifier'].predict_proba(X)[:, 1][0])
    arr_amount = float(models['arrival']['regressor'].predict(X)[0])
    arr_pred = arr_amount if arr_prob > 0.2 else 0.0

    return {
        'departure_delay': dep_pred,
        'departure_probability': dep_prob,
        'arrival_delay': arr_pred,
        'arrival_probability': arr_prob
    }

def get_risk_level(probability_percent: float):
    if probability_percent < 30:
        return "Low", "risk-low"
    elif probability_percent < 60:
        return "Medium", "risk-medium"
    else:
        return "High", "risk-high"

def create_gauge_chart(value_percent: float, title: str, max_value: int = 100):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value_percent,
        title={'text': title},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [None, max_value]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 30], 'color': "lightgreen"},
                {'range': [30, 60], 'color': "yellow"},
                {'range': [60, 100], 'color': "lightcoral"}
            ],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': value_percent}
        }
    ))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    return fig

def load_windy_key() -> str | None:
    # 1) Prefer environment variable (won’t crash if secrets missing)
    key = os.getenv("WINDY_API_KEY")
    if key:
        return key
    try:
        return st.secrets["WINDY_API_KEY"]
    except Exception:
        return None

# ──────────────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────────────
def main():
    st.title("Flight Delay Prediction System")
    st.markdown("Predict delays using ML + **Windy Point Forecast** (origin & destination)")

    # WINDY_API_KEY = load_windy_key()
    WINDY_API_KEY = "JZ6gjRWNQj0HJn4PoVljkpfcIcFTYlNj"
    if not WINDY_API_KEY:
        st.error(
        "Missing Windy API key. Set env var `WINDY_API_KEY` **or** create `.streamlit/secrets.toml` with WINDY_API_KEY.")
        st.stop()

    models = load_models()
    if models is None:
        st.error("Model file 'flight_delay_models_complete.pkl' not found in the app directory.")
        st.info("Run the training script first to generate the model file: `python extract_models_to_pkl.py`")
        return

    distances_df, distances_lookup = load_distances()
    distances_loaded = distances_lookup is not None

    with st.sidebar:
        st.header("Flight Information")
        DEBUG_MODE = st.checkbox("Show debug errors", value=False)

        col1, col2 = st.columns(2)
        with col1:
            airline = st.selectbox(
                "Airline",
                options=['AA', 'DL', 'UA', 'WN', 'B6', 'AS', 'NK', 'F9', 'VX', 'HA', 'OO', 'EV', 'MQ', 'US']
            )
        with col2:
            origin = st.text_input("Origin (IATA/ICAO)", value="LAX", max_chars=4).upper().strip()

        col3, col4 = st.columns(2)
        with col3:
            destination = st.text_input("Destination (IATA/ICAO)", value="JFK", max_chars=4).upper().strip()
        with col4:
            # now this field is for an alternate code to resolve coordinates if needed
            origin_station_override = st.text_input("Origin alt code (optional)", value="").upper().strip()

        station_override_dest = st.text_input("Destination alt code (optional)", value="").upper().strip()

        # Auto distance
        auto_distance = get_distance_from_lookup(origin, destination, distances_lookup) if distances_loaded else None
        can_autofill = auto_distance is not None
        use_auto = st.toggle("Use auto distance from file", value=bool(can_autofill))
        if use_auto and can_autofill:
            st.metric("Auto Distance (miles)", f"{auto_distance:.0f}")
            distance = float(auto_distance)
        else:
            distance = st.number_input("Distance (miles)", min_value=50, max_value=5000,
                                       value=int(auto_distance) if isinstance(auto_distance, (int, float)) else 1000)

        # Schedule
        st.subheader("Schedule")
        flight_date = st.date_input("Flight Date", value=datetime.now().date())
        
        c1, c2 = st.columns(2)
        with c1:
            departure_time = st.time_input("Departure Time", value=time(14, 30))
        with c2:
            arrival_time = st.time_input("Arrival Time", value=time(17, 30))

        predict_button = st.button("Predict Delays", type="primary", use_container_width=True)

        with st.expander("Files status", expanded=False):
            if distances_loaded:
                st.success("Loaded distance.csv")
                st.write(f"Routes available: ~{len(distances_lookup)//2} (direction-agnostic)")
            else:
                st.info("distance.csv not loaded or columns not detected. Using manual distance input.")
            if load_airports() is not None:
                st.success("Loaded airports.csv for coordinates")
            else:
                st.info("airports.csv not found. Using built-in coordinates for common airports.")

    if predict_button:
        # Resolve display codes (if user provides overrides, use those)
        origin_code = origin_station_override or origin
        dest_code = station_override_dest or destination

        # Fetch Windy weather for BOTH origin (at departure time) and destination (at arrival time)
        try:
            wx_origin, src_origin, stn_origin = get_windy_weather_for_airport(
                origin_code, datetime.combine(flight_date, departure_time), WINDY_API_KEY
            )
        except Exception as e:
            if DEBUG_MODE:
                st.error("Failed to fetch/parse Windy data for origin.")
                st.exception(e)
            wx_origin, src_origin, stn_origin = ({
                "temperature_f": 72.0, "humidity_pct": 60.0, "pressure_mb": 1013.0,
                "wind_mph": 8.0, "cloudiness_pct": 30, "visibility_mi": 10.0,
                "precip_in": 0.0, "snow_in": 0.0, "_source": "Windy Fallback"
            }, "Windy Fallback", origin_code)

        try:
            wx_dest, src_dest, stn_dest = get_windy_weather_for_airport(
                dest_code, datetime.combine(flight_date, arrival_time), WINDY_API_KEY
            )
        except Exception as e:
            if DEBUG_MODE:
                st.error("Failed to fetch/parse Windy data for destination.")
                st.exception(e)
            wx_dest, src_dest, stn_dest = ({
                "temperature_f": 72.0, "humidity_pct": 60.0, "pressure_mb": 1013.0,
                "wind_mph": 8.0, "cloudiness_pct": 30, "visibility_mi": 10.0,
                "precip_in": 0.0, "snow_in": 0.0, "_source": "Windy Fallback"
            }, "Windy Fallback", dest_code)

        # Build model input — NOTE: model expects DEST_* features
        scheduled_time = departure_time.hour * 100 + departure_time.minute
        flight_data = pd.DataFrame({
            'YEAR': [flight_date.year],
            'MONTH': [flight_date.month],
            'DAY': [flight_date.day],
            'SCHEDULED_DEPARTURE': [scheduled_time],
            'AIRLINE': [airline],
            'ORIGIN_AIRPORT': [origin],
            'DESTINATION_AIRPORT': [destination],
            'DISTANCE': [float(distance)],
            'DEPARTURE_DELAY': [0],  # compatibility
            'dest_temperature': [wx_dest['temperature_f']],
            'dest_humidity': [wx_dest['humidity_pct']],
            'dest_pressure': [wx_dest['pressure_mb']],
            'dest_wind_speed': [wx_dest['wind_mph']],
            'dest_cloudiness': [wx_dest['cloudiness_pct']],
            'dest_visibility': [wx_dest['visibility_mi']],
            'dest_precipitation': [wx_dest['precip_in']],
            'dest_snow': [wx_dest['snow_in']]
        })

        with st.spinner('Analyzing flight data…'):
            try:
                result = make_prediction(flight_data, models)

                st.session_state.predictions_history.append({
                    'timestamp': datetime.now(),
                    'flight': f"{airline} {origin}->{destination}",
                    'date': flight_date,
                    'departure_time': departure_time,
                    'arrival_time': arrival_time,
                    **result
                })

                st.success("Prediction Complete!")

                # Flight summary — Windy weather cards
                st.markdown("### Flight Summary")
                top1, top2, top3 = st.columns([2, 2, 1])
                with top1:
                    st.metric("Flight", f"{airline} {origin}→{destination}")
                    st.metric("Date", flight_date.strftime("%b %d, %Y"))
                    c_dep, c_arr = st.columns(2)
                    with c_dep:
                        st.metric("Departure", departure_time.strftime("%I:%M %p"))
                    with c_arr:
                        st.metric("Arrival", arrival_time.strftime("%I:%M %p"))
                with top2:
                    cA, cB = st.columns(2)
                    with cA:
                        st.markdown("**Origin Weather (Windy)**")
                        st.metric(f"{stn_origin or 'Origin'}", weather_icon(wx_origin), help=src_origin)
                        st.caption(weather_chip(wx_origin))
                    with cB:
                        st.markdown("**Destination Weather (Windy)**")
                        st.metric(f"{stn_dest or 'Destination'}", weather_icon(wx_dest), help=src_dest)
                        st.caption(weather_chip(wx_dest))
                with top3:
                    st.metric("Distance", f"{distance:.0f} mi")

                # Predictions
                st.markdown("### Delay Predictions")
                cL, cR = st.columns(2)
                with cL:
                    st.markdown("**Departure Delay**")
                    dep_pct = result['departure_probability'] * 100.0
                    dep_risk, dep_class = get_risk_level(dep_pct)
                    s11, s12 = st.columns(2)
                    with s11:
                        st.metric("Predicted Delay",
                                  f"{result['departure_delay']:.0f} min" if result['departure_delay'] > 0 else "On Time",
                                  delta=(f"{result['departure_delay']:.0f} min late"
                                         if result['departure_delay'] > 15 else None),
                                  delta_color="inverse" if result['departure_delay'] > 15 else "off")
                    with s12:
                        st.markdown(f"**Risk Level:** <span class='{dep_class}'>{dep_risk}</span>", unsafe_allow_html=True)
                    st.plotly_chart(create_gauge_chart(dep_pct, "Delay Probability (%)"), use_container_width=True)

                with cR:
                    st.markdown("**Arrival Delay**")
                    arr_pct = result['arrival_probability'] * 100.0
                    arr_risk, arr_class = get_risk_level(arr_pct)
                    s21, s22 = st.columns(2)
                    with s21:
                        st.metric("Predicted Delay",
                                  f"{result['arrival_delay']:.0f} min" if result['arrival_delay'] > 0 else "On Time",
                                  delta=(f"{result['arrival_delay']:.0f} min late"
                                         if result['arrival_delay'] > 15 else None),
                                  delta_color="inverse" if result['arrival_delay'] > 15 else "off")
                    with s22:
                        st.markdown(f"**Risk Level:** <span class='{arr_class}'>{arr_risk}</span>", unsafe_allow_html=True)
                    st.plotly_chart(create_gauge_chart(arr_pct, "Delay Probability (%)"), use_container_width=True)

                # Recommendations
                st.markdown("### Recommendations")
                if result['departure_delay'] > 15 or result['arrival_delay'] > 15:
                    st.warning("Significant delays expected. Consider the following:")
                    recs = []
                    if result['departure_delay'] > 30:
                        recs.append("• Arrive at the origin airport later to avoid long wait times.")
                    if result['departure_delay'] > 15:
                        recs.append("• Check with the airline for possible rebooking options.")
                    if result['arrival_delay'] > 30:
                        recs.append("• Notify ground transportation about potential late arrival.")
                        recs.append("• Consider rebooking connecting flights if applicable.")
                    if wx_origin['wind_mph'] > 20 or wx_origin['precip_in'] > 0.5:
                        recs.append("• Origin: allow extra time for ground ops due to weather.")
                    if wx_dest['wind_mph'] > 20 or wx_dest['precip_in'] > 0.5:
                        recs.append("• Destination: anticipate arrival holds or longer taxi-in.")
                    for r in recs:
                        st.write(r)
                else:
                    st.success("Flight expected to operate on schedule. Have a pleasant journey!")

            except Exception as e:
                if DEBUG_MODE:
                    st.error("An error occurred while making the prediction.")
                    st.exception(e)
                else:
                    st.error("Something went wrong while predicting. Enable 'Show debug errors' in the sidebar for details.")
                st.stop()

    # History
    if st.session_state.predictions_history:
        st.markdown("---")
        st.markdown("### 📊 Recent Predictions")
        history_df = pd.DataFrame(st.session_state.predictions_history)
        history_df['Departure Delay'] = history_df['departure_delay'].round().astype(int)
        history_df['Arrival Delay'] = history_df['arrival_delay'].round().astype(int)
        history_df['Dep. Risk %'] = (history_df['departure_probability'] * 100).round(1)
        history_df['Arr. Risk %'] = (history_df['arrival_probability'] * 100).round(1)
        
        if 'departure_time' in history_df.columns:
            history_df['Dep Time'] = history_df['departure_time'].apply(lambda x: x.strftime("%I:%M %p") if pd.notnull(x) else "")
            history_df['Arr Time'] = history_df['arrival_time'].apply(lambda x: x.strftime("%I:%M %p") if pd.notnull(x) else "")
            display_df = history_df[['flight', 'date', 'Dep Time', 'Arr Time', 'Departure Delay', 'Arrival Delay', 'Dep. Risk %', 'Arr. Risk %']].tail(5)
        else:
            display_df = history_df[['flight', 'date', 'Departure Delay', 'Arrival Delay', 'Dep. Risk %', 'Arr. Risk %']].tail(5)
        
        st.dataframe(display_df, use_container_width=True)

        if len(history_df) > 1:
            col1, col2 = st.columns(2)
            with col1:
                fig_hist_dep = px.bar(history_df.tail(10), x='flight', y='Departure Delay',
                                      title="Recent Departure Delays", color='Departure Delay',
                                      color_continuous_scale=['green', 'yellow', 'red'])
                fig_hist_dep.update_layout(margin=dict(l=10, r=10, t=40, b=10), xaxis_title=None)
                st.plotly_chart(fig_hist_dep, use_container_width=True)
            with col2:
                fig_hist_arr = px.bar(history_df.tail(10), x='flight', y='Arrival Delay',
                                      title="Recent Arrival Delays", color='Arrival Delay',
                                      color_continuous_scale=['green', 'yellow', 'red'])
                fig_hist_arr.update_layout(margin=dict(l=10, r=10, t=40, b=10), xaxis_title=None)
                st.plotly_chart(fig_hist_arr, use_container_width=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; padding: 10px;'>
    Flight Delay Predictor | Weather via <b>Windy Point Forecast</b> (origin @ departure, destination @ arrival)<br>
    <small>Model uses destination weather features; origin weather is displayed for situational awareness.</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
