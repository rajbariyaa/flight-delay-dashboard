# Chrome Built-in AI Setup Troubleshooting

If `window.ai` shows `undefined` after enabling flags, try these steps:

## 1. Verify Chrome Version

In Chrome Canary, go to:
```
chrome://version
```

Check that:
- Version is **128.0.6545.0 or higher**
- It says "Canary" in the version string
- Platform is macOS (arm64 or x64)

If version is below 128, update Chrome Canary:
```
chrome://settings/help
```

## 2. Double-check Flag Settings

### Flag 1: Prompt API
```
chrome://flags/#prompt-api-for-gemini-nano
```
Must be set to: **Enabled** (not Default)

### Flag 2: Optimization Guide
```
chrome://flags/#optimization-guide-on-device-model
```
Must be set to: **Enabled BypassPerfRequirement** (not just "Enabled")

⚠️ Common mistake: Choosing "Enabled" instead of "Enabled BypassPerfRequirement"

## 3. Complete Restart

After changing flags:
1. Click the blue "Relaunch" button
2. OR completely quit Chrome Canary (Cmd+Q)
3. Close ALL Chrome Canary windows
4. Reopen Chrome Canary
5. Wait 10-15 seconds after opening

## 4. Check Origin Trial Enrollment (Alternative)

If flags still don't work, try enrolling in the origin trial:

1. Go to: https://developer.chrome.com/origintrials/#/view_trial/1122744326555721729
2. Register your localhost
3. Add the token to your app

## 5. Known Issues

### macOS-specific issues:
- Some M1/M2 Macs have issues with early builds
- Try Chrome Dev channel instead of Canary
- Ensure macOS is updated to latest version

### Version-specific:
- Builds before 128.0.6545.0 don't support Prompt API
- Some builds between 128-130 had bugs
- Try latest Canary or wait for stable release

## 6. Alternative: Use Gemini API

If you can't get Built-in AI working for the hackathon:

1. Get a free Gemini API key: https://aistudio.google.com/app/apikey
2. Add to `.env.local`:
   ```
   GEMINI_API_KEY=your-key-here
   ```
3. Your app will use the server fallback
4. In your submission, explain the Built-in AI integration is ready but you're using fallback for demo

## 7. Test Commands

Run these in Chrome Canary DevTools Console:

```javascript
// Check if AI object exists
console.log('window.ai:', window.ai)

// Check Chrome version
console.log('Chrome version:', navigator.userAgent)

// Check if running in secure context
console.log('Secure context:', window.isSecureContext)

// Check available APIs
console.log('Available APIs:', Object.keys(window).filter(k => k.includes('ai')))
```

## 8. Report Your Findings

Share the output of the test commands above so we can diagnose further.
