# Footprint Change Checker

A geospatial machine-learning application that automatically detects changes in
building footprints between two shapefile datasets — classifying each building as
**Unchanged**, **Modified**, or **Removed** — to support post-disaster damage
assessment and urban change monitoring.

Built as a group project for **NUS DSA3101 (AY25/26), Group A.**

---

## Overview

Comparing building footprints across time is normally slow and manual. This system
automates it with a two-phase hybrid detection pipeline, an interactive review UI,
and a natural-language chatbot for querying results.

### Key features

- **Two-phase detection pipeline** — a cheap pixel/spectral screen (brightness,
  texture, green ratio) followed by geometry matching using the Segment Anything Model (SAM) and Intersection-over-Union scoring.
- **AI fallback layer** — a classification model steps in when SAM misses a
  building, preventing the pipeline from defaulting to "Removed."
- **Interactive map UI** — toggle between shapefile and satellite views, inspect
  per-building SAM/IoU scores, and manually re-classify buildings.
- **NLP chatbot** — query the spatial database in natural language (change
  summaries, filtering by size / material / height / zone) with read-only,
  SQL-validated, hallucination-resistant guardrails.
- **Export & evaluation** — audit-ready PDF/CSV reports and a built-in suite for
  measuring pipeline performance.

### Tech stack

| Layer    | Technology                       |
| -------- | -------------------------------- |
| Frontend | Next.js (React), JavaScript, CSS |
| Backend  | Django (Python), Django REST     |
| Database | PostgreSQL + PostGIS             |
| ML / CV  | Segment Anything Model (SAM)     |
| Infra    | Docker, Docker Compose, nginx    |

---

## Getting started

### Prerequisites
Install Docker Desktop and make sure it is running.

### Start the database (Postgres + PostGIS)
From the project root:

```bash
docker compose up -d
```

For full backend/frontend setup and the development workflow, see
[SETUP_AND_WORKFLOW.md](SETUP_AND_WORKFLOW.md).

---

## Team

This was a collaborative project by six members of DSA3101 Group A.

### My contributions (D. Paranitharan)

I was one of the two most active contributors. My work focused on:

- **Backend API & authentication** — designed and built the Django REST API
  layer (`views`, `urls`, `serializers`), plus CSRF-exempt session authentication
  and the login/logout flow.
- **Infrastructure & deployment** — containerised the full stack with Docker and
  Docker Compose, and set up the nginx reverse proxy.
- **Async extraction pipeline** — implemented asynchronous footprint extraction
  with SAM tile processing, per-tile timeouts, SAM caps, and live progress
  tracking.
- **Frontend** — built the file-upload flow, progress panel, map view, and
  dashboard/navbar components, and wired the frontend API service to the backend.

> This repository is a personal copy of a group project, published to showcase my
> contributions. All commit history and authorship is preserved from the original
> team repository.
