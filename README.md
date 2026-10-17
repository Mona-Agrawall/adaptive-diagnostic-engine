# Adaptive Diagnostic Engine

A computerized adaptive GRE diagnostic. The engine selects each question based on every previous answer, estimates the test-taker's ability with a two-parameter logistic (2PL) item response model, reports that estimate with an honest uncertainty interval, and turns the results into a study plan that cites the exact questions that were missed.

The project consists of a FastAPI backend with MongoDB persistence and a React single-page application. In production, the backend serves both the API and the built frontend from one process.

## The problem

Fixed-form practice tests spend most of their questions on items that are far too easy or far too hard for the person taking them, so they reveal little about where that person actually stands. Adaptive testing addresses this by choosing the most informative question at each step. Most practice tools also report a single score without saying how certain it is, and they rarely connect the score to concrete next steps.

This application:

- estimates ability in 10 to 20 questions by adapting to each answer,
- shows the estimate together with a 95% interval and a plain-language interpretation,
- breaks results down by topic and warns when a topic has too few items to judge,
- generates a study plan grounded in the missed questions, using an LLM when one is configured and a deterministic rule-based plan otherwise.

## Key features

| Area | What it does |
|------|--------------|
| Adaptive engine | 2PL item response model, expected a posteriori (EAP) ability estimation, maximum-information item selection with topic balancing and randomesque exposure control |
| Stopping rules | Ends at the chosen maximum length, or earlier once the standard error reaches the precision target, or when the selected topics run out of items |
| Answer integrity | Only the currently served question can be answered, exactly once, with a valid option. Concurrent submissions are resolved atomically. The answer key is never sent before an answer is accepted |
| Results | Ability band, estimate and interval, accuracy, time spent, per-topic estimates, estimate trajectory chart, and a full question review with explanations |
| Study plan | AI-generated (Groq) with strict output validation, or rule-based fallback. Cached per assessment, rate limited, and with a bounded number of AI attempts |
| History | Assessments started in a browser are listed with status, results, and whether the change from the previous attempt exceeds measurement error |
| Export | Completed results download as JSON; the results page has a print-friendly layout |
| Operations | Health endpoint that separates app, database, and AI status; idempotent seeding; Docker image and Compose stack; CI on every push |

## Technology stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, FastAPI, Pydantic v2, pydantic-settings, Uvicorn |
| Database | MongoDB (local server, Docker, or Atlas) through PyMongo |
| AI provider | Groq API, default model `openai/gpt-oss-120b` (optional) |
| Frontend | React 19, React Router 7, TypeScript, Vite 7, plain CSS with design tokens |
| Testing | pytest, Vitest, Testing Library, Playwright |
| Quality | Ruff (lint and format), mypy (strict), ESLint, Prettier, TypeScript strict mode |
| Delivery | Multi-stage Dockerfile, Docker Compose, GitHub Actions |

## System architecture

The browser loads the single-page application from the FastAPI process and talks to it through a JSON API under `/api`. Route handlers in `api.py` are thin: they validate input with Pydantic schemas and delegate to the service layer.

`AssessmentService` in `assessment.py` owns the assessment lifecycle. On creation it validates the requested topics against the question bank, picks the first item, and stores an assessment document that embeds a snapshot of the served question, including its answer key. When an answer arrives, the service checks that it targets the currently served question, grades it against the snapshot, re-estimates ability over all responses with the functions in `irt.py`, decides whether to stop with `selection.py`, picks the next item if needed, and writes all of that in one conditional `update_one`. Because the update is filtered on the document version, status, and current question ID, two racing requests can never both succeed.

Study plans are produced by `study_plan.py`. The service first builds the results view. If a Groq key is configured, it reserves one of a limited number of AI attempts atomically, sends only server-side data to the model, and validates the JSON it returns against the real results. Any failure falls back to a rule-based plan. Plans are cached on the assessment document.

Configuration is centralized in `config.py` and validated at startup. The MongoDB client is created lazily, so the application starts and reports a degraded health status even when the database is unreachable, instead of crashing.

## Repository structure

```
backend/
    app/
        main.py            Application factory, lifecycle, security headers, SPA serving
        api.py             HTTP routes
        schemas.py         Request and response models
        assessment.py      Assessment lifecycle and results
        irt.py             2PL model, EAP estimation, ability bands
        selection.py       Item selection and stopping rules
        study_plan.py      Groq provider, output validation, rule-based fallback
        question_bank.py   Question file schema and idempotent seeding
        db.py              MongoDB connection and indexes
        config.py          Typed settings
        errors.py          Error types and the JSON error envelope
        rate_limit.py      Per-client sliding-window limiter
        seed.py            Seeding command-line entry point
    data/questions.json    Question bank (55 items, 5 topics)
    tests/                 pytest suite
    pyproject.toml         Ruff, mypy, and pytest configuration
    requirements.txt
    requirements-dev.txt
frontend/
    src/
        api/               Typed API client and response types
        components/        Layout, charts, review, study plan, feedback states
        pages/             Landing, setup, assessment, results, history
        lib/               Formatting, local history store, data-loading hook
        styles/global.css  Design tokens, light and dark themes, print styles
        test/              Vitest and Testing Library tests
    e2e/                   Playwright end-to-end tests
    package.json
.github/workflows/ci.yml
Dockerfile
docker-compose.yml
.env.example
```

## Prerequisites

- Python 3.12 or newer
- Node.js 20.19 or newer (22 LTS recommended)
- MongoDB 6 or newer, running locally, in Docker, or on Atlas
- Optional: a Groq API key for AI study plans
- Optional: Docker for the containerized setup

## Installation

### Option A: Docker Compose (fastest)

```bash
git clone https://github.com/Mona-Agrawall/adaptive-diagnostic-engine.git
cd adaptive-diagnostic-engine
docker compose up --build
```

Open http://localhost:8000. Compose starts MongoDB, builds the frontend, seeds the question bank, and serves everything on port 8000. To enable AI study plans, create a `.env` file containing `GROQ_API_KEY=...` before running the command.

### Option B: Local development

```bash
git clone https://github.com/Mona-Agrawall/adaptive-diagnostic-engine.git
cd adaptive-diagnostic-engine
cp .env.example .env            # then edit MONGODB_URI and, optionally, GROQ_API_KEY

python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt

cd frontend
npm ci
cd ..
```

## Environment variables

Settings are read from the environment and from `.env` in the repository root. Environment variables take precedence over the file.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URI` | Yes | none | MongoDB connection string, `mongodb://` or `mongodb+srv://` |
| `DB_NAME` | No | `adaptive_diagnostic` | Database name |
| `SEED_ON_STARTUP` | No | `false` | Upsert the question bank when the server starts |
| `MONGODB_TIMEOUT_MS` | No | `5000` | Server selection and connect timeout |
| `GROQ_API_KEY` | No | empty | Enables AI study plans when set |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model ID |
| `AI_TIMEOUT_SECONDS` | No | `20` | Per-request timeout for the AI provider |
| `AI_MAX_RETRIES` | No | `1` | Automatic retries for transient provider errors |
| `STUDY_PLAN_MAX_AI_ATTEMPTS` | No | `3` | AI generation attempts allowed per assessment |
| `ASSESSMENT_TTL_MINUTES` | No | `120` | Inactivity period after which an unfinished assessment expires |
| `SE_TARGET` | No | `0.40` | Standard error at which the assessment may stop early |
| `MIN_QUESTIONS` | No | `6` | Questions required before the precision rule can stop a test |
| `RATE_LIMIT_CREATE_PER_MINUTE` | No | `30` | Assessment creations per client address per minute |
| `RATE_LIMIT_ANSWER_PER_MINUTE` | No | `300` | Answer submissions per client address per minute |
| `RATE_LIMIT_STUDY_PLAN_PER_MINUTE` | No | `6` | Study plan requests per client address per minute |
| `CORS_ORIGINS` | No | empty | Comma-separated origins; only needed if the frontend is hosted elsewhere |
| `SERVE_FRONTEND` | No | `true` | Serve `frontend/dist` from the backend when it exists |
| `FRONTEND_DIST` | No | `frontend/dist` | Location of the built frontend |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

If a required value is missing or invalid, startup stops with a message naming the variable, without echoing its value.

## Database setup and seeding

The application uses three collections: `question_bank`, `topics`, and `assessments`. Indexes (unique `question_id`, unique topic `name`, and supporting indexes) are created automatically on first use.

Seed or update the question bank from the `backend` directory:

```bash
cd backend
python -m app.seed            # validate backend/data/questions.json and upsert it
python -m app.seed --check    # validate the file only, without touching the database
```

Seeding is idempotent and non-destructive:

- Every item is upserted by its stable ID (for example `alg-004`). Running the command again with an unchanged file reports zero changes.
- Edited items are updated in place. Nothing is ever deleted.
- To retire an item, set `"active": false` in the file and seed again.
- Assessments store a snapshot of every question they served, so editing or retiring items never changes existing results and never breaks an assessment in progress.

Collections from the previous version of the project (`questions`, `user_sessions`) are not read or modified.

### Adding questions

Add an entry to `backend/data/questions.json` with a new ID following the `xxx-000` pattern, then run `python -m app.seed --check` followed by `python -m app.seed`. The file is validated with Pydantic. Validation rejects duplicate IDs, undeclared topics, out-of-range answer indexes, duplicate options, and item parameters outside `0.2 <= a <= 3.0` and `-3.5 <= b <= 3.5`.

## Running the application

Production-style, with one process serving the API and the built frontend:

```bash
cd frontend && npm run build && cd ..
cd backend
uvicorn app.main:create_app --factory --port 8000
```

Open http://127.0.0.1:8000. Interactive API documentation is at http://127.0.0.1:8000/docs.

Development, with hot reload for both parts:

```bash
# Terminal 1
cd backend
uvicorn app.main:create_app --factory --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/docs` to the backend.

## Testing and quality checks

Backend tests need a running MongoDB. They connect to `mongodb://localhost:27017` by default (override with `TEST_MONGODB_URI`), use a throwaway database named `ade_test_<random>`, and drop it afterwards. They never read `.env` or touch real data.

```bash
cd backend
pytest                  # 125 tests: unit, integration, concurrency, Monte Carlo simulation
ruff check .
ruff format --check .
mypy                    # strict mode

cd ../frontend
npm test                # 34 Vitest and Testing Library tests
npm run lint
npm run typecheck
npm run format:check
npm run build
```

End-to-end tests run against a live server that serves the production build:

```bash
cd frontend && npm run build && npx playwright install chromium && cd ..
cd backend
MONGODB_URI=mongodb://localhost:27017 DB_NAME=ade_e2e SEED_ON_STARTUP=true \
  RATE_LIMIT_CREATE_PER_MINUTE=1000 uvicorn app.main:create_app --factory --port 8000
# In another terminal:
cd frontend && npm run e2e
```

The Playwright suite covers:

- the full flow from the landing page through setup, adaptive questions, results, study plan, evidence links, and history,
- duplicate-submit prevention,
- recovery from a network failure,
- resuming after a reload,
- keyboard-only answering,
- validation and not-found states,
- confirmation before clearing history,
- the absence of horizontal scrolling at phone width.

The GitHub Actions workflow runs all of the above, plus a Docker image build, on every push and pull request.

## API reference

All endpoints are under `/api`. The OpenAPI schema is served at `/openapi.json`, with interactive documentation at `/docs`.

| Method | Path | Description | Notable errors |
|--------|------|-------------|----------------|
| GET | `/api/health` | App, database, and AI status | none (always 200; `status` is `degraded` if the database is down) |
| GET | `/api/topics` | Active topics with question counts | 503 |
| POST | `/api/assessments` | Start an assessment. Body: `{"topics": [...], "max_questions": 10 or 15 or 20}`. Returns the first question | 422 `unknown_topic`, 429 |
| GET | `/api/assessments/{id}` | Current state and the question awaiting an answer. Safe to repeat | 404 |
| POST | `/api/assessments/{id}/answers` | Body: `{"question_id": "...", "option_index": n}`. Returns feedback and the next state | 409 `question_not_current`, `already_answered`, `assessment_completed`, `conflict`; 410 `assessment_expired`; 422 `invalid_option`; 429 |
| GET | `/api/assessments/{id}/results` | Results of a completed assessment | 409 `assessment_not_completed`, 410 |
| GET | `/api/assessments/{id}/export` | Results as a downloadable JSON file | same as results |
| POST | `/api/assessments/{id}/study-plan` | Return the cached plan or generate one | 409, 410, 429 |

Every error uses the same envelope:

```json
{"error": {"code": "already_answered", "message": "This question has already been answered."}}
```

Validation errors add a `details` array of `{field, message}` objects. Unexpected errors return `internal_error` without a stack trace. Database outages return 503 `database_unavailable`.

### Changes from version 1

The original endpoints (`/start-session`, `/next-question`, `/submit-answer`, `/study-plan`) were replaced because their contract could not be made safe. They accepted any question ID and free-text answers, and the server kept no record of which question it had served, so answers could not be tied to the question actually shown. The new endpoints are listed above.

## Adaptive scoring model

### Item response model

Each item has a difficulty `b` and a discrimination `a`. Under the two-parameter logistic model, the probability that a person with ability `θ` answers correctly is

```
P(correct | θ) = 1 / (1 + exp(-a (θ - b)))
```

`θ` is on the logit scale, where 0 is the middle of the bank's difficulty range and most people fall between -2 and +2. Higher `a` means the item separates nearby ability levels more sharply.

### Ability estimation

After each answer, ability is re-estimated from all responses using the expected a posteriori (EAP) method:

- **Prior.** A standard normal prior, `θ ~ N(0, 1)`. Every assessment starts at `θ = 0` with a standard error of 1.
- **Posterior.** The posterior is evaluated on a fixed grid from -4 to +4 in steps of 0.05. The computation works in log space, using a numerically stable log-sigmoid and normalization against the maximum, so it never overflows.
- **Estimate.** The reported ability is the posterior mean. The standard error is the posterior standard deviation, and the 95% interval is `θ ± 1.96 × SE`, clipped to the grid.
- **Extreme patterns.** The prior keeps estimates finite and sensible for all-correct and all-incorrect patterns, where maximum likelihood estimation would diverge.

Ability bands are fixed cut points on the scale: Foundational below -1, Developing from -1 to 0, Proficient from 0 to 1, and Advanced above 1.

Per-topic estimates use the same method with only that topic's responses. They are marked "Limited data" when fewer than three items were seen.

### Question selection

1. **Content balancing.** Restrict candidates to the selected topics that have been administered the fewest times and still have unused items.
2. **Maximum information.** Rank those items by Fisher information at the current estimate, `I(θ) = a² P(θ) (1 - P(θ))`, which peaks at items whose difficulty is closest to the current estimate.
3. **Randomesque exposure control.** Choose uniformly among the top three, so every test-taker does not see the identical sequence.

An item is never served twice within an assessment.

### Stopping rules

An assessment completes when the first of these applies:

| Rule | Condition |
|------|-----------|
| `max_questions` | The chosen length (10, 15, or 20) has been reached |
| `precision_reached` | At least `MIN_QUESTIONS` answered and `SE <= SE_TARGET` (default 0.40) |
| `item_bank_exhausted` | No unused active items remain in the selected topics |

### Validation

`backend/tests/test_simulation.py` simulates students with known abilities answering the real bank under the model. It checks four things:

- Mean estimates increase monotonically from true ability -2 to +2 and span more than 2.5 logits.
- RMSE stays below 0.8 and the correlation with true ability exceeds 0.85.
- At least 85% of nominal 95% intervals contain the true value.
- Every topic is covered and no item repeats.

For comparison, the previous update rule could only move a perfect scorer from 0.5 to 0.73, and a student who missed everything to 0.27.

### Limitations of the model

The item parameters in `questions.json` are provisional expert estimates. They have not been calibrated from real response data, so estimates are internally consistent but not linked to official GRE scores or to any population. The simulations verify the algorithm's behavior under the model; they cannot verify the parameters themselves. Calibrating the bank requires collecting responses and fitting the 2PL model (for example with marginal maximum likelihood), then updating `a` and `b`. With 10 to 12 items per topic, topic-level estimates remain imprecise.

## AI study plans

When a completed assessment requests a plan:

1. A cached AI plan is returned immediately if one exists.
2. If no Groq key is configured, a rule-based plan is generated and cached.
3. Otherwise, one AI attempt is reserved atomically. The per-assessment budget is `STUDY_PLAN_MAX_AI_ATTEMPTS`.
4. The model receives a JSON payload with the assessed topics, overall and per-topic statistics, and the missed questions (stem, topic, and concept tags). It is asked to return JSON, and Groq's JSON mode is enabled.
5. The response is parsed and validated:
   - 2 to 4 steps, with bounded text lengths.
   - Each step must name an assessed topic or "All topics".
   - Evidence positions are filtered to questions that were actually missed.
   - Invalid steps are dropped. If none remain, the attempt counts as a failure.
6. On timeout, an API error, or invalid output, a rule-based plan is returned with a notice. It is stored but not treated as final, so a later request can try the AI again while the attempt budget lasts.

The rule-based plan ranks topics by estimate, builds a step for each of the three weakest topics with misses (concepts to review, questions to rework, practice volume at a suitable difficulty), and adds a retest step.

AI output is stored separately from responses and scores and is never used for grading.

## Error handling and fallback behavior

| Situation | Behavior |
|-----------|----------|
| Database unreachable at startup | The app starts; health reports `degraded`; data endpoints return 503 until the database recovers |
| Database error during a request | 503 `database_unavailable`; the driver message is logged by type only |
| AI key missing | Everything works; study plans are rule-based |
| AI timeout, error, or malformed output | Rule-based plan with an explanatory notice and a retry option |
| Duplicate or concurrent answer | Exactly one is accepted; others get 409 and the UI reloads the current question |
| Network failure in the browser | The answer stays selected and a "Try again" button resubmits it |
| Page reload mid-assessment | The current question is restored from the server |
| Inactive assessment | Expires after `ASSESSMENT_TTL_MINUTES`; answers return 410 |
| Unknown client-side route | The SPA shows a "Page not found" page; unknown `/api` paths return a JSON 404 |

## Security considerations

- **Secrets.** Secrets are loaded from the environment or an untracked `.env` and held as `SecretStr`, so they never appear in logs, settings representations, or configuration error messages. `.gitignore` excludes `.env`, virtual environments, and build output.
- **Answer integrity.**
  - The server tracks the current question for each assessment.
  - Answers for any other question are rejected, and option indexes are validated against that question's options.
  - Correctness, scores, and stopping decisions are computed only on the server.
  - The answer key and item parameters are never included in responses before an answer is accepted.
- **Concurrency.** State changes are conditional single-document updates guarded by a version number, which makes them atomic in MongoDB.
- **Identity and ownership.**
  - There are no accounts. An assessment ID is a random UUID (122 random bits) that works as a bearer link: anyone who has it can view that assessment.
  - The server never lists assessments, so IDs cannot be enumerated.
  - Browser history is stored locally and is clearly labelled as such.
- **Prompt injection.** Students choose from fixed options and cannot submit free text, so no user-written text reaches the model. The system prompt also tells the model to treat the payload as data, and the output is validated before use.
- **Abuse controls.** Creation, answers, and study plans each have their own per-client rate limits, and AI calls have a per-assessment attempt budget. These limits are in-memory and apply per process; multi-replica deployments should enforce limits at the proxy.
- **HTTP hardening.**
  - Responses carry `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` headers.
  - API responses are marked `no-store`.
  - CORS is disabled unless origins are configured.
- **Container.** The Docker image runs as a non-root user.

## Deployment

The Docker image is self-contained: it builds the frontend and serves it with the API on port 8000.

```bash
docker build -t adaptive-diagnostic-engine .
docker run -p 8000:8000 \
  -e MONGODB_URI="mongodb+srv://<user>:<password>@<cluster>/" \
  -e DB_NAME=adaptive_diagnostic \
  -e SEED_ON_STARTUP=true \
  -e GROQ_API_KEY="<optional>" \
  adaptive-diagnostic-engine
```

This works on any container platform, such as Render, Railway, Fly.io, Google Cloud Run, or Azure Container Apps. Point `MONGODB_URI` at a managed MongoDB such as Atlas and allow the platform's egress addresses in the Atlas network access list. Run a single replica, or move rate limiting to the proxy layer. The image's `HEALTHCHECK` and the `/api/health` endpoint can serve as the platform health check.

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `Invalid configuration (MONGODB_URI: Field required ...)` | `.env` is missing or not in the repository root. Copy `.env.example` to `.env` |
| Health shows `"database": {"status": "down"}` | MongoDB is not reachable. Check that the server is running, the URI is correct, and, for Atlas, that your IP is in the network access list and the cluster still exists |
| `The DNS query name does not exist: _mongodb._tcp...` | The `mongodb+srv` cluster hostname no longer resolves. The cluster was deleted or the hostname is wrong. Copy a fresh connection string from Atlas |
| The setup page shows no topics | The question bank has not been seeded. Run `python -m app.seed` or set `SEED_ON_STARTUP=true` |
| Study plans always say "rule-based" | `GROQ_API_KEY` is not set, or the provider is failing. Check the server log for `Study plan AI generation failed` |
| AI fails with `model_not_found` | Groq retires models periodically. Set `GROQ_MODEL` to a model listed in the Groq console |
| `pytest` exits with "MongoDB is required" | Start a local MongoDB or set `TEST_MONGODB_URI` |
| `http://127.0.0.1:8000` shows JSON 404 at `/` | The frontend has not been built. Run `npm run build` in `frontend` |
| 429 responses during manual testing | Raise the `RATE_LIMIT_*` settings for local use |

## Known limitations

- Item parameters are uncalibrated, and the bank is small (55 items). Estimates are diagnostic indications, not predictions of GRE scores.
- There are no user accounts. History is stored per browser, and results are accessible to anyone with the link.
- Rate limits are per process and in memory.
- The GRE verbal section is represented only by vocabulary and sentence-completion items. Reading comprehension is not included.

## Future work

- Calibrate item parameters from collected responses, and add item-fit and exposure reporting.
- Optional accounts, so history follows a user across devices and results are private by default.
- Reading-comprehension items with shared passages, which require a testlet-aware model.
- A small authoring interface for the question bank, backed by the same validation as the seed command.

## License

MIT. See [LICENSE](LICENSE).

## Author

Mona Agrawal
