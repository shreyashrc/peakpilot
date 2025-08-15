# Deployment to Render

1. Fork this repository
2. Connect to Render and create a new Web Service
3. Choose Docker as runtime, point to `Dockerfile`
4. Add environment variables:
   - `GEMINI_API_KEY` (required)
   - Optional: `INDEXED_TRAILS`, `CACHE_TTL_MINUTES`, `WEATHER_CACHE_TTL_MINUTES`
5. Health check path: `/api/health`
6. Deploy!

The app will be available at: https://hiking-assistant.onrender.com

## Deployment Checklist
- [ ] Environment variables set (`GEMINI_API_KEY`, etc.)
- [ ] ChromaDB persistence configured (bind volume to `/app/chroma_db` if needed)
- [ ] WebSocket URL updated in frontend for production
- [ ] Static files served correctly
- [ ] Health check responding (`/api/health`)

## Frontend WebSocket URL
Use this snippet to auto-pick the correct WS endpoint:

```js
const WS_URL = window.location.hostname === 'localhost' 
  ? 'ws://localhost:8000/ws'
  : `wss://${window.location.hostname}/ws`;
```

## Monitoring & Logs
- Logs include progress steps and errors
- Track query response times using timestamps around orchestrator execution
- Monitor API usage by watching Gemini generation events in logs
