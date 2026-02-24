# Workout Tracker — Project Rules

## Stack
- Backend: Python + FastAPI
- Templating: Jinja2
- Styling: Tailwind CSS via CDN (no build step)
- JS: Vanilla JS only — no React, no Vue, no heavy frameworks
- Charts: Chart.js via CDN
- Database: SQLite locally, PostgreSQL on Render

## Frontend Rules
- Dark mode throughout — background #111827 (gray-900), cards #1f2937 (gray-800)
- Mobile-first using Tailwind responsive prefixes (md:, lg:)
- On mobile (< 1024px): bottom navigation bar, Today's Workout as homepage
- On desktop (>= 1024px): left sidebar navigation, dashboard as homepage
- Large tap targets on all buttons — minimum h-12 on mobile
- Use the frontend-design skill for all UI work

## Code Rules
- Always use Python type hints
- All DB queries must be scoped to the logged-in user_id — never leak data between users
- Never hard-delete training history — use is_archived flags instead
- Weights always rounded to nearest 2.5kg
- Environment variables for all secrets — never hardcode

## Key Reminders
- Read the frontend-design skill in .claude/skills/frontend-design/SKILL.md before building any UI
- Ask before starting each new phase
- Go slow on any external service setup (Render, PostgreSQL, GitHub)
- Explain each step before doing it
- Wait for confirmation that each step worked before moving to the next
```

Then **File → Save** and close Notepad.

Verify it saved correctly:
```
Get-Content "CLAUDE.md"