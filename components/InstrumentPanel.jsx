export default function InstrumentPanel({ backend, gpuOk }) {
  return (
    <div className="rounded-2xl border p-4 shadow-sm bg-white">
      <div className="text-sm text-gray-500">Chrome/TF.js Instrumentation</div>
      <ul className="mt-2 text-sm">
        <li>WebGPU available: <b>{gpuOk ? 'Yes ✅' : 'No ⛔'}</b></li>
        <li>TF.js backend in use: <b>{backend || '—'}</b></li>
      </ul>
      <p className="mt-2 text-xs text-gray-500">Tip: Visit chrome://gpu to confirm WebGPU status.</p>
    </div>
  )
}
