import html
import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Constants ────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "appliances.csv")
METADATA_FILE = os.path.join(os.path.dirname(__file__), "data", "appliance_metadata.csv")

FIELDNAMES = [
    "id", "name", "brand", "category", "purchase_date", "warranty_expiry",
    "serial_number", "model_number", "purchase_price", "last_service_date", "notes",
]
METADATA_FIELDNAMES = [
    "appliance_type", "category", "typical_brands",
    "typical_warranty_years", "avg_lifespan_years", "avg_price_gbp",
]

CATEGORIES = ["Kitchen", "Laundry", "HVAC", "Electronics", "Plumbing", "Cleaning", "Other"]
REMINDER_DAYS = 30
INVALID_DATE_DAYS = 9999

CATEGORY_ICONS = {
    "Kitchen": "🍳", "Laundry": "👕", "HVAC": "❄️",
    "Electronics": "📺", "Plumbing": "🚿", "Cleaning": "🧹", "Other": "🔧",
}

# ── Data helpers ──────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE, dtype=str)
        if not df.empty:
            for col in FIELDNAMES:
                if col not in df.columns:
                    df[col] = ""
            return df[FIELDNAMES]
    return pd.DataFrame(columns=FIELDNAMES)


def save_data(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    for col in FIELDNAMES:
        if col not in df.columns:
            df[col] = ""
    df[FIELDNAMES].to_csv(DATA_FILE, index=False)


def load_metadata() -> pd.DataFrame:
    if os.path.exists(METADATA_FILE):
        mdf = pd.read_csv(METADATA_FILE, dtype=str)
        if not mdf.empty:
            for col in METADATA_FIELDNAMES:
                if col not in mdf.columns:
                    mdf[col] = ""
            return mdf[METADATA_FIELDNAMES]
    return pd.DataFrame(columns=METADATA_FIELDNAMES)


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


def get_warranty_status(days: int) -> str:
    if days < 0:
        return "Expired"
    if days <= REMINDER_DAYS:
        return "Expiring Soon"
    return "Active"


def _parse_date_input(val: str, fallback: date) -> date:
    try:
        return datetime.strptime(str(val), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return fallback


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Appliance Manager", page_icon="🏠", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "toast_shown" not in st.session_state:
    st.session_state.toast_shown = False

# ── CSS (light / dark) ────────────────────────────────────────────────────────
dark = st.session_state.dark_mode

# Colour tokens
_bg      = "#0f172a" if dark else "#ffffff"
_bg2     = "#1e293b" if dark else "#f8fafc"
_bg3     = "#1e293b" if dark else "#f1f5f9"
_card    = "#1e293b" if dark else "#ffffff"
_border  = "#334155" if dark else "#e2e8f0"
_txt     = "#f1f5f9" if dark else "#0f172a"
_txt2    = "#94a3b8" if dark else "#64748b"
_inp_bg  = "#0f172a" if dark else "#ffffff"

st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
    .stApp {{ background-color: {_bg}; }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{ background: {_bg3}; }}

    /* ── Metric cards ── */
    div[data-testid="metric-container"] {{
        background: {_bg2}; border: 1px solid {_border};
        border-radius: 12px; padding: 16px 20px;
    }}
    div[data-testid="metric-container"] label {{
        color: {_txt2}; font-size: 0.78rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.05em;
    }}
    div[data-testid="metric-container"] div[data-testid="metric-value"] {{
        font-size: 2rem; font-weight: 700; color: {_txt};
    }}

    /* ── Appliance cards ── */
    .appliance-card {{
        background: {_card}; border: 1px solid {_border};
        border-radius: 14px; padding: 20px 24px; margin-bottom: 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06); transition: box-shadow 0.2s;
    }}
    .appliance-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.12); }}
    .card-title {{ font-size: 1.15rem; font-weight: 700; color: {_txt}; margin: 0 0 2px; }}
    .card-sub   {{ font-size: 0.88rem; color: {_txt2}; margin: 0; }}

    /* ── Badges ── */
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px;
              font-size: 0.78rem; font-weight: 600; }}
    .badge-green  {{ background: #dcfce7; color: #166534; }}
    .badge-yellow {{ background: #fef9c3; color: #854d0e; }}
    .badge-red    {{ background: #fee2e2; color: #991b1b; }}

    /* ── Detail pills ── */
    .detail-label {{ font-size: 0.78rem; font-weight: 600; color: {_txt2};
                     text-transform: uppercase; letter-spacing: 0.04em; }}
    .detail-value {{ font-size: 0.95rem; color: {_txt}; }}

    /* ── Section header ── */
    .section-header {{
        font-size: 1.25rem; font-weight: 700; color: {_txt};
        margin: 20px 0 10px; padding-bottom: 8px;
        border-bottom: 2px solid {_border};
    }}

    /* ── Dark-mode input overrides ── */
    {"" if not dark else f"""
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb],
    .stDateInput input, .stNumberInput input {{
        background-color: {_inp_bg} !important;
        color: {_txt} !important;
        border-color: {_border} !important;
    }}
    .stMarkdown, .stText, p, span, label, div {{ color: {_txt}; }}
    .stTabs [data-baseweb="tab-list"] {{ background-color: {_bg}; }}
    .stTabs [data-baseweb="tab"] {{ color: {_txt2}; }}
    .stTabs [aria-selected="true"] {{ color: {_txt}; }}
    """}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([9, 1])
with hc1:
    st.markdown(f"## 🏠 Appliance Manager")
    st.markdown(
        f"<p style='color:{_txt2};margin-top:-8px;'>"
        "Track your home appliances, warranties &amp; service history.</p>",
        unsafe_allow_html=True,
    )
with hc2:
    btn_label = "☀️ Light" if dark else "🌙 Dark"
    if st.button(btn_label, use_container_width=True, key="hdr_dark_toggle"):
        st.session_state.dark_mode = not dark
        st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────────
df = load_data()
meta_df = load_metadata()

if not df.empty:
    df["days_left"] = df["warranty_expiry"].apply(days_until_expiry)

# ── Toast notifications (once per session) ────────────────────────────────────
if not df.empty and not st.session_state.toast_shown:
    expired_n = int((df["days_left"] < 0).sum())
    expiring_n = int(df["days_left"].between(0, REMINDER_DAYS).sum())
    if expired_n:
        st.toast(f"🔴 {expired_n} appliance(s) have expired warranties!", icon="🔴")
    if expiring_n:
        st.toast(f"⚠️ {expiring_n} appliance(s) expiring within {REMINDER_DAYS} days!", icon="⚠️")
    st.session_state.toast_shown = True

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_dash, tab_appl, tab_add, tab_edit, tab_bulk, tab_settings = st.tabs([
    "📊 Dashboard", "🏠 Appliances", "➕ Add", "✏️ Edit", "🔄 Bulk Ops", "⚙️ Settings",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 – DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    if df.empty:
        st.info("No appliances yet — head to the ➕ Add tab to get started!")
    else:
        total = len(df)
        expired_count  = int((df["days_left"] < 0).sum())
        expiring_count = int(df["days_left"].between(0, REMINDER_DAYS).sum())
        healthy_count  = total - expired_count - expiring_count
        prices = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0)
        total_value = float(prices.sum())

        # ── Metrics row ──
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("📦 Total", total)
        m2.metric("✅ Active", healthy_count)
        m3.metric("⚠️ Expiring Soon", expiring_count, help=f"Within {REMINDER_DAYS} days")
        m4.metric("🔴 Expired", expired_count)
        m5.metric("💰 Total Value", f"£{total_value:,.0f}")

        # ── Alert banners ──
        exp_df  = df[df["days_left"] < 0]
        soon_df = df[df["days_left"].between(0, REMINDER_DAYS)]
        if not exp_df.empty:
            st.error("🔴 **Expired:** " + ", ".join(exp_df["name"].tolist()))
        if not soon_df.empty:
            st.warning(
                f"⚠️ **Expiring within {REMINDER_DAYS} days:** "
                + ", ".join(f"{r['name']} ({r['days_left']}d)" for _, r in soon_df.iterrows())
            )

        st.markdown("---")

        # ── Row 1: category pie + warranty status bar ──
        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("<div class='section-header'>Category Breakdown</div>", unsafe_allow_html=True)
            cat_counts = df["category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            cat_counts["Label"] = cat_counts["Category"].map(
                lambda c: f"{CATEGORY_ICONS.get(c, '🔧')} {c}"
            )
            fig_pie = px.pie(
                cat_counts, names="Label", values="Count", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(
                showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=_txt,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with ch2:
            st.markdown("<div class='section-header'>Warranty Status</div>", unsafe_allow_html=True)
            df["_status"] = df["days_left"].apply(get_warranty_status)
            status_counts = df["_status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_bar = px.bar(
                status_counts, x="Status", y="Count", color="Status",
                color_discrete_map={
                    "Active": "#22c55e", "Expiring Soon": "#f59e0b", "Expired": "#ef4444",
                },
                text_auto=True,
            )
            fig_bar.update_layout(
                showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=_txt,
                xaxis=dict(color=_txt, showgrid=False),
                yaxis=dict(color=_txt, showgrid=True, gridcolor=_border),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── Row 2: warranty Gantt timeline ──
        st.markdown("<div class='section-header'>Warranty Expiry Timeline</div>", unsafe_allow_html=True)
        tl = df[df["warranty_expiry"].str.match(r"\d{4}-\d{2}-\d{2}", na=False)].copy()
        tl["purchase_dt"] = pd.to_datetime(tl["purchase_date"], errors="coerce")
        tl["expiry_dt"]   = pd.to_datetime(tl["warranty_expiry"], errors="coerce")
        tl = tl.dropna(subset=["purchase_dt", "expiry_dt"])
        tl["Status"] = tl["days_left"].apply(get_warranty_status)
        if not tl.empty:
            fig_gantt = px.timeline(
                tl, x_start="purchase_dt", x_end="expiry_dt", y="name",
                color="Status",
                color_discrete_map={
                    "Active": "#22c55e", "Expiring Soon": "#f59e0b", "Expired": "#ef4444",
                },
            )
            fig_gantt.update_yaxes(autorange="reversed")
            today_ts = pd.Timestamp(date.today()).value / 1e6  # ms for timeline axis
            fig_gantt.add_vline(
                x=today_ts, line_dash="dash", line_color=_txt2,
            )
            fig_gantt.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=max(300, len(tl) * 32),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=_txt,
                xaxis=dict(color=_txt, showgrid=True, gridcolor=_border),
                yaxis=dict(color=_txt),
            )
            st.plotly_chart(fig_gantt, use_container_width=True)

        # ── Row 3: cost analysis ──
        st.markdown("<div class='section-header'>Cost Analysis by Category</div>", unsafe_allow_html=True)
        cost_df = df.copy()
        cost_df["price_num"] = pd.to_numeric(cost_df["purchase_price"], errors="coerce").fillna(0)
        cost_by_cat = (
            cost_df.groupby("category")["price_num"]
            .sum().reset_index()
            .rename(columns={"category": "Category", "price_num": "Total (£)"})
        )
        cost_by_cat = cost_by_cat[cost_by_cat["Total (£)"] > 0].sort_values("Total (£)", ascending=False)
        if not cost_by_cat.empty:
            fig_cost = px.bar(
                cost_by_cat, x="Category", y="Total (£)", color="Category",
                color_discrete_sequence=px.colors.qualitative.Set3,
                text_auto=".2s",
            )
            fig_cost.update_layout(
                showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=_txt,
                xaxis=dict(color=_txt, showgrid=False),
                yaxis=dict(color=_txt, showgrid=True, gridcolor=_border),
            )
            st.plotly_chart(fig_cost, use_container_width=True)

        # Clean up temporary column
        df.drop(columns=["_status"], inplace=True, errors="ignore")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 – APPLIANCES  (advanced filtering + cards)
# ══════════════════════════════════════════════════════════════════════════════
with tab_appl:
    if df.empty:
        st.info("No appliances yet — head to the ➕ Add tab to get started!")
    else:
        # ── Filter bar ──
        with st.expander("🔍 Search & Filter", expanded=True):
            fa, fb, fc = st.columns(3)
            with fa:
                search = st.text_input("Search", placeholder="Name, brand or model…")
            with fb:
                all_cats = sorted(df["category"].dropna().unique().tolist())
                sel_cats = st.multiselect("Categories", all_cats, default=all_cats)
            with fc:
                status_opts = ["Active", "Expiring Soon", "Expired"]
                sel_status = st.multiselect("Warranty Status", status_opts, default=status_opts)

            fd, fe, ff = st.columns(3)
            with fd:
                sort_by = st.selectbox(
                    "Sort By", ["Days Remaining", "Purchase Date", "Price (£)", "Name"]
                )
            with fe:
                sort_asc = st.radio("Order", ["Ascending", "Descending"], horizontal=True) == "Ascending"
            with ff:
                nums = pd.to_numeric(df["purchase_price"], errors="coerce").dropna()
                p_min = float(nums.min()) if not nums.empty else 0.0
                p_max = float(nums.max()) if not nums.empty else 9999.0
                price_range = st.slider(
                    "Price Range (£)", 0.0, max(p_max, 1.0),
                    (0.0, max(p_max, 1.0)), step=10.0,
                )

        # Download button row
        dl_c, cnt_c = st.columns([1, 4])
        with dl_c:
            _exp = df.drop(columns=["days_left"], errors="ignore").copy()
            _exp["warranty_status"] = df["days_left"].apply(get_warranty_status)
            st.download_button(
                "⬇️ Download CSV",
                data=_exp.to_csv(index=False).encode(),
                file_name="appliances.csv", mime="text/csv",
                use_container_width=True,
            )

        # Apply filters
        view_df = df.copy()
        view_df["_status"]    = view_df["days_left"].apply(get_warranty_status)
        view_df["_price_num"] = pd.to_numeric(view_df["purchase_price"], errors="coerce").fillna(0)

        if search:
            mask = (
                view_df["name"].str.contains(search, case=False, na=False)
                | view_df["brand"].str.contains(search, case=False, na=False)
                | view_df["model_number"].str.contains(search, case=False, na=False)
            )
            view_df = view_df[mask]
        if sel_cats:
            view_df = view_df[view_df["category"].isin(sel_cats)]
        if sel_status:
            view_df = view_df[view_df["_status"].isin(sel_status)]
        view_df = view_df[
            (view_df["_price_num"] >= price_range[0]) & (view_df["_price_num"] <= price_range[1])
        ]

        sort_col_map = {
            "Days Remaining": "days_left", "Purchase Date": "purchase_date",
            "Price (£)": "_price_num", "Name": "name",
        }
        view_df = view_df.sort_values(sort_col_map[sort_by], ascending=sort_asc)

        with cnt_c:
            st.markdown(
                f"<p style='padding-top:8px;color:{_txt2};'>{len(view_df)} appliance(s) shown</p>",
                unsafe_allow_html=True,
            )

        if view_df.empty:
            st.info("No appliances match your filters.")
        else:
            for _, row in view_df.iterrows():
                days     = int(row["days_left"])
                cat_icon = CATEGORY_ICONS.get(str(row.get("category", "")), "🔧")

                if days < 0:
                    badge_cls, badge_txt, bar_color = "badge-red",    f"Expired {abs(days)}d ago", "#ef4444"
                    progress_val = 1.0
                elif days <= REMINDER_DAYS:
                    badge_cls, badge_txt, bar_color = "badge-yellow", f"Expires in {days}d",       "#f59e0b"
                    progress_val = warranty_age_fraction(row["purchase_date"], row["warranty_expiry"])
                else:
                    badge_cls, badge_txt, bar_color = "badge-green",  f"{days}d remaining",        "#22c55e"
                    progress_val = warranty_age_fraction(row["purchase_date"], row["warranty_expiry"])

                det = ""
                if row.get("model_number"):
                    det += f"<span class='detail-label'>Model</span> <span class='detail-value'>{html.escape(str(row['model_number']))}</span> &nbsp;·&nbsp; "
                if row.get("serial_number"):
                    det += f"<span class='detail-label'>S/N</span> <span class='detail-value'>{html.escape(str(row['serial_number']))}</span> &nbsp;·&nbsp; "
                if row.get("purchase_price"):
                    det += f"<span class='detail-label'>Price</span> <span class='detail-value'>£{html.escape(str(row['purchase_price']))}</span> &nbsp;·&nbsp; "
                det = det.rstrip(" &nbsp;·&nbsp; ")

                esc = {k: html.escape(str(v)) for k, v in row.items()}

                with st.container():
                    st.markdown(
                        f"""
                        <div class="appliance-card">
                          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div>
                              <p class="card-title">{cat_icon} {esc['name']}</p>
                              <p class="card-sub">{esc['brand']} &nbsp;·&nbsp; {esc['category']}</p>
                            </div>
                            <span class="badge {badge_cls}">{badge_txt}</span>
                          </div>
                          {"<p style='margin:8px 0 4px;font-size:0.85rem;'>" + det + "</p>" if det else ""}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    pct = int(progress_val * 100)
                    st.markdown(
                        f"""
                        <div style="margin:-12px 0 6px;">
                          <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:{_txt2};margin-bottom:3px;">
                            <span>Purchased {esc['purchase_date']}</span>
                            <span>Expires {esc['warranty_expiry']}</span>
                          </div>
                          <div style="height:6px;background:{_border};border-radius:999px;">
                            <div style="height:6px;width:{pct}%;background:{bar_color};border-radius:999px;"></div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    with st.expander("Details & Actions", expanded=False):
                        d1, d2, d3 = st.columns(3)
                        d1.metric("Purchase Date",   row["purchase_date"])
                        d2.metric("Warranty Expiry", row["warranty_expiry"])
                        d3.metric("Days Left", days if days != INVALID_DATE_DAYS else "—")

                        d4, d5, d6 = st.columns(3)
                        d4.metric("Model",          row["model_number"]  if row.get("model_number")  else "—")
                        d5.metric("Serial No.",     row["serial_number"] if row.get("serial_number") else "—")
                        d6.metric("Purchase Price", f"£{row['purchase_price']}" if row.get("purchase_price") else "—")

                        if row.get("last_service_date"):
                            st.markdown(f"🔧 **Last serviced:** {row['last_service_date']}")
                        if row.get("notes"):
                            st.markdown(f"📝 **Notes:** {row['notes']}")

                        btn1, btn2, btn3 = st.columns(3)
                        with btn1:
                            if st.button("✏️ Edit", key=f"edit_{row['id']}", use_container_width=True):
                                st.session_state.edit_id = str(row["id"])
                                st.rerun()
                        with btn2:
                            if st.button("📋 Duplicate", key=f"dup_{row['id']}", use_container_width=True):
                                current = load_data()
                                dup = {k: row[k] for k in FIELDNAMES}
                                dup["id"]   = next_id(current)
                                dup["name"] = f"{row['name']} (copy)"
                                current = pd.concat([current, pd.DataFrame([dup])], ignore_index=True)
                                save_data(current)
                                st.success(f"Duplicated '{row['name']}'!")
                                st.rerun()
                        with btn3:
                            if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                                current = load_data()
                                current = current[current["id"].astype(str) != str(row["id"])]
                                save_data(current)
                                st.success(f"'{row['name']}' deleted.")
                                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 – ADD APPLIANCE  (with metadata template hints)
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.markdown("<div class='section-header'>➕ Add New Appliance</div>", unsafe_allow_html=True)

    # Metadata template picker (outside form so it reruns page on change)
    meta_types = ["— Custom (no template) —"] + meta_df["appliance_type"].tolist()
    sel_meta = st.selectbox("Quick-fill from template", meta_types, key="add_meta_sel")

    meta_hint: dict = {}
    if sel_meta != "— Custom (no template) —":
        match = meta_df[meta_df["appliance_type"] == sel_meta]
        if not match.empty:
            meta_hint = match.iloc[0].to_dict()

    hint_brands     = [b.strip() for b in str(meta_hint.get("typical_brands", "")).split(";") if b.strip()]
    hint_category   = meta_hint.get("category", "Kitchen")
    hint_warranty_y = int(float(meta_hint.get("typical_warranty_years", 2) or 2))
    hint_price      = str(meta_hint.get("avg_price_gbp", ""))
    hint_lifespan   = str(meta_hint.get("avg_lifespan_years", ""))

    if meta_hint:
        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.info(f"⏱️ Warranty: {hint_warranty_y} yr")
        hc2.info(f"📅 Lifespan: {hint_lifespan} yr")
        hc3.info(f"💰 Avg price: £{hint_price}")
        if hint_brands:
            hc4.info(f"🏷️ {', '.join(hint_brands[:3])}")

    with st.form("add_form", clear_on_submit=True):
        ca, cb = st.columns(2)
        with ca:
            default_name = sel_meta if sel_meta != "— Custom (no template) —" else ""
            a_name   = st.text_input("Appliance Name *", value=default_name, placeholder="e.g. Refrigerator")
            a_brand  = st.text_input(
                "Brand *",
                placeholder=f"e.g. {hint_brands[0] if hint_brands else 'Samsung'}",
            )
            cat_idx  = CATEGORIES.index(hint_category) if hint_category in CATEGORIES else 0
            a_cat    = st.selectbox("Category", CATEGORIES, index=cat_idx)
        with cb:
            a_model  = st.text_input("Model Number",    placeholder="e.g. RF28R7351SR")
            a_serial = st.text_input("Serial Number",   placeholder="e.g. SN123456")
            a_price  = st.text_input("Purchase Price (£)", value=hint_price, placeholder="e.g. 799.99")

        cc, cd = st.columns(2)
        with cc:
            a_purchase = st.date_input("Purchase Date", value=date.today())
        with cd:
            a_expiry   = st.date_input(
                "Warranty Expiry",
                value=date.today() + timedelta(days=hint_warranty_y * 365),
            )

        a_service = st.date_input("Last Service Date", value=None,
                                  help="Leave blank if never serviced.")
        a_notes   = st.text_area("Notes", placeholder="Optional notes…")

        if hint_brands:
            st.caption(f"💡 Suggested brands for {sel_meta}: {', '.join(hint_brands)}")

        add_submitted = st.form_submit_button("✅ Add Appliance", use_container_width=True)

    if add_submitted:
        if not a_name or not a_brand:
            st.error("Name and Brand are required.")
        else:
            current = load_data()
            new_row = pd.DataFrame([{
                "id":               next_id(current),
                "name":             a_name,
                "brand":            a_brand,
                "category":         a_cat,
                "purchase_date":    str(a_purchase),
                "warranty_expiry":  str(a_expiry),
                "serial_number":    a_serial,
                "model_number":     a_model,
                "purchase_price":   a_price,
                "last_service_date": str(a_service) if a_service else "",
                "notes":            a_notes,
            }])
            current = pd.concat([current, new_row], ignore_index=True)
            save_data(current)
            st.success(f"✅ '{a_name}' added successfully!")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 – EDIT APPLIANCE
# ══════════════════════════════════════════════════════════════════════════════
with tab_edit:
    st.markdown("<div class='section-header'>✏️ Edit Appliance</div>", unsafe_allow_html=True)

    if df.empty:
        st.info("No appliances available to edit.")
    else:
        # Build selector options
        name_map = {
            str(r["id"]): f"{CATEGORY_ICONS.get(str(r['category']), '🔧')} {r['name']} ({r['brand']})"
            for _, r in df.iterrows()
        }
        ids = list(name_map.keys())

        # Pre-select if Edit was clicked from Appliances tab
        default_idx = 0
        if st.session_state.edit_id and st.session_state.edit_id in ids:
            default_idx = ids.index(st.session_state.edit_id)

        sel_edit_id = st.selectbox(
            "Select appliance to edit",
            options=ids, format_func=lambda x: name_map[x],
            index=default_idx, key="edit_selector",
        )

        row = df[df["id"].astype(str) == str(sel_edit_id)].iloc[0]

        with st.form("edit_form"):
            ea, eb = st.columns(2)
            with ea:
                e_name   = st.text_input("Appliance Name *", value=str(row.get("name", "")))
                e_brand  = st.text_input("Brand *",          value=str(row.get("brand", "")))
                e_cat_i  = CATEGORIES.index(str(row.get("category", ""))) if str(row.get("category", "")) in CATEGORIES else 0
                e_cat    = st.selectbox("Category", CATEGORIES, index=e_cat_i)
            with eb:
                e_model  = st.text_input("Model Number",        value=str(row.get("model_number", "")))
                e_serial = st.text_input("Serial Number",       value=str(row.get("serial_number", "")))
                e_price  = st.text_input("Purchase Price (£)",  value=str(row.get("purchase_price", "")))

            ec, ed = st.columns(2)
            with ec:
                e_purchase = st.date_input(
                    "Purchase Date",
                    value=_parse_date_input(row.get("purchase_date", ""), date.today()),
                )
            with ed:
                e_expiry = st.date_input(
                    "Warranty Expiry",
                    value=_parse_date_input(row.get("warranty_expiry", ""),
                                            date.today() + timedelta(days=365)),
                )

            last_service_val = _parse_date_input(str(row.get("last_service_date", "")), None)
            e_service = st.date_input("Last Service Date", value=last_service_val)
            e_notes   = st.text_area("Notes", value=str(row.get("notes", "")))

            save_col, del_col = st.columns(2)
            with save_col:
                save_btn = st.form_submit_button("💾 Save Changes",    use_container_width=True)
            with del_col:
                del_btn  = st.form_submit_button("🗑️ Delete Appliance", use_container_width=True)

        if save_btn:
            if not e_name or not e_brand:
                st.error("Name and Brand are required.")
            else:
                current = load_data()
                mask = current["id"].astype(str) == str(sel_edit_id)
                current.loc[mask, "name"]             = e_name
                current.loc[mask, "brand"]            = e_brand
                current.loc[mask, "category"]         = e_cat
                current.loc[mask, "model_number"]     = e_model
                current.loc[mask, "serial_number"]    = e_serial
                current.loc[mask, "purchase_price"]   = e_price
                current.loc[mask, "purchase_date"]    = str(e_purchase)
                current.loc[mask, "warranty_expiry"]  = str(e_expiry)
                current.loc[mask, "last_service_date"] = str(e_service) if e_service else ""
                current.loc[mask, "notes"]            = e_notes
                save_data(current)
                st.success(f"✅ '{e_name}' updated!")
                st.session_state.edit_id = None
                st.rerun()

        if del_btn:
            current = load_data()
            current = current[current["id"].astype(str) != str(sel_edit_id)]
            save_data(current)
            st.success("Appliance deleted.")
            st.session_state.edit_id = None
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 – BULK OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab_bulk:
    st.markdown("<div class='section-header'>🔄 Bulk Operations</div>", unsafe_allow_html=True)

    if df.empty:
        st.info("No appliances available for bulk operations.")
    else:
        st.markdown("Tick the appliances you want to act on, then choose an action below.")

        select_all = st.checkbox("☑️ Select All", key="bulk_select_all")
        selected_ids: list[str] = []

        for _, row in df.iterrows():
            days   = int(row["days_left"])
            status = get_warranty_status(days)
            icon   = CATEGORY_ICONS.get(str(row.get("category", "")), "🔧")
            badge  = {"Active": "🟢", "Expiring Soon": "🟡", "Expired": "🔴"}.get(status, "⚪")
            checked = st.checkbox(
                f"{icon} **{row['name']}** — {row['brand']}  {badge} {status}",
                value=select_all, key=f"bulk_chk_{row['id']}",
            )
            if checked:
                selected_ids.append(str(row["id"]))

        st.markdown("---")

        if selected_ids:
            st.markdown(f"**{len(selected_ids)} appliance(s) selected**")
            ba, bb = st.columns(2)

            with ba:
                if st.button("🗑️ Delete Selected", use_container_width=True, type="primary"):
                    current = load_data()
                    current = current[~current["id"].astype(str).isin(selected_ids)]
                    save_data(current)
                    st.success(f"Deleted {len(selected_ids)} appliance(s).")
                    st.rerun()

            with bb:
                sel_rows = df[df["id"].astype(str).isin(selected_ids)].copy()
                sel_rows["warranty_status"] = sel_rows["days_left"].apply(get_warranty_status)
                sel_export = sel_rows.drop(columns=["days_left"], errors="ignore")
                st.download_button(
                    "⬇️ Export Selected as CSV",
                    data=sel_export.to_csv(index=False).encode(),
                    file_name="selected_appliances.csv", mime="text/csv",
                    use_container_width=True,
                )

            st.markdown("#### Batch-update Warranty Expiry")
            new_date = st.date_input(
                "New Warranty Expiry Date",
                value=date.today() + timedelta(days=365), key="bulk_warranty_date",
            )
            if st.button("📅 Apply to Selected", use_container_width=True):
                current = load_data()
                current.loc[
                    current["id"].astype(str).isin(selected_ids), "warranty_expiry"
                ] = str(new_date)
                save_data(current)
                st.success(f"Updated warranty dates for {len(selected_ids)} appliance(s).")
                st.rerun()
        else:
            st.info("Select at least one appliance to enable bulk actions.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 – SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("<div class='section-header'>⚙️ Settings</div>", unsafe_allow_html=True)

    # ── Appearance ──
    st.markdown("#### 🎨 Appearance")
    new_dark = st.toggle("Dark Mode", value=dark, key="settings_dark_toggle")
    if new_dark != dark:
        st.session_state.dark_mode = new_dark
        st.rerun()

    st.markdown("---")

    # ── Data downloads ──
    st.markdown("#### 📥 Data Downloads")
    dl1, dl2 = st.columns(2)

    with dl1:
        if not df.empty:
            exp = df.drop(columns=["days_left"], errors="ignore").copy()
            exp["warranty_status"] = df["days_left"].apply(get_warranty_status)
            st.download_button(
                "⬇️ Download Appliances CSV",
                data=exp.to_csv(index=False).encode(),
                file_name="appliances.csv", mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No appliances data to download.")

    with dl2:
        st.download_button(
            "⬇️ Download Metadata CSV",
            data=meta_df.to_csv(index=False).encode(),
            file_name="appliance_metadata.csv", mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")

    # ── About ──
    st.markdown("#### ℹ️ About")
    st.markdown(
        """
        **Appliance Manager** v2.0

        Track your home appliances, warranties & service history all in one place.

        | Tab | Purpose |
        |---|---|
        | 📊 Dashboard | Charts: category breakdown, warranty status, timeline, costs |
        | 🏠 Appliances | Browse, search, filter and manage all appliances |
        | ➕ Add | Add a new appliance with smart template hints |
        | ✏️ Edit | Full edit form for any existing appliance |
        | 🔄 Bulk Ops | Multi-select delete, export & batch warranty updates |
        | ⚙️ Settings | Theme toggle and CSV downloads |
        """
    )

