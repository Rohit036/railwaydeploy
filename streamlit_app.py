import io
import os
from datetime import date, datetime, timedelta

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
REMINDER_DAYS = 30  # warn when expiry is within this many days
INVALID_DATE_DAYS = 9999  # fallback for unparseable expiry dates


def fetch_appliances():
    try:
        resp = requests.get(f"{API_URL}/appliances", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Could not connect to API: {e}")
        return []


def days_until_expiry(expiry_str: str) -> int:
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return (expiry - date.today()).days
    except ValueError:
        return INVALID_DATE_DAYS


st.set_page_config(page_title="Appliance Manager", page_icon="🏠", layout="wide")
st.title("🏠 Appliance Manager")

# ── Sidebar: Add Appliance ──────────────────────────────────────────────────
with st.sidebar:
    st.header("➕ Add New Appliance")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Appliance Name", placeholder="e.g. Refrigerator")
        brand = st.text_input("Brand", placeholder="e.g. Samsung")
        category = st.selectbox(
            "Category",
            ["Kitchen", "Laundry", "HVAC", "Electronics", "Plumbing", "Cleaning", "Other"],
        )
        purchase_date = st.date_input("Purchase Date", value=date.today())
        warranty_expiry = st.date_input(
            "Warranty Expiry", value=date.today() + timedelta(days=365)
        )
        notes = st.text_area("Notes", placeholder="Optional notes...")
        submitted = st.form_submit_button("Add Appliance")

    if submitted:
        if not name or not brand:
            st.sidebar.error("Name and Brand are required.")
        else:
            payload = {
                "name": name,
                "brand": brand,
                "category": category,
                "purchase_date": str(purchase_date),
                "warranty_expiry": str(warranty_expiry),
                "notes": notes,
            }
            try:
                resp = requests.post(f"{API_URL}/appliances", json=payload, timeout=5)
                resp.raise_for_status()
                st.sidebar.success(f"'{name}' added successfully!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Failed to add appliance: {e}")

# ── Main content ────────────────────────────────────────────────────────────
data = fetch_appliances()

if not data:
    st.info("No appliances found. Add one using the sidebar.")
    st.stop()

df = pd.DataFrame(data)
df["days_left"] = df["warranty_expiry"].apply(days_until_expiry)

# ── Expiry reminders ────────────────────────────────────────────────────────
expiring_soon = df[df["days_left"].between(0, REMINDER_DAYS)]
expired = df[df["days_left"] < 0]

if not expired.empty:
    st.error(
        f"⚠️ **{len(expired)} appliance(s) with expired warranty:** "
        + ", ".join(expired["name"].tolist())
    )

if not expiring_soon.empty:
    st.warning(
        f"🔔 **{len(expiring_soon)} appliance(s) expiring within {REMINDER_DAYS} days:** "
        + ", ".join(
            f"{r['name']} ({r['days_left']} days)" for _, r in expiring_soon.iterrows()
        )
    )

# ── Download button ─────────────────────────────────────────────────────────
try:
    csv_resp = requests.get(f"{API_URL}/appliances/download", timeout=5)
    csv_resp.raise_for_status()
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_resp.content,
        file_name="appliances.csv",
        mime="text/csv",
    )
except Exception:
    pass

st.markdown("---")

# ── Appliance table with delete buttons ────────────────────────────────────
st.subheader(f"Your Appliances ({len(df)} total)")

for _, row in df.iterrows():
    days = int(row["days_left"])
    if days < 0:
        status_icon = "🔴"
        status_text = f"Expired {abs(days)} days ago"
    elif days <= REMINDER_DAYS:
        status_icon = "🟡"
        status_text = f"Expires in {days} days"
    else:
        status_icon = "🟢"
        status_text = f"Expires in {days} days"

    with st.expander(f"{status_icon} {row['name']} — {row['brand']} ({row['category']})"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Purchase Date", row["purchase_date"])
        col2.metric("Warranty Expiry", row["warranty_expiry"])
        col3.metric("Status", status_text)
        if row["notes"]:
            st.caption(f"📝 {row['notes']}")
        if st.button("🗑️ Delete", key=f"del_{row['id']}"):
            try:
                resp = requests.delete(
                    f"{API_URL}/appliances/{row['id']}", timeout=5
                )
                resp.raise_for_status()
                st.success(f"'{row['name']}' deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete: {e}")

