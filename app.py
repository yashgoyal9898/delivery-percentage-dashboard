from io import StringIO
import pandas as pd
import streamlit as st

# ------------------------------------------------------------------#
# 1. Page config
# ------------------------------------------------------------------#
st.set_page_config(page_title="Delivery % Dashboard", layout="wide")
st.title("📊 Delivery Percentage Dashboard")

# ------------------------------------------------------------------#
# 📚 Table of Contents (Sidebar Links)
# ------------------------------------------------------------------#
st.sidebar.markdown("## 📚 Table of Contents")
st.sidebar.markdown("[1. Summary Metrics](#summary-metrics)")
st.sidebar.markdown("[2. Daily Delivery % Table](#daily-delivery-table)")
st.sidebar.markdown("[3. Weekly Delivery % Table](#weekly-delivery-table)")
st.sidebar.markdown("[4. Monthly Delivery % Table](#monthly-delivery-table)")
st.sidebar.markdown("[5. Quarterly Delivery % Table](#quarterly-delivery-table)")
st.sidebar.markdown("[6. Half-Yearly Delivery % Table](#half-yearly-delivery-table)")
st.sidebar.markdown("[7. Yearly Delivery % Table](#yearly-delivery-table)")

# ------------------------------------------------------------------#
# 2. File upload (support multiple CSVs)
# ------------------------------------------------------------------#
uploaded_files = st.sidebar.file_uploader(
    "📌 Upload one or more CSV files", type=["csv"], accept_multiple_files=True
)
if not uploaded_files:
    st.info("Upload at least one CSV to begin.")
    st.stop()

# ------------------------------------------------------------------#
# 3. Data loader & cleaner
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
        "delivery_pct": "delivery_pct",
        "open_price": "open",
        "open": "open",
        "closeprice": "close",
        "close_price": "close",
        "closing_price": "close",
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

    numeric_cols = ["traded_qty", "deliverable_qty", "delivery_pct"]
    if "open" in df.columns:
        numeric_cols.append("open")
    if "close" in df.columns:
        numeric_cols.append("close")

    for c in numeric_cols:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .replace("", pd.NA)
        )
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df.dropna(subset=["traded_qty", "deliverable_qty", "delivery_pct"], inplace=True)
    df["traded_qty"] = df["traded_qty"].astype(int)
    df["deliverable_qty"] = df["deliverable_qty"].astype(int)

    # ✅ Calculate Net Value = Deliverable Qty × Open Price
    df["net_value"] = pd.NA
    if "open" in df.columns:
        df["net_value"] = df["deliverable_qty"] * df["open"]

    return df.reset_index(drop=True)

# ------------------------------------------------------------------#
# 4. Load, clean and merge multiple files
# ------------------------------------------------------------------#
dfs = []
for up in uploaded_files:
    part = load_and_clean(up.read().decode("utf-8", errors="ignore"))
    dfs.append(part)

df = (
    pd.concat(dfs, ignore_index=True)
    .drop_duplicates(subset=["symbol", "date"])
    .sort_values("date")
    .reset_index(drop=True)
)

# ------------------------------------------------------------------#
# 5. Sidebar filters
# ------------------------------------------------------------------#
spike_thr = st.sidebar.slider("🚨 Spike threshold (%)", 0.0, 100.0, 75.0, step=0.5)
net_value_thr = st.sidebar.slider("💰 Net Value Spike (₹ Cr)", 0.0, 50.0, 3.0, step=0.5)

# ------------------------------------------------------------------#
# 6. Summary metrics
# ------------------------------------------------------------------#
st.markdown('<a name="summary-metrics"></a>', unsafe_allow_html=True)
st.subheader("📌 Summary Metrics")
col1, col2, col3, col4 = st.columns(4)

avg_delivery_overall = df['delivery_pct'].mean()
max_delivery = df['delivery_pct'].max()
total_days = df['date'].nunique()

col1.metric("Average Delivery % (Overall)", f"{avg_delivery_overall:.2f}")
col2.metric("Max Delivery %", f"{max_delivery:.2f}")
col3.metric("Total Days", total_days)
col4.metric("Total Symbols", df['symbol'].nunique())

# ------------------------------------------------------------------#
# 7. Spike alerts
# ------------------------------------------------------------------#
spikes = df[df["delivery_pct"] >= spike_thr]
if not spikes.empty:
    st.warning(f"🚨 {len(spikes)} spike(s) ≥ {spike_thr}%")
    st.dataframe(spikes[["date", "symbol", "delivery_pct"]])

# ------------------------------------------------------------------#
# 8. Daily Delivery % Table
# ------------------------------------------------------------------#
st.markdown('<a name="daily-delivery-table"></a>', unsafe_allow_html=True)
st.subheader("📆 Daily Delivery % (Quantities in Millions, Net Value in ₹ Crores)")

df = df.sort_values(["symbol", "date"])
df["traded_qty_chg_%"] = df.groupby("symbol")["traded_qty"].pct_change() * 100
df["deliverable_qty_chg_%"] = df.groupby("symbol")["deliverable_qty"].pct_change() * 100

daily_disp = df.copy()
daily_disp["traded_qty_mn"] = (daily_disp["traded_qty"] / 1e6).round(2)
daily_disp["deliverable_qty_mn"] = (daily_disp["deliverable_qty"] / 1e6).round(2)
daily_disp["net_value_crore"] = (daily_disp["net_value"] / 1e7).round(2)
daily_disp["traded_qty_chg_%"] = daily_disp["traded_qty_chg_%"].round(2)
daily_disp["deliverable_qty_chg_%"] = daily_disp["deliverable_qty_chg_%"].round(2)

daily_columns = [
    "date",
    "symbol",
    "traded_qty_mn",
    "deliverable_qty_mn",
    "delivery_pct",
    "net_value_crore",
    "traded_qty_chg_%",
    "deliverable_qty_chg_%"
]

def highlight_net_value(val):
    if pd.notna(val) and val > net_value_thr:
        return "background-color: #ffe6e6; font-weight: bold"
    return ""

styled_df = daily_disp[daily_columns].style.map(highlight_net_value, subset=["net_value_crore"])
st.dataframe(styled_df, use_container_width=True)

# ------------------------------------------------------------------#
# 9. Aggregation function
# ------------------------------------------------------------------#
def aggregate_and_display(df, period_col, display_name):
    grouped = df.groupby([period_col, "symbol"], as_index=False)[["traded_qty", "deliverable_qty", "net_value"]].sum()
    grouped["delivery_pct"] = 100 * grouped["deliverable_qty"] / grouped["traded_qty"]

    disp = grouped.copy()
    disp["traded_qty_million"] = (disp["traded_qty"] / 1e6).round(2)
    disp["deliverable_qty_million"] = (disp["deliverable_qty"] / 1e6).round(2)
    disp["net_value_crore"] = (disp["net_value"] / 1e7).round(2)

    columns = [period_col, "symbol", "traded_qty_million", "deliverable_qty_million", "delivery_pct", "net_value_crore"]
    st.markdown(f'<a name="{display_name}-delivery-table"></a>', unsafe_allow_html=True)
    st.subheader(f"📊 {display_name} Delivery % (Quantities in Millions, Net Value in ₹ Crores)")
    st.dataframe(disp[columns].style.map(highlight_net_value, subset=["net_value_crore"]), use_container_width=True)

# ------------------------------------------------------------------#
# 10. Weekly, Monthly, Quarterly, Half-Yearly, Yearly Aggregations
# ------------------------------------------------------------------#
df["week"] = df["date"].dt.to_period("W").apply(lambda r: r.start_time)
df["month"] = df["date"].dt.to_period("M").apply(lambda r: r.start_time)
df["quarter"] = df["date"].dt.to_period("Q").apply(lambda r: r.start_time)
df["half_year"] = df["date"].apply(lambda d: pd.Timestamp(f"{d.year}-01-01") if d.month <= 6 else pd.Timestamp(f"{d.year}-07-01"))
df["year"] = df["date"].dt.to_period("Y").apply(lambda r: r.start_time)

aggregate_and_display(df, "week", "Weekly")
aggregate_and_display(df, "month", "Monthly")
aggregate_and_display(df, "quarter", "Quarterly")
aggregate_and_display(df, "half_year", "Half-Yearly")
aggregate_and_display(df, "year", "Yearly")
