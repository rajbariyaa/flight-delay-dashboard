import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'

const MapContainer = dynamic(() => import('react-leaflet').then(m => m.MapContainer), { ssr: false })
const TileLayer = dynamic(() => import('react-leaflet').then(m => m.TileLayer), { ssr: false })
const Marker = dynamic(() => import('react-leaflet').then(m => m.Marker), { ssr: false })
const Popup = dynamic(() => import('react-leaflet').then(m => m.Popup), { ssr: false })

export default function MapView({ iata }) {
  const [airport, setAirport] = useState(null)

  useEffect(() => {
    fetch('/airports.json').then(r=>r.json()).then(list => {
      setAirport(list.find(a => a.iata === iata) || null)
    })
  }, [iata])

  if (!airport) return <div className="text-sm text-gray-500">Loading map…</div>

  return (
    <div className="rounded-2xl overflow-hidden border shadow-sm bg-white">
      <MapContainer center={[airport.lat, airport.lon]} zoom={10} style={{height:'300px', width:'100%'}}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Marker position={[airport.lat, airport.lon]}>
          <Popup>{airport.iata} – {airport.name}</Popup>
        </Marker>
      </MapContainer>
    </div>
  )
}
