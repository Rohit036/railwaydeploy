#!/bin/bash
# Starts both the FastAPI backend (port 8000) and the Streamlit frontend ($PORT)
# in a single Railway service.  The frontend connects to the backend at localhost:8000.
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Wait until FastAPI is accepting connections (up to 30 s) before starting Streamlit
echo "Waiting for FastAPI to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        echo "FastAPI is ready."
        break
    fi
    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
        echo "ERROR: FastAPI process exited unexpectedly." >&2
        exit 1
    fi
    sleep 1
done

exec streamlit run streamlit_app.py --server.port "$PORT" --server.address 0.0.0.0
