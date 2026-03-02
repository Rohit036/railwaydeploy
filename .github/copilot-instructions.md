# Copilot Instructions

## Project Overview

This repository contains an **Appliance Manager** application built with **Streamlit**, deployed on **Railway**. It allows users to track home appliances, monitor warranty expiry dates, troubleshoot common issues, and manage service history.

## Architecture

- **`streamlit_app.py`** — The main Streamlit UI. This is the primary application users interact with. All UI logic, state management, and data rendering live here.
- **`app/main.py`** — A FastAPI REST API providing CRUD endpoints for appliances. This is optional and not used by the Streamlit UI directly.
- **`data/appliances.csv`** — Flat-file data store (CSV) used by both the Streamlit app and the FastAPI backend.
- **`requirements.txt`** — Python dependencies (`streamlit`, `pandas`, `plotly`).
- **`Procfile`** — Railway start command for the Streamlit app.
- **`Procfile.streamlit`** — Alternative Procfile for Streamlit deployments.

## Tech Stack

- **Python 3** (primary language)
- **Streamlit** — UI framework
- **Pandas** — Data manipulation and CSV I/O
- **Plotly** — Charts and visualisations
- **FastAPI** — REST API (optional companion service)
- **Pydantic** — Data validation in the FastAPI layer

## Running Locally

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run streamlit_app.py

# (Optional) Run the FastAPI backend
uvicorn app.main:app --reload
```

## Key Conventions

- **Data storage**: Appliances are persisted in `data/appliances.csv`. The Streamlit app uses the columns: `id`, `name`, `brand`, `category`, `purchase_date`, `warranty_expiry`, `serial_number`, `model_number`, `purchase_price`, `last_service_date`, `notes`. The FastAPI backend uses a subset: `id`, `name`, `brand`, `category`, `purchase_date`, `warranty_expiry`, `notes`.
- **Date format**: Dates are stored as `YYYY-MM-DD` strings in the CSV.
- **Session state**: Streamlit session state (`st.session_state`) is used for UI toggles such as dark mode and edit mode.
- **Styling**: CSS is injected via `st.markdown(..., unsafe_allow_html=True)`. Light/dark mode colour tokens are defined near the top of `streamlit_app.py`.
- **Warranty status**: Calculated at runtime from `warranty_expiry` relative to today's date using `days_left`.

## Testing

There is no dedicated test suite in this repository. When adding new functionality:
- Manually verify Streamlit UI interactions.
- For the FastAPI layer, use the auto-generated Swagger UI at `/docs` when running `uvicorn`.

## Deployment

The app is deployed on [Railway](https://railway.app). Railway detects the `Procfile` and runs:

```
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
```

Set `STREAMLIT_SERVER_HEADLESS=true` in Railway environment variables to suppress browser-open behaviour.
