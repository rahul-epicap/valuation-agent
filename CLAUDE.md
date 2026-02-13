# Claude Code Protocols & Team Standards

This file defines the strict rules, workflows, and context you must follow when working in this repository.

## 1. Project Context

**Project:** Epicenter Valuation Dashboard
**Description:** Web-based dashboard that performs regression-based valuation analysis across ~244 tickers over monthly data from 2015–2026. Regresses valuation multiples (EV/Revenue, EV/Gross Profit, Price/EPS) against growth rates to visualize how the market prices growth, and how that relationship evolves over time. Users upload Excel files with Bloomberg data; the backend parses them into dashboard JSON stored in PostgreSQL.

### Tech Stack
* **Backend:** Python 3.11+ with FastAPI
* **Database:** PostgreSQL (Railway managed)
* **Frontend:** Next.js 14 + React 18 + TypeScript + Chart.js (via react-chartjs-2)
* **Styling:** Tailwind CSS
* **Excel Parsing:** openpyxl
* **Hosting:** Railway (single service — FastAPI serves API + static frontend build)

### Critical Commands
* **Run Backend Dev Server:** `cd backend && uvicorn app.main:app --reload`
* **Run Frontend Dev Server:** `cd frontend && npm run dev`
* **Run Tests:** `cd backend && pytest` / `cd frontend && npm run test`
* **Lint/Format Backend:** `cd backend && ruff check . && ruff format .`
* **Lint/Format Frontend:** `cd frontend && npm run lint`
* **Build Frontend:** `cd frontend && npm run build`
* **Type Check:** `cd frontend && npm run typecheck`

---

## 2. Interaction Workflow
Follow this "Plan-Code-Verify" loop for every complex request:

1. **Exploration:** Search for relevant files first. Do not hallucinate file paths.
2. **Planning:** Propose a high-level plan (steps to take) before generating code.
3. **Execution:** Write code iteratively.
4. **Verification:**
   * ALWAYS run the linter/type-checker after applying changes.
   * If a build error occurs, attempt to fix it, but stop after 2 failed attempts and ask for guidance.
   * Create a test case for new logic/features.

---

## 3. Git & Version Control Standards

### Branching Strategy
* **Feature:** `feat/[kebab-case-description]`
* **Bug Fix:** `fix/[kebab-case-description]`
* **Refactor:** `refactor/[kebab-case-description]`
* **AI Sandbox:** `ai/[kebab-case-description]` (For experimental AI generation)
* **Rule:** Never commit directly to `main` or `master`.

### Commit Message Convention (Conventional Commits)
Format: `<type>(<scope>): <description>`

**Types:**
* `feat`: New feature for the user.
* `fix`: Bug fix.
* `docs`: Documentation only.
* `style`: Formatting (white-space, etc).
* `refactor`: Code change that neither fixes a bug nor adds a feature.
* `test`: Adding/correcting tests.
* `chore`: Build/tooling changes.

**Scopes:**
* `backend`: Python/FastAPI backend changes
* `frontend`: React/TypeScript frontend changes
* `db`: Database schema or migrations
* `parser`: Excel parsing pipeline
* `charts`: Visualization/charting components
* `api`: API endpoints

**Rules:**
* **Imperative Mood:** "Add user login" (not "Added").
* **Length:** Subject line < 50 chars. Body wrapped at 72 chars.
* **No Secrets:** Scan diffs for API keys/tokens before committing.
* **Lockfiles:** Always include lockfile updates if dependencies change.

### Pull Request (PR) Descriptions
When drafting a PR description, include:
1. **Summary:** What changed?
2. **AI Contribution:** Explicitly state what was AI-generated vs. Human-edited.
3. **Verification:** Proof of testing (e.g., "Passes local tests," "Verified manually in UI").

---

## 4. Code Quality Standards

### General Rules
* **No Any/Unknown:** Avoid `any` in TypeScript. Use proper types.
* **Comments:** Comment *why*, not *what*. Explanation is for complex logic only.
* **Error Handling:** No empty catch blocks. Always log or handle errors.
* **Configuration:** No hardcoded config/secrets. Use environment variables.

### Python/FastAPI Specific
* Follow PEP8. Use type hints for all function arguments and returns.
* Use Pydantic models for request/response validation.
* Use dependency injection for database sessions.
* Async functions for I/O-bound operations.

### React/TypeScript Specific
* Use Functional Components and Hooks. Avoid Class components.
* Use TypeScript interfaces for props and state.
* Keep components small and focused (< 200 lines).
* Use `useMemo` for expensive computations (regression, filtering).

### Database
* Use SQLAlchemy ORM with proper typing.
* JSONB for dashboard data storage (single `snapshots` table).

### API Design
* Follow RESTful conventions.
* Use standard HTTP status codes.
* Consistent error response format: `{ "error": { "code": "...", "message": "..." } }`

---

## 5. Prohibited Patterns
* Do not remove existing comments unless the code they describe is deleted.
* Do not change code style (tabs vs spaces, quotes) unless using the project's auto-formatter.
* Do not introduce circular dependencies.
* Do not store credentials in code or commit `.env` files.

---

## 6. Project Structure
```
valuation-agent/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, static mount, lifespan
│   │   ├── config.py            # Settings (DATABASE_URL etc.)
│   │   ├── db.py                # SQLAlchemy async engine + session
│   │   ├── models.py            # Snapshot ORM model
│   │   ├── routes/
│   │   │   ├── upload.py        # POST /api/upload
│   │   │   ├── dashboard.py     # GET /api/dashboard-data, /api/snapshots
│   │   │   └── template.py      # GET /api/template
│   │   ├── services/
│   │   │   └── excel_parser.py  # Excel → dashboard JSON transform
│   │   └── template/
│   │       └── template.xlsx    # Downloadable blank template
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx         # Main dashboard page
│   │   │   └── globals.css      # Tailwind + dark theme CSS vars
│   │   ├── lib/
│   │   │   ├── api.ts           # Fetch wrappers
│   │   │   ├── regression.ts    # Port of lr() function
│   │   │   ├── filters.ts      # Port of filt(), filtMults(), okEps(), aTk()
│   │   │   └── types.ts         # TypeScript interfaces
│   │   ├── hooks/
│   │   │   └── useDashboardState.ts  # All dashboard state (replaces S object)
│   │   └── components/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       ├── IndustryFilter.tsx
│   │       ├── TickerHighlight.tsx
│   │       ├── TickerExclusions.tsx
│   │       ├── ChartCard.tsx
│   │       ├── RegressionChart.tsx
│   │       ├── MultiplesChart.tsx
│   │       ├── SlopeChart.tsx
│   │       ├── RegressionStats.tsx
│   │       ├── MetricToggle.tsx
│   │       ├── UploadModal.tsx
│   │       └── SnapshotSelector.tsx
├── docker-compose.yml           # Local dev (backend + frontend + postgres)
└── railway.toml
```

---

## 7. Domain Knowledge

### Data Schema (Dashboard JSON)
```
{
  dates: string[]              // Monthly dates "2015-01-01" through latest
  tickers: string[]            // Stock tickers (~244)
  industries: {ticker: string} // Maps each ticker to its industry (~42 unique)
  fm: {                        // Financial metrics, keyed by ticker
    [ticker]: {
      er: number[]             // EV / Forward Revenue
      eg: number[]             // EV / Forward Gross Profit
      pe: number[]             // Price / Forward EPS
      rg: number[]             // Revenue growth (decimal, e.g. 0.05 = 5%)
      xg: number[]             // EPS growth (decimal)
      fe: number[]             // Forward EPS (absolute $)
    }
  }
}
```
Values can be `null` when data is unavailable for a ticker/date pair.

### Key Metric Mappings
- `MK`: metric type → multiple key (`evRev→er`, `evGP→eg`, `pEPS→pe`)
- `GK`: metric type → growth key (`evRev→rg`, `evGP→rg`, `pEPS→xg`)
- `CC`: metric type → color scheme (blue for EV/Rev, amber for EV/GP, green for P/EPS)
- `HC`: 8 highlight colors for individually selected tickers

### Outlier Caps (hardcoded in filter logic)
- EV/Revenue: exclude if > 80x
- EV/Gross Profit: exclude if > 120x
- Price/EPS: exclude if > 200x
- EPS growth: exclude if ≤ 2% or > 150% (when cap on)
- Forward EPS: exclude if ≤ $0.50

### Three Visualizations
1. **Regression Scatter** — Plots valuation multiple (Y) vs. growth rate (X) for selected date. Grey dots = normal, colored triangles = highlighted tickers. Dashed regression line. Stats row shows R², slope, intercept, N, date.
2. **Multiples Over Time** — Average (dashed grey) and top-quartile (colored, filled) multiples across all dates. Highlighted tickers overlaid as individual lines.
3. **Slope Over Time** — Regression slope at each date, showing how the market's growth premium has evolved.

### Excel Sheet → Metric Mapping
| Sheet Name | Metric Key | Notes |
|-----------|------------|-------|
| `EV - Rev` | `er` | Ratio sheet (data starts row 8) |
| `EV - GP` | `eg` | Ratio sheet |
| `PE` | `pe` | New sheet |
| `Rev Growth` | `rg` | Raw sheet (data starts row 9) |
| `EPS Growth` | `xg` | New sheet |
| `Forward EPS` | `fe` | New sheet |
| `Industries` | — | Two-column (Ticker, Industry) lookup |

### Database Schema
```sql
CREATE TABLE snapshots (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dashboard_data  JSONB NOT NULL,
    source_filename VARCHAR(255),
    ticker_count    INTEGER,
    date_count      INTEGER,
    industry_count  INTEGER
);
```

### API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/snapshots` | List all snapshots (metadata only) |
| GET | `/api/dashboard-data` | Latest snapshot's full JSON |
| GET | `/api/dashboard-data/{id}` | Specific snapshot's JSON |
| POST | `/api/upload` | Upload Excel, parse, store as new snapshot |
| GET | `/api/template` | Download blank Excel template |

---

## 8. Environment Variables
Required environment variables (never commit actual values):
```
# Backend
DATABASE_URL=postgresql://...

# Frontend (build-time)
NEXT_PUBLIC_API_URL=...
```

---

## 9. Reference Files
- `Epicenter Valuation Dashboard_020426 (1).html` — Original single-file dashboard with all business logic to port (lines 157–391)
- `Simple Regression Analysis_Dashboard Data_v2.xlsx` — Defines exact Excel layout the parser must handle
