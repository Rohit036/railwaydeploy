# FastAPI + Streamlit — Railway deploy

This repo contains an **Appliance Manager** app:

- `app/main.py` — FastAPI REST API (backend)
- `streamlit_app.py` — Streamlit UI (frontend)

---

## Deploying to Railway (recommended: two separate services)

Railway exposes one `$PORT` per service, so run the backend and frontend as two
separate Railway services that share the same GitHub repo.

### 1. Deploy the FastAPI backend

1. Create a new Railway project and add a service linked to this GitHub repo.
2. Railway will detect the `Procfile` and run:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
3. Railway will generate a public URL for this service, e.g.
   `https://your-api.up.railway.app`. Copy it.

### 2. Deploy the Streamlit frontend

1. In the **same Railway project**, add a **second** service linked to the same
   GitHub repo.
2. Set the **Start Command** (in Railway service settings) to:
   ```
   streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```
   Or rename / copy `Procfile.streamlit` to `Procfile` for that service.
3. Add an environment variable in the Railway service settings:
   ```
   API_URL=https://your-api.up.railway.app
   ```
   (Replace with the actual URL from step 1.)
4. Add `STREAMLIT_SERVER_HEADLESS=true` as well.

---

## Deploying to Railway (alternative: single service)

If you prefer a single Railway service running both processes:

1. Set the **Start Command** to:
   ```
   bash start.sh
   ```
   The `start.sh` script starts FastAPI on port 8000 and Streamlit on `$PORT`.
   The Streamlit app defaults to `API_URL=http://localhost:8000` when no
   `API_URL` environment variable is set, so no extra configuration is needed.

---

## Local run

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run FastAPI locally:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run Streamlit locally (in a second terminal):

```bash
streamlit run streamlit_app.py
```

The Streamlit app defaults to `API_URL=http://localhost:8000`, so it will
connect to the local FastAPI server automatically.
