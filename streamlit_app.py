import html
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "appliances.csv")
FIELDNAMES = [
    "id", "name", "brand", "category", "purchase_date", "warranty_expiry",
    "serial_number", "model_number", "purchase_price", "last_service_date", "notes",
]
REMINDER_DAYS = 30  # warn when expiry is within this many days
INVALID_DATE_DAYS = 9999  # fallback for unparseable expiry dates

CATEGORY_ICONS = {
    "Kitchen": "🍳",
    "Laundry": "👕",
    "HVAC": "❄️",
    "Electronics": "📺",
    "Plumbing": "🚿",
    "Cleaning": "🧹",
    "Other": "🔧",
}


def load_data() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE, dtype=str)
        if not df.empty:
            # Back-fill any new columns missing from older CSV files
            for col in FIELDNAMES:
                if col not in df.columns:
                    df[col] = ""
            return df[FIELDNAMES]
    return pd.DataFrame(columns=FIELDNAMES)


def save_data(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    # Ensure all columns are present before saving
    for col in FIELDNAMES:
        if col not in df.columns:
            df[col] = ""
    df[FIELDNAMES].to_csv(DATA_FILE, index=False)


def next_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1
    return int(df["id"].astype(int).max()) + 1


def days_until_expiry(expiry_str: str) -> int:
    try:
        expiry = datetime.strptime(str(expiry_str), "%Y-%m-%d").date()
        return (expiry - date.today()).days
    except (ValueError, TypeError):
        return INVALID_DATE_DAYS


def warranty_age_fraction(purchase_str: str, expiry_str: str) -> float:
    """Return how much of the warranty period has elapsed (0.0 – 1.0)."""
    try:
        start = datetime.strptime(str(purchase_str), "%Y-%m-%d").date()
        end = datetime.strptime(str(expiry_str), "%Y-%m-%d").date()
        total = (end - start).days
        if total <= 0:
            return 1.0
        elapsed = (date.today() - start).days
        return max(0.0, min(1.0, elapsed / total))
    except (ValueError, TypeError):
        return 0.0


# ── Page config & custom CSS ────────────────────────────────────────────────
st.set_page_config(page_title="Appliance Manager", page_icon="🏠", layout="wide")

st.markdown(
    """
    <style>
    /* ── Global typography ── */
    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }

    /* ── Metric cards ── */
    div[data-testid="metric-container"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="metric-container"] label {
        color: #64748b;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="metric-container"] div[data-testid="metric-value"] {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
    }

    /* ── Appliance cards ── */
    .appliance-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s;
    }
    .appliance-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.10); }
    .card-title { font-size: 1.15rem; font-weight: 700; color: #0f172a; margin: 0 0 2px; }
    .card-sub   { font-size: 0.88rem; color: #64748b; margin: 0; }
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-green  { background: #dcfce7; color: #166534; }
    .badge-yellow { background: #fef9c3; color: #854d0e; }
    .badge-red    { background: #fee2e2; color: #991b1b; }
    .detail-label { font-size: 0.78rem; font-weight: 600; color: #64748b;
                    text-transform: uppercase; letter-spacing: 0.04em; }
    .detail-value { font-size: 0.95rem; color: #0f172a; }

    /* ── Section header ── */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #0f172a;
        margin: 24px 0 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid #e2e8f0;
    }

    /* ── Sidebar form polish ── */
    section[data-testid="stSidebar"] { background: #f1f5f9; }
    section[data-testid="stSidebar"] .stTextInput > label,
    section[data-testid="stSidebar"] .stSelectbox > label,
    section[data-testid="stSidebar"] .stDateInput > label,
    section[data-testid="stSidebar"] .stTextArea > label {
        font-weight: 600;
        color: #334155;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("## 🏠 Appliance Manager")
st.markdown(
    "<p style='color:#64748b;margin-top:-8px;'>Track your home appliances, "
    "warranties & service history all in one place.</p>",
    unsafe_allow_html=True,
)

# ── Sidebar: Add Appliance ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ➕ Add New Appliance")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Appliance Name *", placeholder="e.g. Refrigerator")
        brand = st.text_input("Brand *", placeholder="e.g. Samsung")
        category = st.selectbox(
            "Category",
            ["Kitchen", "Laundry", "HVAC", "Electronics", "Plumbing", "Cleaning", "Other"],
        )
        model_number = st.text_input("Model Number", placeholder="e.g. RF28R7351SR")
        serial_number = st.text_input("Serial Number", placeholder="e.g. SN123456")
        purchase_price = st.text_input("Purchase Price (£)", placeholder="e.g. 799.99")
        purchase_date = st.date_input("Purchase Date", value=date.today())
        warranty_expiry = st.date_input(
            "Warranty Expiry", value=date.today() + timedelta(days=365)
        )
        last_service_date = st.date_input(
            "Last Service Date", value=None, help="Leave blank if never serviced."
        )
        notes = st.text_area("Notes", placeholder="Optional notes…")
        submitted = st.form_submit_button("✅ Add Appliance", use_container_width=True)

    if submitted:
        if not name or not brand:
            st.sidebar.error("Name and Brand are required.")
        else:
            df = load_data()
            new_row = pd.DataFrame(
                [
                    {
                        "id": next_id(df),
                        "name": name,
                        "brand": brand,
                        "category": category,
                        "purchase_date": str(purchase_date),
                        "warranty_expiry": str(warranty_expiry),
                        "serial_number": serial_number,
                        "model_number": model_number,
                        "purchase_price": purchase_price,
                        "last_service_date": str(last_service_date) if last_service_date else "",
                        "notes": notes,
                    }
                ]
            )
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.sidebar.success(f"✅ '{name}' added!")
            st.rerun()

# ── Load data ────────────────────────────────────────────────────────────────
df = load_data()

if df.empty:
    st.info("No appliances yet — add your first one using the sidebar! 👈")
    st.stop()

df["days_left"] = df["warranty_expiry"].apply(days_until_expiry)

# ── Summary metrics ──────────────────────────────────────────────────────────
total = len(df)
expired_count = int((df["days_left"] < 0).sum())
expiring_count = int(df["days_left"].between(0, REMINDER_DAYS).sum())
healthy_count = total - expired_count - expiring_count

m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Total Appliances", total)
m2.metric("✅ Active Warranties", healthy_count)
m3.metric("⚠️ Expiring Soon", expiring_count, help=f"Within {REMINDER_DAYS} days")
m4.metric("🔴 Expired", expired_count)

st.markdown("---")

# ── Alert banners ────────────────────────────────────────────────────────────
expired_df = df[df["days_left"] < 0]
expiring_soon_df = df[df["days_left"].between(0, REMINDER_DAYS)]

if not expired_df.empty:
    st.error(
        "🔴 **Expired warranties:** "
        + ", ".join(expired_df["name"].tolist())
    )

if not expiring_soon_df.empty:
    st.warning(
        f"⚠️ **Expiring within {REMINDER_DAYS} days:** "
        + ", ".join(
            f"{r['name']} ({r['days_left']}d)" for _, r in expiring_soon_df.iterrows()
        )
    )

# ── Toolbar: search, filter, download ───────────────────────────────────────
col_search, col_filter, col_dl = st.columns([3, 2, 1])

with col_search:
    search = st.text_input("🔍 Search", placeholder="Name, brand or model…", label_visibility="collapsed")

with col_filter:
    categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
    selected_cat = st.selectbox("Category", categories, label_visibility="collapsed")

with col_dl:
    export_df = df.drop(columns=["days_left"])
    export_df["warranty_status"] = df["days_left"].apply(
        lambda d: "Expired" if d < 0 else ("Expiring Soon" if d <= REMINDER_DAYS else "Active")
    )
    export_df["days_until_expiry"] = df["days_left"].apply(
        lambda d: d if d != INVALID_DATE_DAYS else ""
    )
    st.download_button(
        label="⬇️ CSV",
        data=export_df.to_csv(index=False).encode(),
        file_name="appliances.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ── Filter data ──────────────────────────────────────────────────────────────
view_df = df.copy()

if search:
    mask = (
        view_df["name"].str.contains(search, case=False, na=False)
        | view_df["brand"].str.contains(search, case=False, na=False)
        | view_df["model_number"].str.contains(search, case=False, na=False)
    )
    view_df = view_df[mask]

if selected_cat != "All":
    view_df = view_df[view_df["category"] == selected_cat]

# ── Appliance cards ──────────────────────────────────────────────────────────
st.markdown(
    f"<div class='section-header'>Your Appliances "
    f"<span style='font-weight:400;color:#64748b;font-size:1rem;'>({len(view_df)} shown)</span></div>",
    unsafe_allow_html=True,
)

if view_df.empty:
    st.info("No appliances match your search/filter.")
    st.stop()

for _, row in view_df.iterrows():
    days = int(row["days_left"])
    cat_icon = CATEGORY_ICONS.get(str(row.get("category", "")), "🔧")

    if days < 0:
        badge_cls = "badge-red"
        badge_txt = f"Expired {abs(days)}d ago"
        bar_color = "#ef4444"
        progress_val = 1.0
    elif days <= REMINDER_DAYS:
        badge_cls = "badge-yellow"
        badge_txt = f"Expires in {days}d"
        bar_color = "#f59e0b"
        progress_val = warranty_age_fraction(row["purchase_date"], row["warranty_expiry"])
    else:
        badge_cls = "badge-green"
        badge_txt = f"{days}d remaining"
        bar_color = "#22c55e"
        progress_val = warranty_age_fraction(row["purchase_date"], row["warranty_expiry"])

    # Build detail pills
    details_html = ""
    if row.get("model_number"):
        details_html += f"<span class='detail-label'>Model</span> <span class='detail-value'>{html.escape(str(row['model_number']))}</span> &nbsp;·&nbsp; "
    if row.get("serial_number"):
        details_html += f"<span class='detail-label'>S/N</span> <span class='detail-value'>{html.escape(str(row['serial_number']))}</span> &nbsp;·&nbsp; "
    if row.get("purchase_price"):
        details_html += f"<span class='detail-label'>Price</span> <span class='detail-value'>£{html.escape(str(row['purchase_price']))}</span> &nbsp;·&nbsp; "
    details_html = details_html.rstrip(" &nbsp;·&nbsp; ")

    esc_name = html.escape(str(row["name"]))
    esc_brand = html.escape(str(row["brand"]))
    esc_category = html.escape(str(row["category"]))
    esc_purchase_date = html.escape(str(row["purchase_date"]))
    esc_warranty_expiry = html.escape(str(row["warranty_expiry"]))

    with st.container():
        st.markdown(
            f"""
            <div class="appliance-card">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                  <p class="card-title">{cat_icon} {esc_name}</p>
                  <p class="card-sub">{esc_brand} &nbsp;·&nbsp; {esc_category}</p>
                </div>
                <span class="badge {badge_cls}">{badge_txt}</span>
              </div>
              {"<p style='margin:8px 0 4px;font-size:0.85rem;'>" + details_html + "</p>" if details_html else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Warranty progress bar
        pct = int(progress_val * 100)
        st.markdown(
            f"""
            <div style="margin:-12px 0 6px;">
              <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94a3b8;margin-bottom:3px;">
                <span>Purchased {esc_purchase_date}</span>
                <span>Expires {esc_warranty_expiry}</span>
              </div>
              <div style="height:6px;background:#e2e8f0;border-radius:999px;">
                <div style="height:6px;width:{pct}%;background:{bar_color};border-radius:999px;"></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Expandable details
        with st.expander("Details & Actions", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("Purchase Date", row["purchase_date"])
            c2.metric("Warranty Expiry", row["warranty_expiry"])
            c3.metric("Days Left", days if days != INVALID_DATE_DAYS else "—")

            c4, c5, c6 = st.columns(3)
            c4.metric("Model", row["model_number"] if row.get("model_number") else "—")
            c5.metric("Serial No.", row["serial_number"] if row.get("serial_number") else "—")
            c6.metric("Purchase Price", f"£{row['purchase_price']}" if row.get("purchase_price") else "—")

            if row.get("last_service_date"):
                st.markdown(f"🔧 **Last serviced:** {row['last_service_date']}")
            if row.get("notes"):
                st.markdown(f"📝 **Notes:** {row['notes']}")

            # Edit purchase price inline
            new_price = st.text_input(
                "Update Purchase Price (£)",
                value=row.get("purchase_price", ""),
                key=f"price_{row['id']}",
                placeholder="e.g. 499.99",
            )
            col_save, col_del = st.columns([1, 1])
            with col_save:
                if st.button("💾 Save Price", key=f"save_{row['id']}"):
                    updated = load_data()
                    updated.loc[updated["id"].astype(str) == str(row["id"]), "purchase_price"] = new_price
                    save_data(updated)
                    st.success("Price updated!")
                    st.rerun()
            with col_del:
                if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                    updated = load_data()
                    updated = updated[updated["id"].astype(str) != str(row["id"])]
                    save_data(updated)
                    st.success(f"'{row['name']}' deleted.")
                    st.rerun()

