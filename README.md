# DocScribe

DocScribe converts Malayalam consultation audio into editable English transcripts and OPD notes.

## Local development

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Configure both environment files before starting. Apply missing `supabase/migrations` files once, in filename order.

## Before release

```powershell
cd backend
python -m unittest discover -v
cd ../frontend
npm run lint
npm run build
```

See [deployment](docs/deployment.md) and [technical notes](docs/technical.md).
