# Setup and Workflow (Simple)

## Project Tree
```text
.
├── .github/                               - GitHub settings/templates
│   └── pull_request_template.md           - PR form everyone fills in
├── .gitignore                             - What Git should not track
├── 5540_onahama_修復+階数+高さ差_沿岸/      - Your shapefile data folder
│   ├── ... .cpg                           - Text encoding for the dataset
│   ├── ... .dbf                           - Table of attributes
│   ├── ... .prj                           - Map projection info
│   ├── ... .qmd                           - QGIS extra metadata
│   ├── ... .shp                           - Main shape geometry
│   └── ... .shx                           - Shape index for fast reading
├── README.md                              - Main project intro
├── SETUP_AND_WORKFLOW.md                  - This setup guide
├── backend/                               - Django server code
│   ├── .env                               - Your real local secrets/settings
│   ├── .env.example                       - Copy this to create `.env`
│   ├── README.md                          - Backend notes
│   ├── apps/                              - Feature folders for backend
│   │   ├── __init__.py                    - Tells Python this is a package
│   │   ├── api/                           - API endpoint code
│   │   │   ├── __init__.py                - Package marker
│   │   │   ├── admin.py                   - Admin page config for this app
│   │   │   ├── apps.py                    - App name/config
│   │   │   ├── migrations/__init__.py     - Migration package marker
│   │   │   ├── models.py                  - Database models (if any)
│   │   │   ├── serializers.py             - API input/output formats
│   │   │   ├── urls.py                    - API URL paths
│   │   │   └── views.py                   - API request handling logic
│   │   ├── core/                          - Shared/common backend area
│   │   │   ├── __init__.py                - Package marker
│   │   │   ├── admin.py                   - Admin config
│   │   │   ├── apps.py                    - App config
│   │   │   ├── migrations/__init__.py     - Migration package marker
│   │   │   ├── models.py                  - Core database models
│   │   │   └── views.py                   - Core views
│   │   └── geo/                           - Geospatial backend logic
│   │       ├── __init__.py                - Package marker
│   │       ├── admin.py                   - Geo models in admin
│   │       ├── apps.py                    - Geo app config
│   │       ├── migrations/                - Database change history
│   │       │   ├── 0001_initial.py        - First DB setup for geo app
│   │       │   └── __init__.py            - Migration package marker
│   │       ├── models.py                  - Geo database models
│   │       └── views.py                   - Geo views (if used)
│   ├── manage.py                           - Command runner (`runserver`, `migrate`)
│   ├── media/                              - Uploaded files saved locally
│   ├── nkbp_backend/                       - Main Django project settings
│   │   ├── __init__.py                     - Package marker
│   │   ├── asgi.py                         - Async server entry file
│   │   ├── settings.py                     - All backend settings
│   │   ├── urls.py                         - Top-level URL mapping
│   │   └── wsgi.py                         - Standard server entry file
│   └── requirements.txt                    - Python packages to install
└── frontend/                               - Next.js web app code
    ├── .gitignore                          - Frontend ignore rules
    ├── README.md                           - Frontend notes
    ├── eslint.config.mjs                   - Linting rules
    ├── jsconfig.json                       - JS config/path aliases
    ├── next.config.js                      - Next.js config
    ├── package-lock.json                   - Exact npm package versions
    ├── package.json                        - npm scripts and dependencies
    ├── public/                             - Static files (icons/images)
    │   ├── file.svg                        - Icon asset
    │   ├── globe.svg                       - Icon asset
    │   ├── next.svg                        - Icon asset
    │   ├── vercel.svg                      - Icon asset
    │   └── window.svg                      - Icon asset
    └── src/                                - Frontend source files
        ├── app/                            - Pages/layout for app router
        │   ├── components/                 - Reusable UI blocks
        │   │   ├── analysis/
        │   │   │   ├── AnalysisSummary.js              - Analysis summary box
        │   │   │   └── AnalysisSummary.module.css      - Styles for summary box
        │   │   ├── layout/
        │   │   │   ├── Navbar.js                       - Top menu bar
        │   │   │   ├── Navbar.module.css               - Navbar styles
        │   │   │   ├── Sidebar.js                      - Side menu panel
        │   │   │   └── Sidebar.module.css              - Sidebar styles
        │   │   ├── map/
        │   │   │   ├── MapView.js                      - Map display component
        │   │   │   └── MapView.module.css              - Map styles
        │   │   └── upload/
        │   │       ├── FileUpload.js                   - File upload widget
        │   │       └── FileUpload.module.css           - Upload widget styles
        │   ├── favicon.ico                 - Browser tab icon
        │   ├── globals.css                 - Global CSS
        │   ├── layout.js                   - Shared page layout
        │   ├── page.js                     - Home page content
        │   └── page.module.css             - Home page styles
        └── services/
            └── api.js                      - Functions that call backend APIs
```

## Shared Admin Login (local dev)
Use this account for local testing:
- Username: `admin`
- Password: `Admin123!Temp`

If missing, recreate it:
```bash
cd backend
source .venv/bin/activate
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,_=U.objects.get_or_create(username='admin', defaults={'email':'admin@example.com','is_staff':True,'is_superuser':True}); u.is_staff=True; u.is_superuser=True; u.set_password('Admin123!Temp'); u.save(); print('admin ready')"
```

## 1) First-time setup (frontend + backend)

### 1. Pull latest main first
```bash
cd DSA3101-AY2520-Project5-GroupA
git fetch origin
git checkout main
git pull --ff-only origin main
```

### 2. Backend setup
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

### 3. Frontend setup
Open a new terminal:
```bash
cd DSA3101-AY2520-Project5-GroupA/frontend
npm ci
```
If `npm ci` fails:
```bash
npm install
```

### 4. Run both apps
Backend terminal:
```bash
cd DSA3101-AY2520-Project5-GroupA/backend
source .venv/bin/activate
python manage.py runserver 8000
```
Frontend terminal:
```bash
cd DSA3101-AY2520-Project5-GroupA/frontend
npm run dev
```

## 2) Coming back later

### 1. Pull latest main first
```bash
cd DSA3101-AY2520-Project5-GroupA
git fetch origin
git checkout main
git pull --ff-only origin main
```

### 2. Start backend
```bash
cd backend
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 8000
```

### 3. Start frontend
```bash
cd frontend
npm run dev
```

## 3) Links
- Frontend: `http://localhost:3000`
- Backend health: `http://127.0.0.1:8000/api/health/`
- Admin panel: `http://127.0.0.1:8000/admin/`

## 4) Git pull and push flow

### Start new work
```bash
cd DSA3101-AY2520-Project5-GroupA
git fetch origin
git checkout main
git pull --ff-only origin main
git checkout -b <branch-name>
```

### Push work
```bash
git add -A
git commit -m "<clear message>"
git push -u origin <branch-name>
```

### Before opening PR, sync main
```bash
git fetch origin
git checkout <branch-name>
git merge origin/main
```

## 5) PR expectations
- Add Python docstrings for non-trivial backend code.
- Edit PR description before requesting merge.
- State clearly what changed

## 6) Debug toolbar (quick use)
- Requires `DJANGO_DEBUG=1` in `backend/.env`.
- Open a Django HTML page, e.g. `http://127.0.0.1:8000/admin/login/`.
- The toolbar appears on the page edge; click it to inspect SQL, request data, and timings.
- `GET /__debug__/` alone may show 404; this is normal.
