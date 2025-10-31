// pages/api/ai-advice.js
// Gemini Developer API fallback for advisory, translate, and rewrite.
// Requires env GEMINI_API_KEY.

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.GEMINI_API_KEY;

  try {
    const { mode = 'advice', language = 'en', advice = '', context = {} } = req.body || {};

    console.log('[ai-advice] Request received:', { mode, hasApiKey: !!apiKey });

    let prompt;
    if (mode === 'translate') {
      prompt = `Translate the following advisory to ${language} using clear, friendly travel English localized to the target language.\n\n${advice}`;
    } else if (mode === 'rewrite') {
      prompt = 'Rewrite the following advisory to be more concise while preserving all key recommendations. Limit to 120 words.\n\n' + advice;
    } else {
      prompt = `You are a concise travel assistant integrated in a flight delay dashboard. Given the flight context, weather and predicted delays, generate a short actionable advisory for the traveler. Prefer bullet points. Avoid hedging. Never invent data. Keep to ~120-180 words. Include “What to do next” with 2-3 steps.\n\nJSON Context:\n${JSON.stringify(context, null, 2)}`;
    }

    // If no API key, return a deterministic stub so the UI still works in demos
    if (!apiKey) {
      const stub = [
        'DEMO ADVISORY (no GEMINI_API_KEY set):',
        '- Allow extra time at the airport; weather may introduce minor gate/ground delays.',
        '- Pack essentials in carry-on and consider earlier check-in.',
        'What to do next:',
        '1) Monitor your airline app for gate changes.',
        '2) If connecting, choose longer layover options if possible.',
        '3) Have a backup ground transport plan at destination.'
      ].join('\n')
      return res.status(200).json({ text: stub, provider: 'stub' });
    }

    const base = 'https://generativelanguage.googleapis.com';
    const versions = ['v1beta', 'v1'];
    // Prefer explicit env override first
    const preferred = process.env.GEMINI_MODEL || 'gemini-1.5-flash';
    const models = Array.from(new Set([
      preferred,
      `${preferred}-latest`,
      `${preferred}-002`,
      'gemini-1.5-flash-8b',
      'gemini-1.5-flash-8b-latest',
      'gemini-1.5-flash',
      'gemini-1.5-flash-latest',
      'gemini-1.5-pro',
    ]));

    let lastErrText = '';
    for (const ver of versions) {
      for (const model of models) {
        const url = `${base}/${ver}/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
        console.log(`[ai-advice] Trying ${ver}/${model}...`);
        const r = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [
              {
                role: 'user',
                parts: [{ text: prompt }]
              }
            ]
          })
        });
        if (r.ok) {
          const data = await r.json();
          const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
          console.log(`[ai-advice] SUCCESS with ${ver}/${model}`);
          return res.status(200).json({ text, provider: `gemini:${ver}:${model}` });
        } else {
          const t = await r.text();
          console.log(`[ai-advice] FAILED ${ver}/${model}: ${r.status}`, t.substring(0, 200));
          lastErrText = `(${ver}/${model}) ${t}`;
          // Try next candidate on 404/400; break only for non-retryable 5xx
          if (r.status >= 500) {
            throw new Error(`Gemini API server error ${r.status}: ${t}`);
          }
        }
      }
    }
    // If nothing worked, return a graceful stub so the UI continues to function
    const stub = [
      'DEMO ADVISORY (Gemini endpoints unavailable):',
      '- Expect minor operational variability; build buffer into your plans.',
      '- Keep essentials handy and watch for gate updates.',
      'What to do next:',
      '1) Enable Generative Language API and verify your API key permissions.',
      '2) Try model=`GEMINI_MODEL=gemini-1.5-flash` with API version v1beta.',
      '3) Re-run — the app will use on-device AI when available.'
    ].join('\n');
    return res.status(200).json({ text: stub, provider: 'stub-fallback', errorInfo: lastErrText });
  } catch (err) {
    console.error('[ai-advice] error:', err);
    // Final safety net: return stub instead of 500 to keep UX intact
    const stub = [
      'DEMO ADVISORY (fallback on error):',
      '- Some disruptions possible; arrive early and monitor your airline app.',
      'What to do next:',
      '1) Consider flexible rebooking options.',
      '2) Prepare backup ground transport at destination.'
    ].join('\n');
    return res.status(200).json({ text: stub, provider: 'stub-error' });
  }
}
