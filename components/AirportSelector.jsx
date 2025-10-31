import { useEffect, useState } from 'react'

export default function AirportSelector({ origin, destination, onOriginChange, onDestinationChange, className }) {
  const [airports, setAirports] = useState([])
  const [distance, setDistance] = useState(null)

  useEffect(() => {
    fetch('/airports.json').then(r => r.json()).then(setAirports)
  }, [])

  useEffect(() => {
    if (origin && destination && airports.length > 0) {
      const originAirport = airports.find(a => a.iata === origin)
      const destAirport = airports.find(a => a.iata === destination)
      if (originAirport && destAirport) {
        // Calculate distance using Haversine formula
        const R = 3959 // Earth's radius in miles
        const lat1 = originAirport.lat * Math.PI / 180
        const lat2 = destAirport.lat * Math.PI / 180
        const dLat = (destAirport.lat - originAirport.lat) * Math.PI / 180
        const dLon = (destAirport.lon - originAirport.lon) * Math.PI / 180
        
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1) * Math.cos(lat2) *
                Math.sin(dLon/2) * Math.sin(dLon/2)
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
        const distance = R * c
        setDistance(Math.round(distance))
      }
    }
  }, [origin, destination, airports])

  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 ${className}`}>
      <div className="space-y-1">
        <label className="text-sm font-medium text-gray-700">Origin Airport</label>
        <select 
          value={origin} 
          onChange={e => onOriginChange(e.target.value)}
          className="w-full rounded-lg border border-gray-300 p-2 focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select Origin</option>
          {airports.map(a => (
            <option key={a.iata} value={a.iata}>{a.iata} – {a.name}</option>
          ))}
        </select>
      </div>
      
      <div className="space-y-1">
        <label className="text-sm font-medium text-gray-700">Destination Airport</label>
        <select 
          value={destination} 
          onChange={e => onDestinationChange(e.target.value)}
          className="w-full rounded-lg border border-gray-300 p-2 focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select Destination</option>
          {airports.map(a => (
            <option key={a.iata} value={a.iata}>{a.iata} – {a.name}</option>
          ))}
        </select>
      </div>
      
      {distance && (
        <div className="col-span-full">
          <p className="text-sm text-gray-600">
            Estimated flight distance: <span className="font-medium">{distance} miles</span>
          </p>
        </div>
      )}
    </div>
  )
}
