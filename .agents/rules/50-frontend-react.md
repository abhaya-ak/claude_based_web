---
trigger: glob
globs: frontend/**
description: React frontend conventions
---
# React frontend rules
- Stack: React + Vite + TypeScript, React Router, TanStack Query, Axios, Chart.js, Tailwind. Nothing else without approval.
- API types are generated from backend/openapi.yaml (openapi-typescript). Never hand-write or invent endpoints/fields; if missing, stop and ask.
- Same-origin `/api/v1/...`; dev uses Vite proxy; no CORS hacks.
- Access token in memory only; on 401 do one refresh then retry once, else go to login.
- Handle the standard error envelope {error:{code,message,details,request_id}} everywhere; show request_id in error toasts.
- No secrets in the bundle (VITE_* is public).
- Accessibility: WCAG 2.1 AA, keyboard navigable, labels on inputs, alt text; elderly mode: >=20px base font, high contrast, text-to-speech.
- Loading, empty, and error states for every data view. Forms validate and show field errors from `details`.
- Never render user HTML unsanitised.
- Mobile-first responsive layouts.
