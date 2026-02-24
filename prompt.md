# Claude Code Prompt: PowerBuilding Workout Tracker App

## Project Overview

Build a full-stack web application for tracking strength training programs, with a focus on automatically calculating weights from percentages of 1RM. The app should be mobile-friendly, multi-user ready, and deployable for free on Render.com.

---

## Tech Stack

- **Backend:** Python with FastAPI
- **Database:** SQLite (local dev) → PostgreSQL (Render free tier in production)
- **ORM:** SQLAlchemy with Alembic for migrations
- **Frontend:** Jinja2 templates + Tailwind CSS (via CDN) + vanilla JS (keep it simple, no heavy frameworks)
- **Auth:** FastAPI-Users or simple JWT-based auth (email + password login)
- **Hosting:** Render.com free tier (include a `render.yaml` config file and instructions)
- **Rounding:** All calculated weights round to nearest 2.5kg

---

## Core Data Models

### User
- id, email, hashed_password, display_name, created_at
- is_admin flag (for future use)

### Exercise
- id, name, category (enum: `main_lift` | `accessory`)
- Main lifts: Squat, Bench Press, Deadlift (these are used in 1RM calculations)
- Users can add custom exercises

### OneRepMax
- id, user_id, exercise_id, weight_kg (float), date_set
- Multiple entries per exercise to track history over time
- The most recent entry is the "current" 1RM

### Program
- id, creator_user_id, name, description, is_public (bool, for future sharing)
- A program is a template — it has no dates, just structure

### Block
- id, program_id, block_number (int), name (e.g. "Block 1" or "Deload")
- Blocks are ordered within a program
- A block does NOT equal a week — it's just a collection of training days

### TrainingDay (within a Block)
- id, block_id, day_number (int), name (optional, e.g. "Day 1 - Squat focus")

### PlannedSet
- id, training_day_id, exercise_id, order (int)
- set_number (int), reps (int), intensity_type (enum: `percentage` | `rpe` | `freeform`)
- intensity_value (float, nullable) — e.g. 88.0 for 88%, or 8.0 for RPE 8
- For accessories: just reps and a note, no intensity required
- notes (string, optional)

### ProgramRun
- id, user_id, program_id, started_at, completed_at (nullable)
- current_block_id, current_day_id
- round_number (int) — increments each time user re-runs the same program
- This links a user to an active instance of a program

### ScheduledWorkout
- id, program_run_id, block_id, training_day_id
- scheduled_date (date), completed_at (datetime, nullable), skipped (bool)
- This is how workouts get assigned to calendar dates

### CompletedSet
- id, scheduled_workout_id, planned_set_id
- actual_weight_kg (float, nullable) — used for both main lifts and accessories
- actual_reps (int, nullable)
- was_modified (bool) — true if user changed the prescribed weight/reps
- substituted_exercise_id (int, nullable) — if the user swapped the exercise for this session
- notes (string, optional)

### AccessoryBest
- id, user_id, exercise_id, weight_kg (float), reps (int), date_set
- Tracks the best performance per rep count for accessory exercises (e.g. best 10RM on Dumbbell Bench)
- Separate from OneRepMax — accessories don't feed into % calculations, just personal tracking
- Updated automatically when a new CompletedSet beats the previous best for that rep count

---

## Features to Build

### 1. Authentication
- Register, login, logout
- JWT tokens stored in httpOnly cookies
- Simple session management
- Multi-user ready — all data is scoped to user_id
- Admin user can see all users (stub this out for future use)

### 2. Program Builder (Interactive Wizard)

The program builder should be a **multi-step modal/wizard** experience — clean popups that guide the user through building a program step by step. No overwhelming forms. Each step is focused on one decision at a time. Progress is saved as the user moves through steps so nothing is lost if they close mid-way.

#### Step 1 — Program basics
- Modal popup: "What do you want to call this program?" (text input)
- Then: "Add a description (optional)"
- Then: "How many blocks does this program have?" (number input, e.g. 4)
- Confirm → program shell is created, move to block setup

#### Step 2 — Block setup (repeated per block)
- For each block in sequence, a popup asks:
  - "What do you want to call Block [N]?" (default: "Block N", can rename e.g. "Deload")
  - "How many training days does this block have?" (number input)
- User moves through all blocks one at a time
- After all blocks are named → move to day/exercise setup

#### Step 3 — Exercise setup per day (the main builder)
- For each Block → each Day, a focused modal shows:
  - Header: "Block 1 — Day 1" with a progress indicator (e.g. "Day 1 of 4")
  - "Add an exercise" button opens a sub-modal:
    - Search/select from exercise library (or type to create new)
    - Choose intensity type: **% of 1RM** | **RPE** | **Freeform (no intensity)**
    - Input: number of sets, reps per set, intensity value
    - If multiple sets have different intensities (e.g. 2x1@88% AND 2x5@70%), user can add them as separate "set groups" for the same exercise
    - Optional notes field
  - Exercises appear as a list in the day modal — can reorder (drag handle) or delete
  - "Add another exercise" to keep going
  - "Next Day →" button to proceed
- After all days in a block are done → "Next Block →"
- After all blocks → summary screen

#### Step 4 — Review & confirm
- Full read-only summary of the entire program:
  - Block 1 → Day 1: Bench 2×1@88%, Bench 2×5@70%, Squat 2×1@88% ...
  - Block 1 → Day 2: ...
  - etc.
- User can click "Edit" on any block/day to jump back and fix it
- "Save Program" button → program is saved and user is taken to the program list

#### Duplicating a program
- "Duplicate" button on any program in the program list
- Creates a full deep copy — all blocks, days, exercises, sets — with the name "Copy of [Program Name]"
- User is immediately dropped into the wizard on the review step so they can rename it and make changes before saving

#### Additional UX details
- Wizard should show a **progress bar or step indicator** at the top (e.g. "Step 3 of 4 — Building Block 2")
- Each modal should have a **Back** button to go to the previous step without losing data
- On desktop: wizard appears as a centered modal overlay on top of the dashboard
- On mobile: wizard takes up the full screen (like a native app flow)
- Auto-save draft to the database at each step so the user can close and resume later
- If user navigates away mid-wizard, show a "You have an unfinished program — continue?" prompt on next visit

### 3. 1RM Management
- Dedicated page: "My PRs"
- For Squat, Bench Press, Deadlift:
  - Show current 1RM
  - Button to log a new PR (enter weight + date)
  - Full history table: date | weight
  - Line chart showing 1RM progress over time (use Chart.js via CDN)
- When a new 1RM is entered, all future scheduled workouts automatically recalculate

### 4. Starting a Program
- User selects a program and clicks "Start Program"
- App creates a ProgramRun for that user starting at Block 1, Day 1
- User is shown a simple calendar/scheduling screen:
  - Shows the upcoming blocks and days
  - User can assign each training day to a specific calendar date
  - Can schedule several weeks in advance or just one day at a time
  - If a scheduled day is missed (date passed, not completed), mark it as missed and allow rescheduling to a new date
- When a program run is completed (all blocks done), prompt user to enter new 1RMs for SBD
- After entering new 1RMs, offer to immediately start a new round (round_number + 1) with all percentages recalculated

### 5. Today's Workout View
- Homepage/dashboard shows "Today's Workout" if a workout is scheduled for today
- Also shows upcoming scheduled workouts for the next 7 days
- Workout view shows:
  - Block name, Day name
  - For each exercise, in order:
    - Exercise name
    - Each set: Set 1 — 1 rep @ 110.0 kg (calculated from 88% of 125kg 1RM, rounded to 2.5kg)
    - For RPE sets: show "Set 1 — 3 reps @ RPE 8"
    - For accessories: show "3 sets × 10 reps" with a **weight input field per set** — user fills in the weight they used (or leave blank if bodyweight). Pre-fills with the last weight used for that exercise if available.
- User can tap/click into a set to modify the weight or reps before marking complete
- **Exercise substitution** — each exercise in the workout view has a "Substitute" option (three-dot menu or swap icon):
  - Opens a modal to search/select a replacement exercise from the library
  - Substitution applies to this session only — the program template is never touched
  - The substitution is recorded on the CompletedSet so history shows what was actually done
  - If the substitute is a main lift with a 1RM, weights are recalculated automatically
- At the bottom of the workout view, before hitting "Complete Workout", a free-text **session notes** field — "How did it feel? Anything to note?" (optional, max ~500 chars)
- Notes are stored on the ScheduledWorkout record and visible when reviewing past workouts in the calendar
- Notes feed into the AI summary later (already part of the workout data shape passed to AIService)
- If user manually changes a block/day selector (e.g. "I'm doing Block 2 Day 1 today"), the view updates accordingly

### 6. Calendar Overview
- Full calendar view (monthly) showing:
  - Scheduled workouts (with block/day label)
  - Completed workouts (green)
  - Missed workouts (red/grey)
- Click a day to schedule a workout for that date or reschedule a missed one
- Simple, clean mobile-friendly calendar (build with vanilla JS or use a lightweight library like Pikaday)

### 7. Progress & Stats
- Training frequency chart: workouts per week over the last 12 weeks (bar chart, Chart.js)
- Per-exercise volume over time (optional/stretch goal)
- PR history and graphs (covered in #3 above)

### 8. Volume Tracking per Muscle Group

Each exercise in the library should have a **primary muscle group** tag (enum: `chest` | `back` | `legs` | `shoulders` | `arms` | `core`). Pre-seed all default exercises with the correct tag. Users can set it when adding custom exercises.

On a dedicated **Volume** page (and as a widget on the desktop dashboard):
- Weekly volume per muscle group — bar chart showing total sets per group per week for the last 8 weeks
- Helps the user spot imbalances (e.g. lots of chest, not much back)
- Volume is calculated from CompletedSets — so it reflects what was actually done, not just what was planned
- Also show a simple current-week summary: "This week: Legs 12 sets · Chest 9 sets · Back 8 sets · Shoulders 6 sets"

Add `muscle_group` field to the Exercise model.

### 10. Accessory Exercise Progress

A dedicated **Exercise Progress** page (accessible from the nav as "Lifts" or from each exercise in the library):

- Shows progress for **any exercise** — both main lifts and accessories
- For each exercise, display:
  - **Best ever per rep count** — e.g. "Best 5 reps: 40kg · Best 10 reps: 32.5kg · Best 15 reps: 27.5kg"
  - **Weight over time chart** — line chart (Chart.js) showing the heaviest weight logged per session for that exercise, across all sessions. X-axis = date, Y-axis = kg
  - **Full history log** — table of every session where this exercise was logged: date | sets | reps | weight
- On the workout completion screen, after logging an accessory set, if it beats the previous best for that rep count, show a small highlight: "💪 New best: 42.5kg × 10"
- **Important:** this system is completely separate from the SBD PR/1RM system. Accessory bests do NOT appear on the PR page and do NOT feed into any percentage calculations — they are purely for personal progress tracking
- On the exercise library page, each exercise has a "View Progress" link that goes to this chart/history view
- On mobile, this page should be easily reachable — add it as a quick-access option from the completed workout screen ("See progress for these exercises")

The dashboard is the **desktop homepage** and also accessible on mobile via the Home tab. It should give a full at-a-glance picture of where the user is at. Build it as a card-based layout with the following widgets:

**Active Program card**
- Program name, current block, current day, round number
- Progress bar: how far through the program (e.g. "Block 2 of 4 — 12 of 16 sessions done")
- Quick buttons: "Log Today's Workout" / "Schedule Next Session"

**Next Workout card**
- Date, block name, day name
- Preview of the main lifts (not accessories) with calculated weights
- e.g. "Thursday — Block 2 Day 3: Bench 2×1@110kg · Squat 2×1@150kg"

**Recent PRs card**
- Last PR logged for each of SBD — exercise name, weight, date
- "Log new PR" shortcut button

**Training frequency card**
- Simple bar chart: workouts per week for the last 8 weeks (Chart.js)
- Streak indicator: "🔥 3 weeks in a row"

**Volume summary card**
- Current week's sets per muscle group (from Volume Tracking above)
- Small horizontal bar chart or pill badges

**Last workout card**
- Date, block/day name, duration (time between start and complete if tracked)
- The session notes the user wrote
- Greyed-out "AI Summary — coming soon" section below the notes

**SBD PR graph card** (desktop only — too large for mobile home)
- Compact line chart showing all three lifts' 1RM history on one chart
- Click to go to full PR page

### 8. Exercise Library
- Searchable and filterable list of all exercises (by category and muscle group)
- Default exercises pre-seeded (see Seed Data section)
- **Any user can add a custom exercise** at any time from:
  - The exercise library page ("+ Add Exercise" button)
  - Directly inside the program builder wizard — "Can't find it? Add new exercise" link opens a quick-add mini modal without leaving the wizard
  - The workout view when substituting an exercise — same quick-add option
- When adding a custom exercise, user sets:
  - Name (required)
  - Category: **Main Lift** or **Accessory** (default: Accessory)
  - Muscle group: chest | back | legs | shoulders | arms | core
- Custom exercises immediately appear in all search/select dropdowns across the app
- Custom exercises get full progress tracking (history + chart) just like built-in ones
- User can edit or delete their own custom exercises from the library page

---

## UI/UX Requirements

- Clean, minimal design using Tailwind CSS
- Dark mode preferred (easier to read in gyms)

### Mobile Layout (primary use: in the gym)
- Mobile-first for the workout experience
- Large tap targets for buttons (gym gloves, sweaty hands)
- The workout view should be usable with one hand
- No unnecessary clutter — the "Today's Workout" screen is the most important screen on mobile
- Use a **bottom navigation bar** on mobile: Home | Programs | PRs | Calendar | Profile
- Mobile home screen = Today's Workout front and center, with quick access to log a new PR

### Desktop Layout (primary use: program management)
- On screens wider than 1024px, switch to a **sidebar navigation** (left side) instead of bottom nav
- Desktop home screen = **dashboard overview** with:
  - Summary cards: active program, current block/day, next scheduled workout, recent PRs
  - Quick links to program builder, edit existing programs, start a new block/round
  - Upcoming workout schedule for the next 2 weeks
  - PR progress graphs for SBD visible at a glance
- The **program builder** should be optimized for desktop use — multi-column layout, drag-and-drop reordering of blocks/days/exercises if possible, inline editing
- Today's Workout is still accessible on desktop but is not the primary focus
- Use Tailwind responsive prefixes (`md:`, `lg:`) throughout to handle the layout switch cleanly

---

## Weight Calculation Logic

```python
def calculate_weight(one_rep_max: float, percentage: float) -> float:
    """Calculate working weight from 1RM percentage, rounded to nearest 2.5kg"""
    raw = one_rep_max * (percentage / 100)
    return round(raw / 2.5) * 2.5
```

- Always use the most recent 1RM entry for the relevant exercise
- Squat % → uses Squat 1RM
- Bench % → uses Bench Press 1RM  
- Deadlift % → uses Deadlift 1RM
- Other exercises with % → use their own 1RM if one exists, otherwise flag to user

---

## File Structure to Generate

```
workout-tracker/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # DB connection, session
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── auth.py              # Auth logic, JWT
│   ├── routers/
│   │   ├── auth.py
│   │   ├── programs.py
│   │   ├── workouts.py
│   │   ├── prs.py
│   │   ├── calendar.py
│   │   ├── exercises.py
│   │   ├── volume.py        # Volume tracking endpoints
│   │   ├── progress.py      # Accessory exercise progress + history
│   │   ├── dashboard.py     # Dashboard summary endpoints
│   │   └── ai.py            # Stub — no active endpoints yet
│   ├── services/
│   │   └── ai_service.py    # AI stub service
│   ├── templates/
│   │   ├── base.html        # Base layout with nav (mobile bottom bar / desktop sidebar)
│   │   ├── dashboard.html   # Desktop dashboard / mobile home
│   │   ├── program_list.html
│   │   ├── program_builder.html
│   │   ├── workout_view.html
│   │   ├── prs.html
│   │   ├── calendar.html
│   │   ├── volume.html      # Volume tracking page
│   │   ├── progress.html    # Exercise progress charts + history (accessories + main lifts)
│   │   └── auth/
│   │       ├── login.html
│   │       └── register.html
│   └── static/
│       └── app.js           # Minimal JS for interactivity and wizard logic
├── alembic/                 # DB migrations
├── requirements.txt
├── render.yaml              # Render.com deployment config
├── .env.example
└── README.md                # Setup + deployment instructions
```

---

## Deployment Instructions to Include in README

1. Clone the repo
2. `python -m venv venv && source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in values
5. `alembic upgrade head` to create DB
6. `uvicorn app.main:app --reload` for local dev
7. Push to GitHub
8. Create a new Web Service on Render.com, connect GitHub repo
9. Set environment variables in Render dashboard
10. Render auto-deploys on every push to main

---

## Seed Data

On first run, seed the database with:
- Default exercise library with muscle group tags:
  - Squat (legs, main_lift), Bench Press (chest, main_lift), Deadlift (back, main_lift)
  - Overhead Press (shoulders, main_lift)
  - Romanian Deadlift (legs, accessory), Leg Press (legs, accessory), Leg Curl (legs, accessory)
  - Pull-up (back, accessory), Barbell Row (back, accessory), Dumbbell Row (back, accessory)
  - Tricep Pushdown (arms, accessory), Bicep Curl (arms, accessory)
  - Lateral Raise (shoulders, accessory)
  - Ab Wheel / Plank (core, accessory)
- One example program called "Example PowerBuilding Program" with 4 blocks, each with 4 days, using realistic SBD percentages (70-90% range, with heavy singles at 88-92%) — so the user can see immediately how it works

---

## Future Features (do NOT build now, but structure the code to support them)

- Program sharing between users (is_public flag already in model)
- Coach/athlete relationship (one user manages programs for another)
- Accessory exercise progress tracking in detail
- Bodyweight logging
- Export workout history to CSV
- RPE-based autoregulation (adjust next session weights based on how RPE felt)
- **AI pattern recognition across programs** — analysing which programs produced the best 1RM gains over time, what intensities and volumes the user responds best to, recovery patterns from session notes, and volume sweet spots per muscle group. This requires the full uncompressed history to be intact — see data retention note below.

---

## Data Retention — Critical for Long-Term AI Analysis

**Never delete or compress historical data.** Every CompletedSet, every ScheduledWorkout, every OneRepMax entry, every session note must be kept permanently in the database. This history is what makes long-term AI pattern recognition possible — e.g. comparing which program produced the best Squat gains over 12 months, or correlating session notes with PR breakthroughs.

Specific rules:
- Deleting a program should NOT delete its historical ProgramRuns or CompletedSets — mark the program as `archived` instead
- Deleting an exercise should NOT delete its history — mark as `archived`
- No automatic cleanup jobs or log rotation on workout/set data
- When a user "restarts" a program, the old round's data stays intact — that's what `round_number` is for
- The database should be designed to grow over years of training data without issue
- On the frontend, archived programs and exercises should simply be hidden from active views, but remain fully queryable in the background

---

## AI Integration (do NOT build now — structure code to make this easy to add later)

The app should be architected so that AI features can be dropped in later with minimal refactoring. Do this by:

### Service layer
- Create an `app/services/` directory from the start
- Add an empty `app/services/ai_service.py` file with a clear docstring explaining it is a stub for future AI integration
- All future AI calls will go through this single service — nowhere else in the codebase should call an LLM directly

```python
# app/services/ai_service.py
"""
AI Service — stub for future LLM integration (e.g. Claude API via Anthropic SDK).
All AI features should be routed through this service.

Planned features:
- Workout summary: generate a natural language summary of a completed workout
- Program feedback: analyse a full program and give coaching notes
- Progress insights: spot trends in PR history and volume over time
- Autoregulation suggestions: recommend weight adjustments based on RPE logs
- Program generation: suggest a new program based on goals and history
"""

class AIService:
    def __init__(self):
        # Future: load API key from env, initialise Anthropic client here
        pass

    async def summarise_workout(self, workout_data: dict) -> str:
        # Future: send workout to Claude, return summary string
        raise NotImplementedError("AI service not yet configured")

    async def analyse_program(self, program_data: dict) -> str:
        raise NotImplementedError("AI service not yet configured")

    async def progress_insights(self, pr_history: dict, volume_history: dict) -> str:
        raise NotImplementedError("AI service not yet configured")
```

### Data shapes
- When serialising completed workouts, PR history, and program structures to JSON (for the frontend), use the same clean Pydantic schemas that will eventually be passed to the AI service — no extra transformation needed later

### UI placeholders
- On the completed workout screen, add a greyed-out "AI Summary" card with a "Coming soon" label — so the UI slot is already designed and reserved
- On the PR page and dashboard, add a greyed-out "AI Insights" section with the same treatment
- These placeholders make it easy to swap in real content later without redesigning pages

### Environment variable
- Add `ANTHROPIC_API_KEY=` as an empty entry in `.env.example` with a comment: `# Add your Anthropic API key here when ready to enable AI features`

### Router stub
- Add an empty `app/routers/ai.py` router that is imported but has no active endpoints yet — just a comment block describing the planned endpoints (`POST /ai/summarise-workout`, `POST /ai/programme-feedback`, `GET /ai/insights`)
- Register it in `main.py` so adding real endpoints later requires no changes to the app structure

---

## Important Notes for Claude Code

- Write clean, well-commented code
- Use type hints throughout Python code
- All routes should return proper HTTP status codes
- Include basic error handling (exercise not found, 1RM not set, etc.)
- If a user tries to view a workout with no 1RM set for a percentage-based exercise, show a clear message: "Set your [Squat] 1RM before starting this program"
- The weight calculation should happen at render time (when the page loads), not stored in the DB — so it always uses the latest 1RM
- Use environment variables for all secrets (SECRET_KEY, DATABASE_URL)
- Include a `.env.example` file
- **Multi-user:** the app supports multiple independent users out of the box — every query must be scoped to the logged-in user's `user_id`. Never return or modify another user's data. Anyone can register at the app's URL and get a fully isolated experience with their own programs, PRs, and history
- **Never hard-delete training history** — see Data Retention section above. Use `is_archived` flags instead of DELETE for programs and exercises

---

## Pre-Flight Checklist — Before Writing Any Code

Before starting Phase 1, verify the following are installed and working on your machine. Claude Code should check each of these and tell you exactly what to install if anything is missing.

### Required tools
- **Python 3.11+** — check with `python --version` or `python3 --version`
- **pip** — check with `pip --version`
- **git** — check with `git --version`
- **A GitHub account** — needed for Render deployment later
- **A Render.com account** — sign up free at render.com (do this before Phase 8)

### Python libraries (install before starting)
Claude Code should generate a `requirements.txt` first, then tell the user to run:
```
pip install -r requirements.txt
```
The requirements.txt should include at minimum:
```
fastapi
uvicorn[standard]
sqlalchemy
alembic
psycopg2-binary
python-jose[cryptography]
passlib[bcrypt]
python-dotenv
python-multipart
jinja2
httpx
```

Claude Code should verify these install without errors before proceeding. If there are any conflicts or errors, resolve them before writing any application code.

### Environment setup
- Create and activate a virtual environment first:
  ```
  python -m venv venv
  source venv/bin/activate   # Mac/Linux
  venv\Scripts\activate      # Windows
  ```
- Confirm the virtual environment is active before installing anything

---

## Important Instructions for Claude Code — Slow Down on Integrations

Whenever the build process reaches a step that involves **external services, hosting, databases, or environment configuration**, Claude Code must:

1. **Stop and explain what is about to happen** before doing anything — what service, why it's needed, what the user will need to do
2. **Give complete step-by-step instructions** with exact commands, exact URLs, and screenshots descriptions of what to click where
3. **Wait for confirmation** that each step is complete before moving to the next
4. **Explain what each environment variable does** when asking the user to set one — never just say "add this to your .env" without explaining what it is

### Specific integrations that need this careful treatment:

**Setting up the local database (SQLite)**
- Explain that SQLite needs no installation — it's built into Python
- Show exactly how to run the first migration: `alembic upgrade head`
- Show how to verify the database was created correctly
- Show how to run the seed data script and verify it worked

**Setting up PostgreSQL on Render**
- Explain the difference between SQLite (local) and PostgreSQL (production)
- Walk through creating a PostgreSQL instance on Render step by step:
  - Go to render.com → New → PostgreSQL
  - Name it, select free tier, create
  - Copy the "Internal Database URL" — explain what this is and where to paste it
- Explain that the DATABASE_URL env variable switches between SQLite locally and PostgreSQL on Render

**Deploying to Render (Phase 8)**
- This should be a complete, numbered walkthrough:
  1. Push code to GitHub — explain how if the user hasn't set up a repo yet
  2. Go to render.com → New → Web Service
  3. Connect GitHub account and select the repo — explain the OAuth flow
  4. Set the build command: `pip install -r requirements.txt && alembic upgrade head`
  5. Set the start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  6. Add each environment variable one by one — explain what each one is:
     - `DATABASE_URL` — the PostgreSQL connection string from the Render DB
     - `SECRET_KEY` — a random secret for signing JWT tokens, generate with `python -c "import secrets; print(secrets.token_hex(32))"`
     - `ENVIRONMENT` — set to `production`
  7. Click Deploy and watch the logs — explain what successful output looks like
  8. Open the live URL and test login on mobile

**Generating and managing the SECRET_KEY**
- Explain what it is (signs auth tokens — keep it secret, never commit to git)
- Show the exact command to generate one
- Remind the user to add `.env` to `.gitignore` before the first commit

**Any time a `.env` file is involved**
- Show the complete current state of `.env.example` with all variables listed
- Remind the user to copy it to `.env` and fill in real values
- Remind the user that `.env` should never be committed to git

Do NOT build everything at once. Follow this phased approach, making sure each phase works fully before moving to the next. At the start of each new phase, remind Claude Code of the full spec above so it keeps the bigger picture in mind.

---

### Phase 1 — Foundation (get something running locally)
1. Set up the project structure and file layout as specified
2. Build the database models and run the first Alembic migration
3. Seed the exercise library and example program
4. Build auth — register, login, logout with JWT cookies
5. Build a bare-bones homepage that just shows "Hello [name], you are logged in"

**Stop here. Make sure the app runs locally with `uvicorn`, you can register a user, log in, and see the homepage.**

---

### Phase 2 — 1RM and PR foundation
1. Build the 1RM model and the My PRs page
2. User can log a new SBD PR, see history table, see the line chart
3. Weight calculation function working and tested

**Stop here. Make sure you can enter a Squat/Bench/Deadlift 1RM and see it saved and charted correctly. This is the foundation everything else depends on.**

---

### Phase 3 — Today's Workout (the most important screen)
1. Manually insert a test program + scheduled workout directly in the database (no builder yet)
2. Build the workout view — shows exercises, calculated weights, set modification, exercise substitution
3. Build workout completion — mark as done, log CompletedSets, session notes field
4. Homepage shows today's workout if one is scheduled

**Stop here. Test the full loop on your phone: see today's workout, check the weights are calculated correctly from your 1RM, modify a set, complete the workout. This is the core of the app.**

---

### Phase 4 — Program Builder Wizard
1. Build the 4-step wizard (program basics → block setup → exercise setup → review)
2. Auto-save draft at each step
3. Edit existing program
4. Duplicate program

**Stop here. Build a real program through the wizard and verify it produces correct scheduled workouts with correct weight calculations.**

---

### Phase 5 — Calendar and Scheduling
1. Build the calendar view (monthly, colour-coded)
2. Schedule workouts to specific dates from a program run
3. Missed workout detection and rescheduling
4. Start program flow — creates ProgramRun, drops into scheduling screen
5. End of program flow — prompt for new 1RMs, start new round

**Stop here. Run through a full program start → schedule workouts → complete them → finish program → enter new 1RMs → start round 2.**

---

### Phase 6 — Progress and Stats
1. Accessory weight logging in workout view (pre-fill from last session)
2. Exercise Progress page — history table + weight over time chart for any exercise
3. AccessoryBest tracking — auto-update on completion, "New best" highlight
4. Volume tracking per muscle group — weekly chart
5. Training frequency chart

**Stop here. Complete a few workouts with accessories and verify the progress charts are populating correctly.**

---

### Phase 7 — Dashboard
1. Build the full dashboard with all widgets (active program, next workout, recent PRs, frequency chart, volume summary, last workout card, SBD PR graph)
2. Make sure desktop layout uses sidebar nav and dashboard as homepage
3. Make sure mobile layout uses bottom nav and today's workout as homepage

---

### Phase 8 — Polish and Deploy
1. Review all screens on mobile — tap targets, readability, one-handed usability
2. Dark mode check across all pages
3. Error states — missing 1RM warning, empty states for new users, etc.
4. Deploy to Render.com following the README instructions
5. Test the full app on your phone via the live URL

---

### Ongoing — add features as needed
After Phase 8 you have a fully working v1. New features, tweaks, and AI integration can be added incrementally without touching the core architecture. Each addition should follow the same pattern: build it, test it locally, deploy.

---

**To start, paste this entire document into Claude Code and say:**

> "Follow the iterative build process at the bottom of this spec. Start with Phase 1 only — set up the project structure, database models, migrations, seed data, and auth. Do not build anything from Phase 2 or later yet. Ask me if anything is unclear before starting."