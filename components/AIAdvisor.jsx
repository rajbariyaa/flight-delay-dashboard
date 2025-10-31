import { useCallback, useEffect, useMemo, useState } from 'react'

// Client-side advisor that uses Chrome Built‑in AI (Prompt API / Gemini Nano) if available.
// Falls back gracefully with helpful messaging when not available.
export default function AIAdvisor({
  origin,
  destination,
  date,
  departureTime,
  arrivalTime,
  originWeather,
  destWeather,
  prediction
}) {
  const [advice, setAdvice] = useState('')
  const [loading, setLoading] = useState(false)
  const [language, setLanguage] = useState('en')
  const [provider, setProvider] = useState('') // Track which AI provider was used
  const [aiStatus, setAiStatus] = useState(null) // Track Built-in AI availability

  const supportsPromptAPI = useMemo(() => {
    return typeof window !== 'undefined' && window.ai && typeof window.ai.createTextSession === 'function'
  }, [])

  // Check Built-in AI status on mount
  useEffect(() => {
    async function checkAI() {
      if (typeof window === 'undefined') return
      if (!window.ai) {
        setAiStatus('unavailable')
        return
      }
      try {
        const status = await window.ai.canCreateTextSession()
        setAiStatus(status) // "readily", "after-download", or "no"
      } catch (e) {
        setAiStatus('error')
      }
    }
    checkAI()
  }, [])

  const systemPrompt = useMemo(() => {
    return [
      'You are a concise travel assistant integrated in a flight delay dashboard.',
      'Given the flight context, weather and predicted delays, generate a short actionable advisory for the traveler.',
      'Prefer bullet points. Avoid hedging. Never invent data.',
      'Keep to ~120-180 words. Include “What to do next” with 2-3 steps.',
    ].join(' ')
  }, [])

  const buildContext = useCallback(() => {
    const d = date instanceof Date ? date.toISOString().split('T')[0] : String(date)
    const ctx = {
      flight: { origin, destination, date: d, departureTime, arrivalTime },
      weather: { origin: originWeather, destination: destWeather },
      prediction: prediction || null
    }
    return ctx
  }, [origin, destination, date, departureTime, arrivalTime, originWeather, destWeather, prediction])

  const generate = useCallback(async (mode = 'advice') => {
    setLoading(true)
    try {
      if (supportsPromptAPI) {
        const can = await window.ai?.canCreateTextSession?.()
        if (can === 'readily' || can === 'after-download') {
          const session = await window.ai.createTextSession({
            systemPrompt,
            temperature: mode === 'translate' ? 0.2 : 0.4,
            topK: 40
          })

          const ctx = buildContext()
          let prompt
          if (mode === 'translate') {
            prompt = `Translate the following advisory to ${language} using clear, friendly travel English localized to the target language:\n\n${advice}`
          } else if (mode === 'rewrite') {
            prompt = 'Rewrite the following advisory to be more concise while preserving all key recommendations. Limit to 120 words.\n\n' + advice
          } else {
            prompt = `Create a traveler advisory for this flight context. Output plain text.\n\nJSON Context:\n${JSON.stringify(ctx, null, 2)}`
          }

          const output = await session.prompt(prompt)
          setAdvice(String(output || ''))
          setProvider('on-device (Gemini Nano)')
          return
        }
      }

      // Fallback to server (Gemini Developer API)
      const ctx = buildContext()
      console.log('[AIAdvisor] Calling server fallback with context:', ctx)
      const r = await fetch('/api/ai-advice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, language, advice, context: ctx })
      })
      const j = await r.json()
      console.log('[AIAdvisor] Server response:', j)
      if (!r.ok) throw new Error(j?.error || 'AI advice failed')
      setAdvice(String(j.text || ''))
      setProvider(j.provider || 'server')
      console.log('[AIAdvisor] Updated advice and provider:', j.provider)
    } catch (err) {
      console.error('AIAdvisor error', err)
      setAdvice('Unable to generate advisory (both Built-in AI and fallback failed).')
      setProvider('error')
    } finally {
      setLoading(false)
    }
  }, [supportsPromptAPI, systemPrompt, buildContext, advice, language])

  return (
    <div className="bg-white rounded-lg border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">AI Travel Advisor</h3>
          {provider && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              provider.startsWith('on-device') 
                ? 'bg-green-100 text-green-700' 
                : provider.startsWith('gemini:')
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-600'
            }`}>
              {provider.startsWith('on-device') ? '🔒 On-device' : 
               provider.startsWith('gemini:') ? '☁️ Server' : 
               '📋 Demo'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={e => setLanguage(e.target.value)}
            className="text-sm border rounded px-2 py-1"
            aria-label="Target language"
          >
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="hi">Hindi</option>
            <option value="zh">Chinese</option>
            <option value="ja">Japanese</option>
          </select>
          <button
            onClick={() => generate('advice')}
            disabled={loading}
            className={`text-sm px-3 py-1 rounded ${loading ? 'bg-blue-300' : 'bg-blue-600 hover:bg-blue-700'} text-white`}
          >
            {loading ? 'Generating…' : 'Generate advisory'}
          </button>
        </div>
      </div>

      {/* No warning needed: we silently fallback to server if Built-in AI is unavailable */}

      {aiStatus && aiStatus !== 'readily' && (
        <div className={`text-xs border rounded p-2 ${
          aiStatus === 'after-download' 
            ? 'bg-blue-50 border-blue-200 text-blue-700'
            : aiStatus === 'unavailable'
            ? 'bg-amber-50 border-amber-200 text-amber-700'
            : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {aiStatus === 'after-download' && (
            <>
              <strong>📥 Model Download Required:</strong> Chrome needs to download Gemini Nano (~1.7GB).
              Go to <code className="bg-white px-1 rounded">chrome://components/</code> and click "Check for update" on "Optimization Guide On Device Model".
            </>
          )}
          {aiStatus === 'unavailable' && (
            <>
              <strong>⚙️ Setup Required:</strong> Chrome Built-in AI is not available. 
              Enable flags in <code className="bg-white px-1 rounded">chrome://flags</code>:
              <br/>• <code className="bg-white px-1 rounded">prompt-api-for-gemini-nano</code> → Enabled
              <br/>• <code className="bg-white px-1 rounded">optimization-guide-on-device-model</code> → Enabled BypassPerfRequirement
              <br/>Then restart Chrome Canary.
            </>
          )}
          {(aiStatus === 'no' || aiStatus === 'error') && (
            <>
              <strong>❌ Not Available:</strong> Built-in AI cannot be enabled. Make sure you're using Chrome Canary 128+ with the required flags enabled.
            </>
          )}
        </div>
      )}

      {aiStatus === 'readily' && (
        <div className="text-xs bg-green-50 border border-green-200 text-green-700 rounded p-2">
          <strong>✅ On-device AI Ready:</strong> Gemini Nano is available. Your advisories will run entirely on your device!
        </div>
      )}

      <div className="space-x-2">
        <button
          onClick={() => generate('translate')}
          disabled={loading || !advice}
          className="text-xs px-2 py-1 rounded border bg-white hover:bg-gray-50"
        >
          Translate
        </button>
        <button
          onClick={() => generate('rewrite')}
          disabled={loading || !advice}
          className="text-xs px-2 py-1 rounded border bg-white hover:bg-gray-50"
        >
          Rewrite shorter
        </button>
      </div>

      <div className="border rounded p-3 text-sm whitespace-pre-wrap min-h-[120px]">
        {advice || 'No advisory yet. Click “Generate advisory”.'}
      </div>
    </div>
  )
}
