#!/usr/bin/env python3
"""
Reads one JSON record from stdin, loads the pickled model pipeline, and prints
prediction JSON to stdout.

Expected input keys (single flight):
  YEAR, MONTH, DAY, SCHEDULED_DEPARTURE (e.g., 1430),
  AIRLINE, ORIGIN_AIRPORT, DESTINATION_AIRPORT, DISTANCE, DEPARTURE_DELAY,
  dest_temperature, dest_humidity, dest_pressure, dest_wind_speed,
  dest_cloudiness, dest_visibility, dest_precipitation, dest_snow

Environment:
  MODEL_PATH: absolute/relative path to flight_delay_models_complete.pkl
"""

import sys
import os
import json
import pickle
import pandas as pd
import numpy as np


def load_models(model_path: str):
    with open(model_path, 'rb') as f:
        return pickle.load(f)


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


def main():
    try:
        raw = sys.stdin.read()
        if not raw:
            print(json.dumps({"error": "No input"}))
            sys.exit(2)
        rec = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(2)

    model_path = os.environ.get("MODEL_PATH") or os.path.join("public", "model", "flight_delay_models_complete.pkl")
    try:
        models = load_models(model_path)
    except FileNotFoundError:
        print(json.dumps({"error": f"Model file not found at: {model_path}"}))
        sys.exit(3)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load model: {e}"}))
        sys.exit(3)

    # Build a one-row DataFrame
    try:
        df = pd.DataFrame([rec])
        out = make_prediction(df, models)
        print(json.dumps(out))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"error": f"Prediction error: {e}"}))
        sys.exit(4)


if __name__ == "__main__":
    main()
