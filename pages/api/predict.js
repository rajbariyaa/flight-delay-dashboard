// pages/api/predict.js
// Bridge Next.js -> Python model (.pkl). Spawns a short-lived Python process
// to load the pickle and return predictions for a single flight.

import { spawn } from "child_process";
import fs from "fs";
import path from "path";

function toHHMM(timeStr) {
  // timeStr like "14:30" -> 1430
  if (!timeStr || typeof timeStr !== "string") return 0;
  const [hh, mm] = timeStr.split(":");
  const h = parseInt(hh, 10);
  const m = parseInt(mm, 10);
  if (Number.isNaN(h) || Number.isNaN(m)) return 0;
  return h * 100 + m;
}

function loadAirportsIndex() {
  try {
    const p = path.join(process.cwd(), "public", "airports.json");
    const raw = fs.readFileSync(p, "utf8");
    const arr = JSON.parse(raw);
    const map = new Map();
    for (const a of arr) {
      if (a && a.iata) {
        map.set(String(a.iata).toUpperCase(), a);
      }
    }
    return map;
  } catch (e) {
    return new Map();
  }
}

function haversineMiles(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const R = 3958.8; // miles
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function estimateDistanceMiles(origin, destination) {
  const idx = loadAirportsIndex();
  const o = idx.get(String(origin || "").toUpperCase());
  const d = idx.get(String(destination || "").toUpperCase());
  if (o && d && typeof o.lat === "number" && typeof d.lat === "number") {
    return Math.round(haversineMiles(o.lat, o.lon, d.lat, d.lon));
  }
  // Fallback demo distance
  return 1000;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const {
      airline,
      origin,
      destination,
      dateISO, // e.g., new Date().toISOString()
      departureTime = "14:30",
      arrivalTime = "17:30",
      destWeather,
    } = req.body || {};

    if (!airline || !origin || !destination || !destWeather) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    const when = dateISO ? new Date(dateISO) : new Date();
    const YEAR = when.getUTCFullYear();
    const MONTH = when.getUTCMonth() + 1;
    const DAY = when.getUTCDate();
    const SCHEDULED_DEPARTURE = toHHMM(departureTime);
    const DISTANCE = estimateDistanceMiles(origin, destination);

    const record = {
      YEAR,
      MONTH,
      DAY,
      SCHEDULED_DEPARTURE,
      AIRLINE: String(airline).toUpperCase(),
      ORIGIN_AIRPORT: String(origin).toUpperCase(),
      DESTINATION_AIRPORT: String(destination).toUpperCase(),
      DISTANCE,
      DEPARTURE_DELAY: 0,
      dest_temperature: destWeather?.temperature_f ?? 72,
      dest_humidity: destWeather?.humidity_pct ?? 60,
      dest_pressure: destWeather?.pressure_mb ?? 1013,
      dest_wind_speed: destWeather?.wind_mph ?? 8,
      dest_cloudiness: destWeather?.cloudiness_pct ?? 30,
      dest_visibility: destWeather?.visibility_mi ?? 10,
      dest_precipitation: destWeather?.precip_in ?? 0,
      dest_snow: destWeather?.snow_in ?? 0,
    };

    const scriptPath = path.join(process.cwd(), "server", "predict_once.py");
    const modelPath =
      process.env.MODEL_PATH ||
      path.join(process.cwd(), "public", "model", "flight_delay_models_complete.pkl");

    // Check script exists
    if (!fs.existsSync(scriptPath)) {
      return res.status(503).json({ error: "Prediction script not found", details: scriptPath });
    }
    // Check model path (we'll let the script error with a friendlier message too)
    const env = { ...process.env, MODEL_PATH: modelPath };

    const py = spawn("python3", [scriptPath], { env });
    let stdout = "";
    let stderr = "";

    const timeoutMs = 15000; // 15s safety
    const killTimer = setTimeout(() => {
      try { py.kill("SIGKILL"); } catch {}
    }, timeoutMs);

    py.stdout.on("data", (d) => (stdout += d.toString()));
    py.stderr.on("data", (d) => (stderr += d.toString()));

    py.on("error", (err) => {
      clearTimeout(killTimer);
      return res.status(503).json({ error: "Failed to start Python", details: String(err) });
    });

    py.on("close", (code) => {
      clearTimeout(killTimer);
      if (code !== 0) {
        return res.status(500).json({ error: "Prediction failed", code, stderr: stderr?.slice(0, 2000) });
      }
      try {
        const out = JSON.parse(stdout || "{}");
        if (out && out.departure_probability != null) {
          return res.status(200).json({ provider: "python-pkl", prediction: out });
        }
        return res.status(500).json({ error: "Malformed output from predictor", stdout });
      } catch (e) {
        return res.status(500).json({ error: "Failed to parse predictor output", stdout: stdout?.slice(0, 2000) });
      }
    });

    // Write input record to stdin
    py.stdin.write(JSON.stringify(record));
    py.stdin.end();
  } catch (e) {
    return res.status(500).json({ error: "Unexpected server error", details: String(e) });
  }
}
