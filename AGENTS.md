# AGENTS.md — Salon Queue Management

Queue app for a salon: customers join from their phone, see wait time, get called; reception and barbers manage the queue; TV display.

## Read first
- docs/01-brief.md        -> features + what NOT to build
- docs/02-screens.md      -> every screen's layout and behaviour
- docs/03-flows-rules.md  -> flows, queue rules, test checklist

## Stack
React-like component structure for better UI, but use only raw JavaScript, CSS and HTML. No React installation, build tools, bundlers or frontend framework setup.
Django for backend.
Choose the simplest storage that keeps phone, tablet and TV in sync, for eg: sqlite (explain your choice before using it).
Frontend must run without a separate frontend server or development setup. Django should serve the frontend directly.
Hosting: Vercel (frontend); Render or Railway if a backend is needed.
Live link must be the first line after the title in README.md.

## UI / Design Guidelines
- **Overall look:** Premium, polished and modern. The UI must look professionally designed, not generic, template-like or AI-generated.
- **Theme:** Dark theme throughout the application.
- **Background:** Use dark charcoal and near-black shades to create depth and visual hierarchy.
- **Primary colour:** Deep purple. Use it consistently for primary actions, highlights, active states and important UI elements.
- **Secondary colour:** Use a complementary colour that works well with deep purple and the dark background. Prefer subtle lavender, muted violet or cool grey tones. Avoid introducing colours that clash with the primary theme.
- **Cards:** All cards must have rounded corners and an elevated appearance, using subtle shadows, borders or background contrast to create depth.
- **Component structure:** Build the UI using reusable, React-like components and modular JavaScript functions, but implement everything using plain HTML, CSS and JavaScript. Do not introduce React or any frontend framework dependencies.
- **Consistency:** Maintain consistent spacing, typography, border radii, shadows, colours and interaction patterns across all screens.
- **Avoid visual clutter:** Use whitespace, clear hierarchy and restrained visual effects. Avoid excessive gradients, unnecessary animations, flashy effects and generic AI-generated design patterns.
- **Responsiveness:** The UI must adapt cleanly to phones, tablets and TV displays.

## How to work
- One screen or one feature per task. Don't touch other screens.
- All labels via the EN/GU language file; no hard-coded text.
- Queue rules live in ONE place in the code; reuse them everywhere.
- Never add features from the 'Don't build' list.
- After each task: list changed files and how to test the change.
- Log each of my prompts and the changes you made with a short summary into 'prompts.md'.