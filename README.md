# Weather-Aware Truck Routing

Pick the safest truck route between two places. The app finds up to three routes, checks the weather each one will hit at the time the truck gets there, scores the risk, and recommends one.

- Live app: https://weather-truck-routing-159685347492.us-central1.run.app
- Walkthrough video: Loom link added at submission

The first trip you plan can take 20 to 40 seconds. The weather service is slow, and the app shows a loading state while it waits.

## How it works

1. You enter an origin, a destination, a departure time, the cargo weight and how often to check the weather (every 10, 25 or 50 miles).
2. HERE finds truck routes. The cargo weight plus 35,000 lb for the empty truck is sent as the gross weight, so the routes respect truck limits.
3. The route is cut into checkpoints. Each one gets an arrival time that includes the legally required driving breaks, and the Open-Meteo forecast for that exact hour.
4. Each checkpoint is scored Low, Moderate, High, Severe or No Travel from wind, rain and snow, and heavy loads make strong wind worse. Routes are ranked and the best one is recommended with a one-line reason.
5. A heatmap shows wind, rain, snow or overall risk along the corridor for the 48 hours after departure. Hour 0 on the slider is the departure time, so the clock and the truck line up with the trip. Dragging the slider only swaps data already in the browser, and a truck icon moves along the selected route.

## What the brief asked for, and where it lives

| Requirement | How it is done | Where to look |
|---|---|---|
| Origin, destination, departure time, load weight | Form with place autocomplete (HERE geocoding, proxied so the key stays on the server). Also an optional driver name and the checkpoint interval. | `frontend/src/components/TripForm.tsx`, `backend/trips/serializers.py` |
| 3 route options from a routing API | HERE truck routing with 2 alternatives. If fewer than 3 come back, it asks for detours through a point shifted sideways from the middle of the route. | `backend/trips/routing.py` |
| Weather every 10, 25 or 50 miles at the truck's arrival time | Checkpoints along the route line, arrival times with driving breaks, then the Open-Meteo forecast hour that contains each arrival. | `geometry.py`, `hos.py`, `timeline.py`, `weather.py`, `planner.py` in `backend/trips/` |
| Risk from the given risk and load rules | Pure Python with no Django, one function per rule, tested at every boundary. | `backend/trips/risk.py`, `backend/trips/tests/` |
| Recommend the best route (risk and time) | Routes are ranked on No Travel, Severe and High miles, then average risk, then travel time. The winner gets a one-line reason. | `risk.py` (ranking) |
| Routes, checkpoints, risk levels, ETAs and summaries on a map | Route lines, risk-coloured checkpoints with popups, route cards, a timeline and warnings, all in the origin's time zone. | `frontend/src/components/` (`RouteMap`, `RouteCards`, `Timeline`, `WarningsList`) |
| Weather heatmap along the corridor with a 0 to 48 hour slider | One server call returns every hour for a grid around the routes. The slider swaps hours in memory, with no network calls. | `backend/trips/corridor.py`, `frontend/src/heatmap.ts`, `ForecastPanel.tsx` |
| GitHub repo, hosted app, Loom | The links are at the top of this file. | |

## Decisions where the brief was open

- **Wind** uses gusts, and never less than the sustained wind, because gusts are what tip trucks over.
- **Boundaries** are inclusive at the lower end, so exactly 25 mph is Moderate.
- **Level per checkpoint** is the worst of wind, rain and snow. The load rules can raise it and never lower it.
- **Ranking** compares No Travel miles first, then Severe, then High, then the average risk, then travel time. The brief lists Severe first. I put No Travel ahead of it because a stretch where nobody should drive is worse than any Severe one. Average risk is weighted by miles and skips miles with no forecast.
- **Miles per checkpoint:** each checkpoint covers the road from halfway to the previous one to halfway to the next one, so the covered miles add up to the route length.
- **Driving breaks** follow the US federal rules in simplified form: 30 minutes after 8 hours of driving and 10 hours of rest after 11. The 14-hour duty window is not modelled.
- **Weight:** a load that pushes the gross weight over 80,000 lb shows an "overweight permit needed" warning. It is not an input error.
- **No forecast:** a checkpoint past the forecast range, or when the weather service fails, is grey (Unknown). The plan still works and says so in the warnings.
- **Fewer than three routes:** if HERE returns fewer, the detour fallback above fills in, and any detour that mostly repeats an existing route is dropped.
- **The truck icon** stays on the map at every slider hour. It waits at the origin before departure and at the destination after arrival, dimmed, so it never seems to vanish.

## Run it locally

You need Python 3.13, Node 24 and a free HERE API key.

```bash
# Backend
cd backend
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
echo "HERE_API_KEY=your-key-here" > .env
python manage.py runserver
```

```bash
# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` calls to Django on port 8000.

Tests and checks:

```bash
cd backend && python manage.py test trips
cd frontend && npm run build && npm run lint && npm run format:check
```

## Deploy

One Docker image: a Node stage builds the React app, then a slim Python image serves the API and the built app together with gunicorn and WhiteNoise. It runs on Google Cloud Run, deployed with `gcloud run deploy --source .`. The HERE key and the Django secret live in Secret Manager.

## Trade-offs and next steps

- **The cache lives in memory** (30 minutes, per instance). Redis would share it between instances and survive restarts.
- **The heatmap is capped at 120 grid points** to stay fast and polite to the free weather service.
- **Cloud Run needs its own outbound IP.** Open-Meteo's free tier limits shared cloud IPs, and the shared Cloud Run addresses were already over the limit (HTTP 429). The service sends traffic through Cloud NAT with a reserved static IP.
- **Deploys are manual.** Next step is GitHub Actions with Workload Identity Federation, so no key is stored in GitHub.
- **Not included:** live traffic, tolls, place names in the warnings (they use mile markers), saved trips and accounts, and frontend tests.

## Built with

Django and Django REST Framework, React with TypeScript, Material UI, MapLibre, HERE, Open-Meteo, OpenFreeMap tiles.
## License

MIT
