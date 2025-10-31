

import fs from "fs";
import path from "path";

function toF(c) {
  return c == null ? null : (c * 9) / 5 + 32;
}
function msToMph(ms) {
  return ms == null ? null : ms * 2.236936;
}
function metersToMiles(m) {
  return m == null ? null : m / 1609.344;
}
function mmToIn(mm) {
  return mm == null ? null : mm / 25.4;
}

export default async function handler(req, res) {
  try {
    const { iata } = req.query;
    if (!iata) {
      return res.status(400).json({ error: "Missing query parameter: iata" });
    }

    // Load airports.json from /public
    const airportsPath = path.join(process.cwd(), "public", "airports.json");
    const airportsRaw = fs.readFileSync(airportsPath, "utf-8");
    const airports = JSON.parse(airportsRaw);

    const airport =
      airports.find((a) => a.iata?.toUpperCase() === iata.toUpperCase()) ||
      null;

    if (!airport) {
      return res.status(404).json({ error: `Unknown airport: ${iata}` });
    }

    // Call Open-Meteo "current" endpoint (no key needed)
    // Docs: https://open-meteo.com/en/docs
    const url =
      `https://api.open-meteo.com/v1/forecast` +
      `?latitude=${airport.lat}&longitude=${airport.lon}` +
      `&current=temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_direction_10m,precipitation,visibility,cloud_cover`;

    const r = await fetch(url, { next: { revalidate: 120 } }); // cache 2 minutes (Next.js)
    if (!r.ok) {
      throw new Error(`Weather provider error: ${r.status}`);
    }
    const j = await r.json();
    const cur = j?.current ?? {};

    // Normalize to the fields your WeatherInputs displays
    const weather = {
      temperature_f:
        cur.temperature_2m != null ? Math.round(toF(cur.temperature_2m)) : null,
      wind_mph:
        cur.wind_speed_10m != null ? Math.round(msToMph(cur.wind_speed_10m)) : null,
      humidity_pct:
        cur.relative_humidity_2m != null ? Math.round(cur.relative_humidity_2m) : null,
      pressure_mb:
        cur.pressure_msl != null ? Math.round(cur.pressure_msl) : null,
      cloudiness_pct:
        cur.cloud_cover != null ? Math.round(cur.cloud_cover) : null,
      visibility_mi:
        cur.visibility != null ? Number(metersToMiles(cur.visibility)).toFixed(1) : null,
      precip_in:
        cur.precipitation != null ? mmToIn(cur.precipitation).toFixed(2) : null,
      snow_in: null, // Open-Meteo current may not include snowfall; fill if you switch provider
      updated_at_iso: cur.time ?? null,
    };

    // Helpful metadata too
    const meta = {
      iata: airport.iata,
      name: airport.name,
      coords: { lat: airport.lat, lon: airport.lon },
      provider: "open-meteo",
      provider_units: {
        temperature: "°C -> °F",
        wind_speed: "m/s -> mph",
        visibility: "m -> mi",
        precipitation: "mm -> in",
        pressure: "mb",
      },
    };

    // Cache for a short time at the edge/browsers
    res.setHeader(
      "Cache-Control",
      "public, s-maxage=120, stale-while-revalidate=120"
    );

    return res.status(200).json({ meta, weather });
  } catch (err) {
    console.error("[/api/weather] error:", err);
    return res.status(500).json({ error: "Weather fetch failed" });
  }
}
