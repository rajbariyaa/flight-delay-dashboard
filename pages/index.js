// pages/index.js
import { useEffect, useState } from "react";
import Head from "next/head";

import AirlineSelector from "../components/AirlineSelector";
import AIAdvisor from "../components/AIAdvisor";
import AirportSelector from "../components/AirportSelector";
import WeatherInputs from "../components/WeatherInputs";
import MapView from "../components/MapView";
import PredictionCard from "../components/PredictionCard";
import FeatureChart from "../components/FeatureChart";
import InstrumentPanel from "../components/InstrumentPanel";

export default function Home() {
  // Core selections
  const [airline, setAirline] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");

  // Weather states
  const [originWx, setOriginWx] = useState(null);
  const [destWx, setDestWx] = useState(null);
  const [loadingOriginWx, setLoadingOriginWx] = useState(false);
  const [loadingDestWx, setLoadingDestWx] = useState(false);
  const [wxError, setWxError] = useState(null);

  // (Optional) Demo prediction state to keep page functional
  const [prediction, setPrediction] = useState(null);

  // Fetch weather for a given IATA via our API route
  async function fetchWeather(iata, setter) {
    try {
      setWxError(null);
      if (!iata) {
        setter(null);
        return;
      }
      const res = await fetch(`/api/weather?iata=${encodeURIComponent(iata)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Weather fetch failed");
      setter(data.weather || null);
    } catch (e) {
      console.error("fetchWeather error:", e);
      setWxError(e.message || "Weather fetch failed");
      setter(null);
    }
  }

  // When origin changes, fetch its weather
  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoadingOriginWx(true);
      await fetchWeather(origin, (wx) => {
        if (!ignore) setOriginWx(wx);
      });
      if (!ignore) setLoadingOriginWx(false);
    })();
    return () => {
      ignore = true;
    };
  }, [origin]);

  // When destination changes, fetch its weather
  useEffect(() => {
    let ignore = false;
    (async () => {
      setLoadingDestWx(true);
      await fetchWeather(destination, (wx) => {
        if (!ignore) setDestWx(wx);
      });
      if (!ignore) setLoadingDestWx(false);
    })();
    return () => {
      ignore = true;
    };
  }, [destination]);

  // Try real model via /api/predict whenever inputs are ready; fallback to demo heuristic
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!destWx || !airline || !origin || !destination) {
        setPrediction(null);
        return;
      }

      // Call backend that uses the Python .pkl model
      try {
        const body = {
          airline,
          origin,
          destination,
          dateISO: new Date().toISOString(),
          departureTime: "14:30",
          arrivalTime: "17:30",
          destWeather: destWx,
        };
        const resp = await fetch("/api/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (resp.ok && data?.prediction && !cancelled) {
          setPrediction(data.prediction);
          return;
        }
        // If server returns error, fall through to heuristic
        console.warn("/api/predict fallback:", data?.error || resp.statusText);
      } catch (e) {
        console.warn("/api/predict call failed, using heuristic:", e);
      }

      // Heuristic fallback to keep UI responsive
      if (!originWx) return; // need at least origin weather for fallback
      const airlineFactors = {
        AA: 1.1,
        UA: 1.15,
        DL: 0.9,
        WN: 0.95,
        B6: 1.0,
        AS: 0.85,
        NK: 1.2,
        F9: 1.15,
      };
      const airlineFactor = airlineFactors[airline] || 1.0;
      const baseProb =
        (originWx?.wind_mph || 0) * 0.01 +
        (originWx?.precip_in || 0) * 0.1 +
        (originWx?.cloudiness_pct || 0) * 0.002;
      const prob = Math.min(0.95, Math.max(0, baseProb * airlineFactor));
      const delayMin = Math.round(prob * 45);
      if (!cancelled) {
        setPrediction({
          departure_delay: delayMin,
          departure_probability: prob,
          arrival_delay: Math.max(0, delayMin - 5),
          arrival_probability: Math.min(0.95, prob * 0.9),
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [destWx, originWx, origin, destination, airline]);

  // Fake feature importances (replace with real API when ready)
  const demoImportances = [0.42, 0.23, 0.15, 0.12, 0.08];

  return (
    <>
      <Head>
        <title>Flight Delay Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <main className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-6xl p-4 md:p-6 space-y-6">
          <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold">Flight Delay Dashboard</h1>
              <p className="text-sm text-gray-600">
                Select airline and airports to see live weather and estimated
                delay risk.
              </p>
            </div>
            <div className="w-full md:w-72">
              <AirlineSelector value={airline} onChange={setAirline} />
            </div>
          </header>

          {/* Selectors */}
          <section>
            <AirportSelector
              className="mt-2"
              origin={origin}
              destination={destination}
              onOriginChange={setOrigin}
              onDestinationChange={setDestination}
            />
          </section>

          {/* Weather + Maps */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-4">
              <div className="rounded-2xl border p-4 shadow-sm bg-white">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Origin</h2>
                  {loadingOriginWx && (
                    <span className="text-sm text-gray-500">Loading…</span>
                  )}
                </div>
                <div className="mt-3">
                  <MapView iata={origin} />
                </div>
                <div className="mt-4">
                  <WeatherInputs
                    title="Origin Weather"
                    weather={originWx}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border p-4 shadow-sm bg-white">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Destination</h2>
                  {loadingDestWx && (
                    <span className="text-sm text-gray-500">Loading…</span>
                  )}
                </div>
                <div className="mt-3">
                  <MapView iata={destination} />
                </div>
                <div className="mt-4">
                  <WeatherInputs
                    title="Destination Weather"
                    weather={destWx}
                  />
                </div>
              </div>
            </div>
          </section>

          {wxError && (
            <div className="p-3 rounded-md bg-red-50 border border-red-200 text-sm text-red-700">
              Weather error: {wxError}
            </div>
          )}

          {/* Prediction + Explainability */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <PredictionCard type="departure" prediction={prediction} />
              <div className="mt-4">
                <PredictionCard type="arrival" prediction={prediction} />
              </div>
            </div>
            <div>
              <FeatureChart importances={demoImportances} />
            </div>
          </section>

          {/* AI Advisor (Chrome Built-in AI Prompt API) */}
          <section>
            <AIAdvisor
              origin={origin}
              destination={destination}
              date={new Date()}
              departureTime={"14:30"}
              arrivalTime={"17:30"}
              originWeather={originWx}
              destWeather={destWx}
              prediction={prediction}
            />
          </section>

          {/* Instrumentation */}
          <section>
            <InstrumentPanel backend={"cpu"} gpuOk={false} />
          </section>
        </div>
      </main>
    </>
  );
}
