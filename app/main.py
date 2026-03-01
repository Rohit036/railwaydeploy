import csv
import io
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Appliance Manager API")

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "appliances.csv")
FIELDNAMES = ["id", "name", "brand", "category", "purchase_date", "warranty_expiry", "notes"]


class Appliance(BaseModel):
    id: Optional[int] = None
    name: str
    brand: str
    category: str
    purchase_date: str
    warranty_expiry: str
    notes: str = ""


def read_appliances() -> List[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def write_appliances(appliances: List[dict]) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(appliances)


def next_id(appliances: List[dict]) -> int:
    if not appliances:
        return 1
    return max(int(a["id"]) for a in appliances) + 1


@app.get("/")
async def root():
    return {"message": "Appliance Manager API"}


@app.get("/appliances", response_model=List[Appliance])
async def list_appliances():
    return read_appliances()


@app.get("/appliances/download")
async def download_appliances():
    appliances = read_appliances()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(appliances)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=appliances.csv"},
    )


@app.post("/appliances", response_model=Appliance, status_code=201)
async def add_appliance(appliance: Appliance):
    appliances = read_appliances()
    new_id = next_id(appliances)
    new_row = {
        "id": new_id,
        "name": appliance.name,
        "brand": appliance.brand,
        "category": appliance.category,
        "purchase_date": appliance.purchase_date,
        "warranty_expiry": appliance.warranty_expiry,
        "notes": appliance.notes,
    }
    appliances.append(new_row)
    write_appliances(appliances)
    return new_row


@app.delete("/appliances/{appliance_id}", status_code=204)
async def delete_appliance(appliance_id: int):
    appliances = read_appliances()
    remaining = [a for a in appliances if int(a["id"]) != appliance_id]
    if len(remaining) == len(appliances):
        raise HTTPException(status_code=404, detail="Appliance not found")
    write_appliances(remaining)
