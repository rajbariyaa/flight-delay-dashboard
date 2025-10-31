const airlines = [
  { code: 'AA', name: 'American Airlines' },
  { code: 'DL', name: 'Delta Air Lines' },
  { code: 'UA', name: 'United Airlines' },
  { code: 'WN', name: 'Southwest Airlines' },
  { code: 'B6', name: 'JetBlue Airways' },
  { code: 'AS', name: 'Alaska Airlines' },
  { code: 'NK', name: 'Spirit Airlines' },
  { code: 'F9', name: 'Frontier Airlines' },
  { code: 'HA', name: 'Hawaiian Airlines' },
  { code: 'OO', name: 'SkyWest Airlines' },
];

export default function AirlineSelector({ value, onChange, className = "" }) {
  return (
    <div className={`space-y-1 ${className}`}>
      <label className="text-sm font-medium text-gray-700">Airline</label>
      <select 
        value={value} 
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-300 p-2 focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Select Airline</option>
        {airlines.map(airline => (
          <option key={airline.code} value={airline.code}>
            {airline.code} - {airline.name}
          </option>
        ))}
      </select>
    </div>
  );
}