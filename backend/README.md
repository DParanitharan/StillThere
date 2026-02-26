# Backend Scaffold (Django + DRF)
TEST BACKEND v
## Prerequisite
Install Geos, Gdal, Proj form OSGeo4W

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
$env:GDAL_LIBRARY_PATH="C:\Users\user\OSGeo4W\bin\gdal312.dll"
$env:GEOS_LIBRARY_PATH="C:\Users\user\OSGeo4W\bin\geos_c.dll"
$env:PATH="C:\Users\user\OSGeo4W\bin;" + $env:PATH
python manage.py migrate
python manage.py runserver 8000
```

## API Endpoints

- `GET /api/health/`
- `POST /api/upload/`
  - Request: `multipart/form-data` with field `file`
  - Response includes top-level `geojson` for current frontend compatibility.
- `GET /api/overlay/<session_id>/`
- `POST /api/analysis/<upload_id>/` (stub; matches existing frontend service)
- `GET /api/analysis/<analysis_id>/results/` (stub; matches existing frontend service)
- `POST /api/analyze/<session_id>/` (stub)
- `GET /api/export/<session_id>/<export_type>/` (stub)

## Notes

- DB engine is configured for PostGIS in `nkbp_backend/settings.py`.
- Uploads are stored under `backend/media/uploads/` in development.
