# AI-Driven Flight Delay Predictor (Web Dashboard Edition)

Chrome AI hackathon MVP demonstrating **hybrid AI**:
- **Client-side** inference with TensorFlow.js + **WebGPU**
- **Cloud** serverless API for contextual airport status

## Quick Start

```bash
npm install
npm run dev
# open http://localhost:3000
```

> Optional: place your TF.js model files in `/public/model` (model.json + shards). The app falls back to a baseline logistic demo model otherwise.

## Deploy
- Vercel: push to GitHub and import repo, or `vercel` CLI.
- Google Cloud Run: export Next.js and serve, or use Node server.

## Notes
- This MVP is for demo purposes. Replace the baseline with your trained model, and wire real data sources as time permits.

## Chrome Built‑in AI Challenge 2025 readiness

This project now includes a client-side AI panel powered by Chrome Built‑in AI (Prompt API / Gemini Nano) via the `AIAdvisor` component. It generates a concise travel advisory from your current selections, weather, and delay estimates, and can translate or rewrite the output entirely on-device.

- On-device advisory generation, translation, and rewrite
- No user data leaves the device when using Built‑in AI

### How to enable Chrome Built-in AI (Recommended)

**Step 1: Get Chrome Canary**
- Download [Chrome Canary](https://www.google.com/chrome/canary/) (version 128 or later)
- Or use Chrome Dev channel

**Step 2: Join the Early Preview Program**
- Sign up at [Chrome Built-in AI Early Preview Program](https://developer.chrome.com/docs/ai/built-in)
- This gives you access to documentation and updates

**Step 3: Enable the Prompt API**
- Open Chrome Canary
- Go to `chrome://flags/#prompt-api-for-gemini-nano`
- Restart Chrome

**Step 4: Verify and download model**
- Open DevTools Console (F12)
- Run: `await window.ai.canCreateTextSession()`
- If it returns `"readily"` → you're all set!
- If it returns `"after-download"` → Chrome will download Gemini Nano (~1.7GB)
  - This may take a few minutes
  - Check `chrome://components/` and look for "Optimization Guide On Device Model"
  - Click "Check for update" if needed
- If it returns `"no"` → ensure flags are enabled and restart Chrome

**Step 5: Test in your app**
- Run `npm run dev`
- Open http://localhost:3000
- Select airports and click "Generate advisory" in the AI Travel Advisor panel
- You should see real AI-generated travel advice running entirely on your device!

Hybrid fallback (optional)
- The app includes automatic fallback via `/api/ai-advice`
- When Built-in AI isn't available, it uses a demo stub
- To enable real server-side AI: set `GEMINI_API_KEY` in `.env.local`
- The UI automatically chooses: on-device (preferred) → server → demo stub

Security & Privacy
- AI runs locally with Chrome Built‑in AI; network calls for weather use Open‑Meteo (no API key).
- No sensitive user data is sent to third-party AI services by default.
