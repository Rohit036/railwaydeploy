# FastAPI / Streamlit minimal apps — Railway deploy

This repo contains two minimal example apps you can deploy to Railway:

- `app/main.py`: Minimal FastAPI application (default).
- `streamlit_app.py`: Minimal Streamlit app (alternate).

Quick steps

1. Commit this repo to a GitHub repository.
2. Create a new project on Railway and link your GitHub repo.
3. Railway will detect a Python app. By default the `Procfile` runs the FastAPI app.

To deploy the Streamlit app instead:

1. Rename `Procfile.streamlit` to `Procfile` (or set the start command in Railway to:
   `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`).
2. Add the environment variable `STREAMLIT_SERVER_HEADLESS=true` in Railway.

Local run

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

Run Streamlit locally:

```bash
streamlit run streamlit_app.py
```
