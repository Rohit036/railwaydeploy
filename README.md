# Streamlit — Railway deploy

This repo contains an **Appliance Manager** app built with Streamlit.

- `streamlit_app.py` — Streamlit UI
- `app/main.py` — FastAPI REST API (optional, not used by the Streamlit UI)

---

## Deploying to Railway

1. Create a new Railway project and add a service linked to this GitHub repo.
2. Railway will detect the `Procfile` and run:
   ```
   streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```
3. Optionally add `STREAMLIT_SERVER_HEADLESS=true` in the Railway service
   environment variables.

---

## Local run

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run Streamlit locally:

```bash
streamlit run streamlit_app.py
```
