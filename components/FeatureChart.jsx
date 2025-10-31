import { Bar } from 'react-chartjs-2'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export default function FeatureChart({ importances }) {
  const labels = ['Temp','Wind','Precip','Hour','Day']
  const data = {
    labels,
    datasets: [{
      label: 'Influence (abs)',
      data: importances,
    }]
  }
  const options = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } }
  }
  return (
    <div className="rounded-2xl border p-4 shadow-sm bg-white">
      <div className="mb-2 text-sm text-gray-500">Feature Influence (demo)</div>
      <Bar data={data} options={options} />
    </div>
  )
}
