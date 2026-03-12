# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack
- Backend: Python + FastAPI
- Templating: Jinja2
- Styling: Tailwind CSS via CDN (no build step)
- JS: Vanilla JS only — no React, no Vue, no heavy frameworks
- Charts: Chart.js via CDN
- Database: SQLite locally, PostgreSQL on Render
- Auth: JWT tokens in httpOnly cookies (7-day expiry)

## Development Commands

```bash
# Activate virtualenv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (Alembic)
alembic upgrade head

# Seed exercise library + example program
python seed.py

# Start dev server
uvicorn app.main:app --reload
```

App runs at http://127.0.0.1:8000. Copy `.env.example` → `.env` and set `SECRET_KEY` before first run.

## Architecture

### Request Flow
All routes use two FastAPI dependencies: `get_current_user` (raises 401 → redirects to login) and `get_db` (yields SQLAlchemy session). Routes return `TemplateResponse` for page renders or `RedirectResponse` for mutations.

### Data Model
The core hierarchy is: **Program → Block → TrainingDay → PlannedSet** (the template). When a user starts a program, a **ProgramRun** is created and **ScheduledWorkouts** are generated for each day. Logging a session creates **CompletedSets** that reference both the ScheduledWorkout and the PlannedSet.

**1RM resolution for percentage-based sets:** `PlannedSet.intensity_type = "percentage"` → look up `OneRepMax` for the exercise. If `Exercise.reference_exercise_id` is set, use that exercise's 1RM instead (e.g. Tempo Squat → Squat). The `calculate_weight()` helper in `app/utils.py` handles the rounding.

**Soft deletes:** Programs and exercises use `is_archived` flags. `Program.is_draft = True` means the builder wizard hasn't been confirmed yet.

### Key Files
| File | Purpose |
|------|---------|
| `app/main.py` | App entry, homepage route, router registration |
| `app/models.py` | All SQLAlchemy models |
| `app/auth.py` | JWT creation/decode, `get_current_user` / `get_optional_user` dependencies |
| `app/database.py` | SQLite↔PostgreSQL switch via `DATABASE_URL` env var |
| `app/migrations.py` | Lightweight idempotent startup migrations (for post-Alembic column adds) |
| `app/utils.py` | `calculate_weight()` and `round_weight()` — rounding increment is 1.25 kg |
| `app/services/ai_service.py` | Stub for Anthropic AI integration |
| `app/templates/base.html` | Base layout with nav (bottom bar mobile / sidebar desktop) |

### Router Summary
- `/auth` — register, login, logout
- `/programs` — program builder wizard, list, CRUD
- `/workouts` — today's workout view, set completion
- `/prs` — 1RM management
- `/calendar` — schedule view, reschedule, skip
- `/exercises` — exercise library, custom exercises
- `/progress` — sparklines, accessory bests
- `/volume` — volume analytics
- `/dashboard` — stats overview
- `/ai` — AI endpoints (future)

## Frontend Rules
- Dark mode throughout — background `#111827` (gray-900), cards `#1f2937` (gray-800)
- Mobile-first using Tailwind responsive prefixes (`md:`, `lg:`)
- On mobile (< 1024px): bottom navigation bar, Today's Workout as homepage
- On desktop (>= 1024px): left sidebar navigation, dashboard as homepage
- Large tap targets on all buttons — minimum `h-12` on mobile
- Read `.claude/skills/frontend-design/SKILL.md` before building any UI

## Code Rules
- Always use Python type hints
- All DB queries must be scoped to the logged-in `user_id` — never leak data between users
- Never hard-delete training history — use `is_archived` flags instead
- Weights always rounded to nearest 1.25 kg via `round_weight()` in `app/utils.py` (CLAUDE.md says 2.5 kg but code uses 1.25 kg — follow the code)
- Environment variables for all secrets

## Workflow
- Ask before starting each new phase
- Go slow on any external service setup (Render, PostgreSQL, GitHub)
- Explain each step before doing it
- Wait for confirmation that each step worked before moving to the next
