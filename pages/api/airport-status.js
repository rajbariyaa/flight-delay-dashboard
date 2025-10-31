export default function handler(req, res) {
  const { iata = 'BWI' } = req.query
  const table = {
    BWI: 'On Time',
    ATL: 'Moderate Delay',
    JFK: 'Severe Delay',
    ORD: 'Moderate Delay',
    LAX: 'On Time',
  }
  res.status(200).json({ airport: iata, status: table[iata] || 'Unknown' })
}
