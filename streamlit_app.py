import html
import os
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Constants ────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "appliances.csv")
METADATA_FILE = os.path.join(os.path.dirname(__file__), "data", "appliance_metadata.csv")

FIELDNAMES = [
    "id", "name", "brand", "category", "purchase_date", "warranty_expiry",
    "serial_number", "model_number", "purchase_price", "last_service_date", "notes",
    "manual_url",
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


# ── Troubleshooting knowledge base ───────────────────────────────────────────
TROUBLESHOOT_GUIDE: dict[str, list[dict]] = {
    "Kitchen": [
        {
            "symptom": "Refrigerator not cooling",
            "steps": [
                "Check the appliance is plugged in and the circuit breaker has not tripped.",
                "Clean the condenser coils (at the back or beneath the unit).",
                "Inspect door seals for gaps or cracks; replace if damaged.",
                "Ensure internal vents are not blocked by food items.",
                "Verify temperature is set to 2–4 °C (fridge) / -18 °C (freezer).",
            ],
            "pro_tip": "Persistent warm temperatures despite correct settings may indicate a failing compressor or refrigerant leak — contact a qualified engineer.",
        },
        {
            "symptom": "Dishwasher not draining",
            "steps": [
                "Remove and clean the filter basket at the bottom of the dishwasher.",
                "Check the drain hose for kinks or blockages.",
                "If newly installed, ensure the garbage-disposal knockout plug has been removed.",
                "Run the garbage disposal (if present) to clear the shared drain line.",
                "Check the door latch is fully closing — the pump only runs when door is sealed.",
            ],
            "pro_tip": "A faulty drain pump motor usually requires replacement by a technician.",
        },
        {
            "symptom": "Oven not heating evenly",
            "steps": [
                "Allow 15–20 minutes for full preheat before placing food inside.",
                "Place bakeware on the centre rack for best circulation.",
                "Use an oven thermometer to verify the actual internal temperature.",
                "Clean any burnt residue from the heating elements or oven floor.",
                "Ensure the convection fan (if present) is not obstructed.",
            ],
            "pro_tip": "A burnt-out bake or broil element can often be replaced as a DIY task — consult the service manual for part numbers.",
        },
        {
            "symptom": "Microwave not heating",
            "steps": [
                "Check the door latch closes completely — the interlock prevents operation when open.",
                "Confirm the appliance is not in demo/display mode (consult manual to disable).",
                "Unplug for 60 seconds, then reconnect (soft reset).",
                "Check and replace the door fuse if accessible (refer to manual).",
            ],
            "pro_tip": "The magnetron and high-voltage capacitor are dangerous to handle — magnetron replacement must be done by a qualified engineer.",
        },
    ],
    "Laundry": [
        {
            "symptom": "Washing machine not draining / leaving water in drum",
            "steps": [
                "Clean the pump filter / coin trap (usually behind a small door at the front bottom).",
                "Inspect the drain hose for kinks, and ensure the drain outlet is no higher than 1 metre from the floor.",
                "Run a Rinse & Spin cycle to test drainage.",
                "Check that the selected programme has a spin/drain phase enabled.",
            ],
            "pro_tip": "A faulty drain pump needs professional replacement.",
        },
        {
            "symptom": "Washing machine vibrating excessively",
            "steps": [
                "Level all four adjustable feet firmly on the floor.",
                "Remove shipping bolts from the back (present on new machines — check the manual).",
                "Reduce load size — overloading causes drum imbalance.",
                "Redistribute clothing evenly inside the drum.",
            ],
            "pro_tip": "Loud grinding during spin often indicates worn drum bearings — a service call is recommended.",
        },
        {
            "symptom": "Tumble dryer not drying clothes",
            "steps": [
                "Clean the lint filter before every drying cycle.",
                "Ensure the exhaust vent hose is not kinked, crushed, or blocked at the outside vent.",
                "Dry smaller loads — overloading significantly reduces efficiency.",
                "Select the correct heat setting for the fabric type.",
                "For heat-pump dryers, empty the condensate water tank and clean the heat-exchanger filter.",
            ],
            "pro_tip": "A faulty heating element or thermostat requires professional diagnosis.",
        },
    ],
    "HVAC": [
        {
            "symptom": "Air conditioner not cooling",
            "steps": [
                "Check and replace or wash the air filter if dirty (recommended monthly in heavy use).",
                "Ensure the thermostat is set at least 2 °C below the current room temperature.",
                "Inspect the outdoor unit — clear leaves, dust, and debris from the fins.",
                "Close all windows and doors to prevent warm air ingress.",
                "Check the remote batteries and try operating from the unit's manual controls.",
            ],
            "pro_tip": "Ice on the refrigerant pipes or warm air from the indoor unit while the compressor runs outside indicates low refrigerant — only a Gas Safe / F-Gas certified engineer may top this up.",
        },
        {
            "symptom": "Boiler not producing hot water or heating",
            "steps": [
                "Check the boiler pressure gauge — it should read 1–1.5 bar when cold; re-pressurise if low using the filling loop.",
                "Press the reset button on the boiler and wait 5 minutes.",
                "Ensure the gas supply is on and the pilot light (if applicable) is lit.",
                "Verify the programmer / thermostat schedule and temperature settings.",
                "Bleed radiators to remove trapped air if individual radiators are cold at the top.",
            ],
            "pro_tip": "Boiler faults (especially error codes, gas smells, or repeated lock-outs) must be diagnosed by a Gas Safe registered engineer.",
        },
        {
            "symptom": "Strange smell from HVAC unit",
            "steps": [
                "Replace or wash the air filter.",
                "Inspect vents and grilles for visible mould; clean with a diluted bleach solution (1:10).",
                "Ensure the condensate drain pan is not overflowing — clear blockages.",
                "Run the system for 15 minutes with a window slightly open to air out.",
            ],
            "pro_tip": "A burning smell may indicate an electrical fault — turn the unit off immediately and contact a qualified engineer.",
        },
    ],
    "Electronics": [
        {
            "symptom": "TV not turning on",
            "steps": [
                "Check the power cable and try a different wall outlet.",
                "Press the physical power button on the TV (not just the remote).",
                "Replace the remote control batteries.",
                "Unplug the TV for 30 seconds, then reconnect (cold reset).",
                "Check for a standby indicator light — if present, the panel or mainboard may be faulty.",
            ],
            "pro_tip": "No backlight (sound but black screen) usually indicates a faulty backlight inverter or LED strip — professional repair required.",
        },
        {
            "symptom": "Laptop overheating / shutting down",
            "steps": [
                "Clean the ventilation grilles with compressed air (do not use a vacuum directly).",
                "Ensure the laptop is placed on a hard, flat surface — not on a bed or cushion.",
                "Check Task Manager / Activity Monitor for processes maxing out the CPU.",
                "Use a laptop cooling pad for extended sessions.",
                "Update the BIOS/firmware — manufacturers often release thermal management improvements.",
            ],
            "pro_tip": "If the fan is noisy or not spinning, or if overheating persists after cleaning, thermal paste reapplication by a technician is likely needed.",
        },
        {
            "symptom": "Printer not printing",
            "steps": [
                "Check ink or toner levels and replace cartridges if low.",
                "Clear the print queue: Settings → Printers & Scanners → Open Queue → Cancel All.",
                "Restart both the printer and the computer.",
                "Delete and reinstall the printer driver from the manufacturer's website.",
                "For inkjet printers, run the built-in print-head cleaning utility.",
            ],
            "pro_tip": "Severe print-head clogging on inkjet printers may require a soak in warm distilled water or a replacement print head.",
        },
    ],
    "Plumbing": [
        {
            "symptom": "Water heater not producing hot water",
            "steps": [
                "Verify the thermostat is set to 60 °C (minimum to prevent Legionella).",
                "For gas units: check the pilot light is lit and the gas supply valve is open.",
                "For electric units: check the circuit breaker and reset the high-temperature cut-off switch (usually a red button on the unit).",
                "Flush sediment from the tank annually: connect a hose to the drain valve and run until water runs clear.",
            ],
            "pro_tip": "Anode rod inspection and replacement every 3–5 years significantly extends tank life — consult a plumber.",
        },
        {
            "symptom": "Boiler pressure keeps dropping",
            "steps": [
                "Check all radiator valves are fully open.",
                "Inspect visible pipes and fittings for drips or damp patches.",
                "Re-pressurise via the filling loop to 1–1.5 bar.",
                "Bleed radiators to remove air that may be masking a pressure issue.",
            ],
            "pro_tip": "A system that requires regular re-pressurisation has a leak — call a Gas Safe registered engineer to locate and repair it.",
        },
    ],
    "Cleaning": [
        {
            "symptom": "Vacuum cleaner losing suction",
            "steps": [
                "Empty the dustbin or replace the bag.",
                "Wash or replace the filters (check the manual for filter locations and schedules).",
                "Disconnect the hose and blow through it to check for blockages.",
                "Remove the brush roll and cut away any tangled hair or fibre.",
                "Check all seals and clips are firmly seated.",
            ],
            "pro_tip": "A persistent suction loss after all filters are clean may indicate a worn motor seal — seek service.",
        },
        {
            "symptom": "Robot vacuum not charging / docking",
            "steps": [
                "Clean the charging contacts on both robot and dock with a dry microfibre cloth.",
                "Ensure the dock is plugged in, the LED is on, and it is on a hard, flat floor with clear space in front.",
                "Move the dock away from direct sunlight or bright lamps (can confuse IR docking sensors).",
                "Check for firmware updates in the companion app.",
                "Manually place the robot on the dock to confirm contacts align.",
            ],
            "pro_tip": "Li-ion batteries in robot vacuums typically need replacement after 2–3 years of daily use.",
        },
    ],
    "Other": [
        {
            "symptom": "Appliance not turning on",
            "steps": [
                "Check the power supply — try a different socket or extension lead.",
                "Inspect the power cable for visible damage, kinks, or scorch marks.",
                "Check and replace the fuse in the plug with the correct rated fuse.",
                "Unplug for 60 seconds and try again (soft reset).",
                "Check for a reset button on the appliance body.",
            ],
            "pro_tip": "If the appliance trips the circuit breaker when plugged in, there is likely an internal short — do not use it and seek professional repair.",
        },
        {
            "symptom": "Unusual noise during operation",
            "steps": [
                "Ensure the appliance is on a level surface.",
                "Check for any loose parts, panels, or foreign objects inside.",
                "Tighten any visible screws or fasteners.",
                "Consult the troubleshooting section of the user manual for noise-specific advice.",
            ],
            "pro_tip": "Grinding or squealing noises often indicate a worn component — seek professional advice before continued use.",
        },
    ],
}


def generate_ics(name: str, warranty_expiry: str, purchase_date: str) -> str:
    """Return an ICS calendar string with a service-check reminder and warranty-expiry event."""
    try:
        expiry = datetime.strptime(warranty_expiry, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return ""

    today = date.today()

    def _d(d: date) -> str:
        return d.strftime("%Y%m%d")

    def _dt() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _ics_escape(text: str) -> str:
        """Escape ICS text fields per RFC 5545."""
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    safe_uid = re.sub(r"[^a-zA-Z0-9-]", "-", name.lower())
    uid_warranty = f"warranty-{safe_uid}-{_d(expiry)}@appliancemanager"
    dtstamp = _dt()

    esc_name = _ics_escape(name)
    esc_expiry = _ics_escape(warranty_expiry)
    esc_purchase = _ics_escape(purchase_date)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Appliance Manager//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    # ── Service-check reminder event (only if warranty hasn't already expired) ──
    reminder_date = expiry - timedelta(days=30)
    if expiry > today:
        reminder_date = max(reminder_date, today)
        uid_service = f"service-{safe_uid}-{_d(reminder_date)}@appliancemanager"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid_service}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{_d(reminder_date)}",
            f"DTEND;VALUE=DATE:{_d(reminder_date + timedelta(days=1))}",
            f"SUMMARY:Service Check Due - {esc_name}",
            f"DESCRIPTION:Schedule a service check for {esc_name} before the warranty expires"
            f" on {esc_expiry}. Purchase date: {esc_purchase}.",
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Service check reminder for {esc_name}",
            "END:VALARM",
            "END:VEVENT",
        ]

    # ── Warranty-expiry event ──
    lines += [
        "BEGIN:VEVENT",
        f"UID:{uid_warranty}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{_d(expiry)}",
        f"DTEND;VALUE=DATE:{_d(expiry + timedelta(days=1))}",
        f"SUMMARY:Warranty Expires - {esc_name}",
        f"DESCRIPTION:Warranty for {esc_name} expires on {esc_expiry}."
        f" Purchase date: {esc_purchase}.",
        "BEGIN:VALARM",
        "TRIGGER:-P7D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:Warranty expiry reminder for {esc_name}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


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
            # ── Summary table ─────────────────────────────────────────────────
            tbl = view_df[
                ["name", "brand", "category", "purchase_date", "warranty_expiry",
                 "_status", "days_left", "purchase_price"]
            ].copy()
            tbl["days_left"] = tbl["days_left"].apply(
                lambda x: None if x == INVALID_DATE_DAYS else x
            )
            tbl.columns = [
                "Name", "Brand", "Category", "Purchased", "Warranty Expires",
                "Status", "Days Left", "Price (£)",
            ]
            st.dataframe(
                tbl,
                column_config={
                    "Days Left":  st.column_config.NumberColumn("Days Left",  format="%.0f d"),
                    "Price (£)":  st.column_config.NumberColumn("Price (£)",  format="£%.0f"),
                },
                use_container_width=True,
                hide_index=True,
            )

            # ── Details & Actions panel ───────────────────────────────────────
            st.markdown(
                "<div class='section-header'>Appliance Details & Actions</div>",
                unsafe_allow_html=True,
            )
            appl_options = {
                str(r["id"]): f"{CATEGORY_ICONS.get(str(r['category']), '🔧')} {r['name']} ({r['brand']})"
                for _, r in view_df.iterrows()
            }
            sel_detail_id = st.selectbox(
                "Select appliance",
                options=list(appl_options.keys()),
                format_func=lambda x: appl_options[x],
                key="appl_detail_sel",
            )
            if sel_detail_id:
                row  = view_df[view_df["id"].astype(str) == sel_detail_id].iloc[0]
                days = int(row["days_left"])

                # ── Key metrics ──
                d1, d2, d3 = st.columns(3)
                d1.metric("Purchase Date",   row["purchase_date"])
                d2.metric("Warranty Expiry", row["warranty_expiry"])
                d3.metric("Days Left",       days if days != INVALID_DATE_DAYS else "—")

                d4, d5, d6 = st.columns(3)
                d4.metric("Model",          row.get("model_number")  or "—")
                d5.metric("Serial No.",     row.get("serial_number") or "—")
                d6.metric("Purchase Price", f"£{row['purchase_price']}" if row.get("purchase_price") else "—")

                if row.get("last_service_date"):
                    st.markdown(f"🔧 **Last serviced:** {row['last_service_date']}")
                if row.get("notes"):
                    st.markdown(f"📝 **Notes:** {row['notes']}")

                # ── Standard action buttons ──
                ba1, ba2, ba3 = st.columns(3)
                with ba1:
                    if st.button("✏️ Edit", key=f"edit_{row['id']}", use_container_width=True):
                        st.session_state.edit_id = str(row["id"])
                        st.rerun()
                with ba2:
                    if st.button("📋 Duplicate", key=f"dup_{row['id']}", use_container_width=True):
                        current = load_data()
                        dup = {k: row[k] for k in FIELDNAMES}
                        dup["id"]   = next_id(current)
                        dup["name"] = f"{row['name']} (copy)"
                        current = pd.concat([current, pd.DataFrame([dup])], ignore_index=True)
                        save_data(current)
                        st.success(f"Duplicated '{row['name']}'!")
                        st.rerun()
                with ba3:
                    if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                        current = load_data()
                        current = current[current["id"].astype(str) != str(row["id"])]
                        save_data(current)
                        st.success(f"'{row['name']}' deleted.")
                        st.rerun()

                # ── New feature buttons ──
                bb1, bb2 = st.columns(2)

                # 📅 Add to Calendar
                with bb1:
                    ics_data = generate_ics(
                        str(row["name"]),
                        str(row["warranty_expiry"]),
                        str(row["purchase_date"]),
                    )
                    if ics_data:
                        safe_name = re.sub(r"[^\w\-]", "_", str(row["name"])).lower()
                        st.download_button(
                            "📅 Add to Calendar",
                            data=ics_data.encode("utf-8"),
                            file_name=f"{safe_name}_reminders.ics",
                            mime="text/calendar",
                            use_container_width=True,
                            key=f"cal_{row['id']}",
                            help="Downloads a .ics file with a service-check reminder and warranty-expiry event.",
                        )
                    else:
                        st.button(
                            "📅 Add to Calendar", disabled=True,
                            use_container_width=True, key=f"cal_dis_{row['id']}",
                            help="Set a valid warranty expiry date to enable calendar export.",
                        )

                # 📖 Service Manual
                with bb2:
                    manual_url = str(row.get("manual_url", "")).strip()
                    url_safe = manual_url if re.match(r"^https?://", manual_url, re.IGNORECASE) else ""
                    if url_safe:
                        st.link_button(
                            "📖 Service Manual", url=url_safe,
                            use_container_width=True,
                        )
                    else:
                        help_txt = (
                            "URL must start with http:// or https://"
                            if manual_url else "Add a manual URL via the ✏️ Edit tab to enable this button."
                        )
                        st.button(
                            "📖 Service Manual", disabled=True,
                            use_container_width=True, key=f"manual_{row['id']}",
                            help=help_txt,
                        )

                # 🔧 Troubleshoot guide (collapsible)
                cat   = str(row.get("category", "Other"))
                guide = TROUBLESHOOT_GUIDE.get(cat, TROUBLESHOOT_GUIDE["Other"])
                with st.expander("🔧 Troubleshoot"):
                    ts_q = st.text_input(
                        "Search issue",
                        placeholder="e.g. not cooling, strange noise",
                        key=f"ts_q_{row['id']}",
                    )
                    if ts_q:
                        matched = [
                            g for g in guide
                            if ts_q.lower() in g["symptom"].lower()
                            or any(ts_q.lower() in s.lower() for s in g["steps"])
                        ]
                        if not matched:
                            st.info("No matches found — showing all issues for this category.")
                            matched = guide
                    else:
                        matched = guide

                    sel_sym = st.selectbox(
                        "Select symptom / issue",
                        [g["symptom"] for g in matched],
                        key=f"ts_sel_{row['id']}",
                    )
                    chosen = next((g for g in matched if g["symptom"] == sel_sym), None)
                    if chosen:
                        st.markdown("**Steps to resolve:**")
                        for i, step in enumerate(chosen["steps"], 1):
                            st.markdown(f"{i}. {step}")
                        if chosen.get("pro_tip"):
                            st.info(f"💡 **When to call a professional:** {chosen['pro_tip']}")


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
        a_manual  = st.text_input(
            "Service Manual URL",
            placeholder="https://… (link to PDF or product page)",
            help="Paste the URL of the appliance's service manual or product page.",
        )

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
                "manual_url":       a_manual,
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
            e_manual  = st.text_input(
                "Service Manual URL",
                value=str(row.get("manual_url", "")),
                placeholder="https://… (link to PDF or product page)",
                help="Paste the URL of the appliance's service manual or product page.",
            )

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
                current.loc[mask, "manual_url"]       = e_manual
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
        **Appliance Manager** v3.0

        Track your home appliances, warranties & service history all in one place.

        | Tab | Purpose |
        |---|---|
        | 📊 Dashboard | Charts: category breakdown, warranty status, timeline, costs |
        | 🏠 Appliances | Browse, filter & manage all appliances in a table; select one for details |
        | 🏠 → 📅 Add to Calendar | Download a .ics file with a service-check reminder and warranty-expiry event |
        | 🏠 → 📖 Service Manual | Opens the appliance's service manual URL (set via ✏️ Edit) |
        | 🏠 → 🔧 Troubleshoot | Keyword-searchable step-by-step guide for common issues by category |
        | ➕ Add | Add a new appliance with smart template hints |
        | ✏️ Edit | Full edit form including service manual URL |
        | 🔄 Bulk Ops | Multi-select delete, export & batch warranty updates |
        | ⚙️ Settings | Theme toggle and CSV downloads |
        """
    )

