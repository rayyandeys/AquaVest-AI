# AquaVest AI

Smart Portfolio Tracker & AI-Powered Stock Intelligence Dashboard. A local paper-trading app with an original deep-ocean glass interface. It includes local registration and sign-in; no external identity service, brokerage connection, or paid market API is required. Nothing is deployed.

## Features

- Overview with calculated portfolio value, invested capital, unrealized and realized P&L, daily contribution story, best performer, risk gauge and smart alerts.
- Sortable/searchable holdings, decimal transaction inputs, weighted-average buys, partial/full sells, oversell rejection and chronological ledger validation.
- Account-isolated SQLite portfolios, cash balances updated atomically by simulated orders, and transaction history scoped to the signed-in account.
- Local authentication with PBKDF2 password hashes, expiring HttpOnly session cookies, protected portfolio APIs, and an immediately available demo account.
- Stock/sector allocation donuts and daily price charts with 1D/1W/1M/3M/1Y controls.
- Searchable 13-stock Indian equity universe, seeded watchlist, market movers, stock fundamentals and technical analytics.
- Stock analysis and Portfolio Doctor with Gemini, Groq and deterministic local providers.
- Responsive sidebar, keyboard search (Ctrl+K), loading states, toast messages, empty/error states and reduced-motion support.

## Quick start — Windows PowerShell

Prerequisites: Python 3.12+ and Node.js 20.19+ (Node 22/24 also work). Run these commands from the project root in two terminals. Dependencies have been installed in this workspace; installation commands also make a fresh checkout runnable. Use npm.cmd to avoid PowerShell execution-policy restrictions.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend (second terminal, from project root):

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. Sign in with **demo@aquavest.local** / **AquaVestDemo2026!**, or register a separate account. The demo begins with eight illustrative holdings, a sample watchlist, and ₹1,000,000 starting capital allocated between holdings and cash. Interactive API docs: http://127.0.0.1:8000/docs. The Vite development server proxies /api to port 8000. Keep both terminals running. Virtual-environment activation is optional because the commands address its Python executable directly.

All orders are simulated and stored locally. A BUY reduces the signed-in account’s cash by quantity × entered price; a SELL increases it by the proceeds and updates realized P&L. Insufficient cash and oversells are rejected. No brokerage orders are sent. This setup is for a local demonstration, not public hosting; bind the backend to localhost and change the demo password before sharing access to the machine.

## Optional environment variables

Copy backend/.env.example to backend/.env. Restart the backend after changing it. Never put provider keys in the frontend.

| Variable | Default | Purpose |
| --- | --- | --- |
| GEMINI_API_KEY | empty | Enable Gemini when selected |
| GROQ_API_KEY | empty | Enable Groq when selected |
| AI_PROVIDER | gemini | gemini or groq; absent selected key uses local analytics |
| GEMINI_MODEL | gemini-2.5-flash | Configurable provider model |
| GROQ_MODEL | llama-3.3-70b-versatile | Configurable provider model |
| MARKET_MODE | auto | auto refreshes Yahoo in background; demo is fully offline/deterministic |
| DATABASE_URL | SQLite backend/aquavest.db | Optional alternate SQLite path |
| DEMO_PASSWORD | AquaVestDemo2026! | Password assigned to the built-in demo account when the database is first created |
| VITE_API_URL | /api | Optional frontend API base URL; configure in frontend/.env |

No credentials are needed for a complete demonstration. Model availability and free quotas depend on the provider; invalid keys, unavailable models, malformed output and network errors fall back to local analysis. Outbound AI requests send the relevant market/portfolio snapshot only when a selected provider key exists. Provider integrations follow [Gemini generateContent](https://ai.google.dev/api/generate-content) and [Groq Chat Completions](https://console.groq.com/docs/api-reference).

## Architecture

React + TypeScript + Vite + Tailwind CSS + Recharts + Lucide + Axios + React Router → FastAPI REST API → SQLAlchemy → SQLite.

MarketData service → cached Yahoo daily history → clearly labelled deterministic synthetic fallback.

AIService → selected GeminiProvider / GroqProvider → Pydantic output validation → LocalInsightProvider on failure.

The backend uses synchronous request handlers so blocking database/provider calls run outside the event loop. A bounded three-worker market pool refreshes prices without holding up the first screen. Yahoo refreshes are throttled to five minutes. Demo snapshots are returned immediately until a valid Yahoo result exists. Cached Yahoo quotes past the refresh window are marked stale. Stock detail shows quote date, retrieval time and source. No secrets are returned by the API. Passwords use PBKDF2-SHA256; sessions use random opaque tokens whose hashes are stored in SQLite and are issued in 12-hour HttpOnly, SameSite cookies. The database is migrated additively so existing single-user demo data is assigned to the built-in demo account.

## Directory structure

```text
backend/
  app/
    main.py                   REST routes, lifespan and CORS
    config.py                 .env loading and defaults
    database.py               SQLite engine and session lifecycle
    models.py                 Users, sessions, account-scoped holdings, transactions and watchlist
    auth.py                   Password hashing, session cookies and account lookup
    schemas.py                Decimal input and AI-output validation
    seed.py                   Idempotent first-run data
    services/
      market_data.py          Yahoo refresh, cache and offline universe
      portfolio_service.py    Atomic ledger and portfolio calculations
      analytics.py            Moving averages, momentum and volatility
      ai_service.py           Gemini, Groq and local analysis
  tests/test_api.py
  requirements.txt
  .env.example
  run.py
frontend/
  src/
    components/               Tables, charts, search, modal and AI panel
    pages/                    Overview, stocks and workspace pages
    hooks/useData.ts
    services/api.ts
    types/index.ts
    utils/format.ts
    App.tsx
    styles.css
  package.json
  package-lock.json
  vite.config.ts
```

For this minor project, REST routes are intentionally consolidated in main.py; business logic remains in services.

## Accounting and analytical methodology

- Investment = quantity × average price; value = quantity × latest price; unrealized P&L = value − investment; return = P&L / investment × 100.
- BUY uses weighted-average cost. SELL retains remaining average cost and records realized P&L. SQLite write reservation serializes trade read/update operations. Decimal input validation and Numeric database columns limit avoidable rounding; display values are formatted separately.
- Transactions must be entered chronologically for each symbol. Backdated entries before that symbol's latest transaction are rejected. Fees, tax lots, dividends, splits and brokerage reconciliation are outside scope.
- Closing/removing a holding explicitly records a full SELL at the latest available snapshot. The confirmation dialog explains this behavior; the ledger is retained.
- Day P&L uses latest versus previous daily close for current quantities. It does not calculate intraday cash-flow-adjusted performance.
- Portfolio history is a **current-holdings price illustration**, not actual historical portfolio performance. Historical cash flows are not reconstructed. Series align on common dates. 1D compares two daily closes; it does not claim intraday data.
- Volatility = sample standard deviation of log daily returns × sqrt(252). Momentum compares the latest close with approximately 20 sessions ago. Moving averages use 20 and 50 available daily observations.
- Risk score = min(100, 1.5 × value-weighted individual-stock volatility + 0.4 × largest stock weight + 0.2 × largest sector weight). Scores below 35 are Low, below 70 Moderate, otherwise High. This is a heuristic, not covariance-adjusted portfolio volatility.
- Diversification score = 100 minus the largest position percentage (zero for an empty portfolio). It does not account for cross-stock correlations.
- Alerts cover stock weight >30%, sector weight >40%, fewer than four holdings, stock volatility >30%, a holding contributing >50% of positive unrealized gains, and unrealized drawdown worse than −15%.
- AI confidence is a completeness indicator, not a probability of profit; local analysis uses a fixed illustrative score of 70.

## Data honesty and offline behavior

Synthetic quotes/fundamentals are labelled DEMO DATA. Yahoo is labelled DAILY / DELAYED with an as-of date on stock details, never guaranteed real-time. Missing Yahoo fundamentals show an em dash; synthetic fundamentals are not mixed into Yahoo snapshots. Index cards are explicitly synthetic. The stock universe is curated and limited to the supported 13 NSE equities. Featured stocks are curated, not asserted to be actual popularity rankings.

Demo history uses a symbol-derived random seed and closes at the displayed demo price. All prices and demo company fundamentals are illustrative, not verified current market facts. No internet is needed after dependencies are installed. The browser still requires the local backend process. A database seed marker prevents reseeding after users intentionally close all positions or clear the watchlist.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /api/health | Health check |
| POST | /api/auth/register | Create an account and sign in |
| POST | /api/auth/login | Sign in |
| POST | /api/auth/logout | End the current session |
| GET | /api/auth/me | Current account profile and demo cash balance |
| GET | /api/portfolio | Holdings |
| GET | /api/portfolio/summary | Totals, risk, allocations and story |
| GET | /api/portfolio/allocation | Stock and sector allocation |
| GET | /api/portfolio/history?period=1m | Current-holdings historical illustration |
| DELETE | /api/portfolio/{symbol} | Record a full closing sale |
| GET / POST | /api/transactions | Ledger / record trade |
| GET / POST | /api/watchlist | Read / add watched stock |
| DELETE | /api/watchlist/{symbol} | Remove watched stock |
| GET | /api/stocks/search?q=TCS | Offline-compatible symbol search |
| GET | /api/stocks/{symbol} | Quote and fundamentals |
| GET | /api/stocks/{symbol}/history?period=1m | Daily prices |
| GET | /api/stocks/{symbol}/analytics | Technical indicators |
| POST | /api/ai/analyze-stock/{symbol} | Structured stock analysis |
| POST | /api/ai/analyze-portfolio | Portfolio diagnosis |
| GET | /api/insights | Alerts and daily story |
| GET | /api/markets | Demo indices and stock snapshots |

Periods: 1d, 1w, 1m, 3m, 1y. Portfolio, order, watchlist, market and analysis routes require a signed-in session. CORS permits localhost:5173 and 127.0.0.1:5173 with credentials. API keys are backend-only. The app is intended to bind only to localhost.

## Demo workflow

1. Start both servers and sign in with the built-in demo account, or register your own account.
2. Inspect allocation, return and risk indicators.
3. Search TCS (Ctrl+K), open stock details and generate Aqua AI analysis.
4. Record a simulated BUY at the displayed quote (or an entered paper-trade price); review the reduced cash balance, updated holdings and transaction history.
5. Add a stock to the watchlist and remove another.
6. Open AI Insights and run Diagnose my portfolio.
7. Record a partial SELL and inspect proceeds, updated cash, and realized P&L.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm.cmd run build
```

Tests use a temporary SQLite database for endpoint data, force demo market mode, and disable real AI credentials. They cover health, portfolio mathematics, weighted-average buys, average-cost-preserving sells, oversized/invalid trades, watchlist deduplication, local and failed-provider AI, analytics, search, history, idempotent seed behavior, empty portfolios, backdated transactions and CORS. The app lifespan also exercises database startup against the isolated test engine.

## Screenshots

Placeholder: add screenshots of Overview, Stock Intelligence and Portfolio Doctor here after choosing your preferred window size and demo data.

## Disclaimer

AI-generated insights are for educational and analytical purposes only and are not financial advice.
#   A q u a V e s t - A I  
 