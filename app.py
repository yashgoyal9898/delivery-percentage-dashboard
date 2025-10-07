from io import StringIO
import pandas as pd
import streamlit as st

# ------------------------------------------------------------------#
# 1. Page config
# ------------------------------------------------------------------#
st.set_page_config(page_title="Delivery % Dashboard", layout="wide")
st.title("📊 Delivery Percentage Dashboard")

# ------------------------------------------------------------------#
# 2. Sidebar: Table of Contents
# ------------------------------------------------------------------#
st.sidebar.markdown("## 📚 Table of Contents")
sections = [
    ("summary-metrics", "Summary Metrics"),
    ("daily-delivery-table", "Daily Delivery % Table"),
    ("weekly-delivery-table", "Weekly Delivery % Table"),
    ("monthly-delivery-table", "Monthly Delivery % Table"),
    ("quarterly-delivery-table", "Quarterly Delivery % Table"),
    ("half-yearly-delivery-table", "Half-Yearly Delivery % Table"),
    ("yearly-delivery-table", "Yearly Delivery % Table"),
]
for anchor, name in sections:
    st.sidebar.markdown(f"[{name}](#{anchor})")

# ------------------------------------------------------------------#
# 3. File upload
# ------------------------------------------------------------------#
uploaded_files = st.sidebar.file_uploader(
    "📌 Upload one or more CSV files", type=["csv"], accept_multiple_files=True
)
if not uploaded_files:
    st.info("Upload at least one CSV to begin.")
    st.stop()

# ------------------------------------------------------------------#
# 4. Data loader & cleaner
# ------------------------------------------------------------------#
@st.cache_data(show_spinner=False)
def load_and_clean(raw_csv: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(raw_csv))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    COL_MAP = {
        "symbol": "symbol",
        "date": "date",
        "qty_traded": "traded_qty",
        "total_traded_quantity": "traded_qty",
        "traded_qty": "traded_qty",
        "deliverable_qty": "deliverable_qty",
        "delivered_qty": "deliverable_qty",
        "delivery_percentage": "delivery_pct",
        "delivery_percent": "delivery_pct",
        "%_dly_qt_to_traded_qty": "delivery_pct",
        "open_price": "open",
        "close_price": "close",
        "close": "close",
    }
    df.rename(columns=lambda c: COL_MAP.get(c, c), inplace=True)

    REQUIRED = ["symbol", "date", "traded_qty", "deliverable_qty", "delivery_pct"]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}")

    df.replace(["-", "NA", "N/A", "na", ""], pd.NA, inplace=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    for col in ["traded_qty", "deliverable_qty", "delivery_pct", "open", "close"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
                .replace("", pd.NA)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.dropna(subset=["traded_qty", "deliverable_qty", "delivery_pct"], inplace=True)
    df["traded_qty"] = df["traded_qty"].astype(int)
    df["deliverable_qty"] = df["deliverable_qty"].astype(int)

    df["net_value"] = df["deliverable_qty"] * df.get("open", 1)
    return df.reset_index(drop=True)

# ------------------------------------------------------------------#
# 5. Merge all uploaded files
# ------------------------------------------------------------------#
df = pd.concat(
    [load_and_clean(up.read().decode("utf-8", errors="ignore")) for up in uploaded_files],
    ignore_index=True,
).drop_duplicates(subset=["symbol", "date"]).sort_values("date")

# ------------------------------------------------------------------#
# 6. Sidebar filters
# ------------------------------------------------------------------#
spike_thr = st.sidebar.slider("🚨 Spike threshold (%)", 0.0, 100.0, 75.0, step=0.5)
net_value_thr = st.sidebar.slider("💰 Net Value Spike (₹ Cr)", 0.0, 50.0, 3.0, step=0.5)

# ------------------------------------------------------------------#
# 7. Summary metrics
# ------------------------------------------------------------------#
st.markdown('<a name="summary-metrics"></a>', unsafe_allow_html=True)
st.subheader("📌 Summary Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Average Delivery % (Overall)", f"{df['delivery_pct'].mean():.2f}")
col2.metric("Max Delivery %", f"{df['delivery_pct'].max():.2f}")
col3.metric("Total Days", int(df["date"].nunique()))
col4.metric("Total Symbols", df["symbol"].nunique())

# ------------------------------------------------------------------#
# 8. Spike alerts
# ------------------------------------------------------------------#
spikes = df[df["delivery_pct"] >= spike_thr]
if not spikes.empty:
    st.warning(f"🚨 {len(spikes)} spike(s) ≥ {spike_thr}%")
    st.dataframe(spikes[["date", "symbol", "delivery_pct"]])

# ------------------------------------------------------------------#
# 9. Helper: Highlight and Aggregate
# ------------------------------------------------------------------#
def highlight_net_value(val):
    return "background-color: #ffe6e6; font-weight: bold" if pd.notna(val) and val > net_value_thr else ""

def aggregate(df, freq, label):
    """Generic aggregator for daily/weekly/monthly/quarterly/half-yearly/yearly."""
    temp = df.copy()
    if freq == "D":  # daily
        temp["period"] = temp["date"]
    elif freq == "2H":  # half-year
        temp["period"] = temp["date"].apply(lambda d: pd.Timestamp(f"{d.year}-01-01") if d.month <= 6 else pd.Timestamp(f"{d.year}-07-01"))
    else:  # other pandas periods
        temp["period"] = temp["date"].dt.to_period(freq).apply(lambda r: r.start_time)

    agg = temp.groupby(["period", "symbol"], as_index=False)[["traded_qty", "deliverable_qty", "net_value"]].sum()
    agg["delivery_pct"] = 100 * agg["deliverable_qty"] / agg["traded_qty"]

    if freq in ["D", "W", "M"]:
        agg = agg.sort_values(["symbol", "period"])
        agg["traded_qty_chg_%"] = agg.groupby("symbol")["traded_qty"].pct_change() * 100
        agg["deliverable_qty_chg_%"] = agg.groupby("symbol")["deliverable_qty"].pct_change() * 100
    else:
        agg["traded_qty_chg_%"] = pd.NA
        agg["deliverable_qty_chg_%"] = pd.NA

    agg["traded_qty_mn"] = (agg["traded_qty"] / 1e6).round(2)
    agg["deliverable_qty_mn"] = (agg["deliverable_qty"] / 1e6).round(2)
    agg["net_value_crore"] = (agg["net_value"] / 1e7).round(2)

    cols = ["period", "symbol", "traded_qty_mn", "deliverable_qty_mn", "delivery_pct",
            "net_value_crore", "traded_qty_chg_%", "deliverable_qty_chg_%"]
    disp = agg[cols]

    st.markdown(f'<a name="{label.lower()}-delivery-table"></a>', unsafe_allow_html=True)
    st.subheader(f"📅 {label} Delivery % (Quantities in Millions, Net Value in ₹ Crores)")
    st.dataframe(disp.style.applymap(highlight_net_value, subset=["net_value_crore"]), use_container_width=True)

# ------------------------------------------------------------------#
# 10. Show all tables
# ------------------------------------------------------------------#
aggregate(df, "D", "Daily")
aggregate(df, "W", "Weekly")
aggregate(df, "M", "Monthly")
aggregate(df, "Q", "Quarterly")
aggregate(df, "2H", "Half-Yearly")
aggregate(df, "Y", "Yearly")
