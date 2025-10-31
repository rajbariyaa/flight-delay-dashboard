export default function WeatherInputs({ weather, onChange, title = "Weather Conditions" }) {
  // This component now displays read-only weather fetched from the server.
  // Manual editing has been removed — weather should be fetched by providing
  // airport + date + time in the parent page.
  return (
    <div className="space-y-3 p-4 bg-white rounded-lg border">
      <h3 className="font-medium text-lg">{title}</h3>
      <div className="grid grid-cols-2 gap-3 text-sm text-gray-700">
        <div className="flex flex-col">
          <span className="text-gray-500">Temperature</span>
          <span className="font-medium">{weather?.temperature_f ?? '—'} °F</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Wind</span>
          <span className="font-medium">{weather?.wind_mph ?? '—'} mph</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Humidity</span>
          <span className="font-medium">{weather?.humidity_pct ?? '—'} %</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Pressure</span>
          <span className="font-medium">{weather?.pressure_mb ?? '—'} mb</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Cloud Cover</span>
          <span className="font-medium">{weather?.cloudiness_pct ?? '—'} %</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Visibility</span>
          <span className="font-medium">{weather?.visibility_mi ?? '—'} mi</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Precipitation</span>
          <span className="font-medium">{weather?.precip_in ?? '—'} in</span>
        </div>
        <div className="flex flex-col">
          <span className="text-gray-500">Snow</span>
          <span className="font-medium">{weather?.snow_in ?? '—'} in</span>
        </div>
      </div>
    </div>
  )
}

