import { useMemo } from 'react';

export default function PredictionCard({ prediction, type = "departure" }) {
  const { delay, probability } = useMemo(() => ({
    delay: prediction?.[`${type}_delay`] || 0,
    probability: prediction?.[`${type}_probability`] || 0
  }), [prediction, type]);

  const riskLevel = useMemo(() => {
    const prob = probability * 100;
    if (prob < 30) return { level: "Low", class: "bg-green-100 text-green-700" };
    if (prob < 60) return { level: "Medium", class: "bg-yellow-100 text-yellow-700" };
    return { level: "High", class: "bg-red-100 text-red-700" };
  }, [probability]);

  return (
    <div className="rounded-2xl border p-4 shadow-sm bg-white">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-sm text-gray-500 capitalize">{type} Delay Prediction</div>
          <div className="mt-1">
            <div className="text-3xl font-bold">
              {delay > 0 ? `${Math.round(delay)} min` : "On Time"}
            </div>
            {delay > 15 && (
              <div className="text-sm text-red-600 mt-1">
                {Math.round(delay)} minutes late
              </div>
            )}
          </div>
        </div>
        
        <div className="text-right">
          <div className="text-2xl font-bold">{Math.round(probability * 100)}%</div>
          <div className={`mt-1 inline-block rounded-full px-3 py-1 text-sm ${riskLevel.class}`}>
            {riskLevel.level} Risk
          </div>
        </div>
      </div>

      {delay > 15 && (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
          <div className="font-medium text-yellow-800">Recommendations:</div>
          <ul className="mt-2 space-y-1 text-yellow-700">
            {delay > 30 && (
              <li>• Arrive at the airport later to avoid long wait times</li>
            )}
            <li>• Check with airline for possible rebooking options</li>
            {delay > 30 && type === "arrival" && (
              <>
                <li>• Notify ground transportation about potential late arrival</li>
                <li>• Consider rebooking connecting flights if applicable</li>
              </>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
