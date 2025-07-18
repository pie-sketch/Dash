import dash
import os
from dash import html, dcc, Input, Output
import pandas as pd
import plotly.express as px

# --- Google Sheet CSV URL ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"

# --- Dash App ---
app = dash.Dash(__name__)
app.title = "Live Pool Dashboard"

app.layout = html.Div(style={"backgroundColor": "#111", "color": "#FFF", "padding": "20px"}, children=[
    html.H1("🕒 Live Pool Overview", style={"textAlign": "center"}),

    dcc.Dropdown(id="pool-selector", placeholder="Select previous pool...", style={"width": "300px", "marginBottom": "20px"}),

    dcc.Graph(id="pool-chart"),

    dcc.Interval(id="auto-refresh", interval=60 * 1000, n_intervals=0),
    html.Div(id="last-update", style={"textAlign": "right", "marginTop": "10px", "fontSize": "14px"})
])

def load_data():
    df = pd.read_csv(SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    return df

@app.callback(
    [Output("pool-selector", "options"), Output("pool-selector", "value")],
    Input("auto-refresh", "n_intervals")
)
def update_pool_list(n):
    df = load_data()
    pool_up_times = df[df["Pool Up"].notna()].groupby("Pool Name")["Pool Up"].min().sort_values(ascending=False)
    current_pool = pool_up_times.index[0] if not pool_up_times.empty else None
    previous_pools = pool_up_times.index[1:3].tolist()

    options = [{"label": pool, "value": pool} for pool in previous_pools]
    return options, current_pool

@app.callback(
    [Output("pool-chart", "figure"), Output("last-update", "children")],
    [Input("pool-selector", "value"), Input("auto-refresh", "n_intervals")]
)
def update_dashboard(pool_name, n):
    df = load_data()
    if not pool_name:
        return dash.no_update, ""

    pool_df = df[df["Pool Name"] == pool_name].copy()
    pool_up_time = pool_df["Pool Up"].dropna().min()
    initiators = pool_df[pool_df["Pool Up"].notna()]
    total_load = initiators["Load"].sum()

    helpers = pool_df[pool_df["Load"] < 5]["Name"].tolist()
    manpower_df = pool_df[
        (pool_df["Pool Up"].isna()) &
        (~pool_df["Name"].isin(helpers)) &
        (pool_df["Load"] >= 5)
    ].copy()

    manpower_count = len(manpower_df)
    expected_load = round(total_load / manpower_count, 2) if manpower_count else 0
    load_range = (round(expected_load) - 2, round(expected_load) + 2)

    def get_status(row):
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            duration = (row["End Time"] - row["Start Time"]).total_seconds() / 60
            if duration >= 15 and row["Load"] < 45:
                return "delay"
            if load_range[0] <= row["Load"] <= load_range[1]:
                return "complete"
            return "in progress"
        return "in progress"

    def format_duration(start, end):
        if pd.isna(start) or pd.isna(end): return ""
        delta = end - start
        return f"{int(delta.total_seconds() // 60)}:{str(int(delta.total_seconds() % 60)).zfill(2)}"

    manpower_df["Duration"] = manpower_df.apply(lambda r: format_duration(r["Start Time"], r["End Time"]), axis=1)
    manpower_df["Status"] = manpower_df.apply(get_status, axis=1)

    fig = px.bar(
        manpower_df,
        x="Name", y="Load", color="Status",
        color_discrete_map={
            "complete": "#2ecc71",
            "in progress": "#a8e6cf",
            "delay": "#f39c12"
        },
        text="Load",
        title=f"Load Distribution for {pool_name}"
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        plot_bgcolor="#222", paper_bgcolor="#111",
        font_color="white", title_font_color="white",
        xaxis_title="", yaxis_title="Load",
        height=500,
        bargap=0.4,
        margin=dict(t=60, b=80, l=40, r=40),
        hovermode="closest"
    )

    last_time = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M:%S")
    return fig, f"Last updated: {last_time}"

# --- Run app ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=True)
