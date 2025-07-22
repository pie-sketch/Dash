import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Google Sheet CSV ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
POOL_MAP_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=1831523651"  # Pool Sequences tab

# --- Load Data ---
def load_data():
    df = pd.read_csv(SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]

    pool_map = pd.read_csv(POOL_MAP_URL)
    pool_map["Pool ID"] = pool_map["Pool Name"] + " - " + pool_map["Tab"]
    df = df.merge(pool_map[["Pool ID", "Pools"]], on="Pool ID", how="left")
    return df

# --- Status ---
def get_status(row, pool_df):
    if not pd.isna(row["Pool Up"]):
        return "TL", "secondary"
    if row["Load"] == 0:
        return "Helper", "secondary"

    tl_row = pool_df[pool_df["Pool Up"].notna()]
    total_pool_load = tl_row["Load"].max() if not tl_row.empty else 0
    active_staff = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)]
    num_staff = len(active_staff)
    target_load = total_pool_load / num_staff if num_staff else 1

    if abs(row["Load"] - target_load) <= 3:
        return "Complete", "success"
    return "In Progress", "warning"

# --- Pool Progress ---
def generate_pool_progress_row(df, recent_pool_ids):
    rows = []
    for pid in recent_pool_ids:
        pool_df = df[df["Pool ID"] == pid]
        tl_row = pool_df[pool_df["Pool Up"].notna()]
        if tl_row.empty:
            continue

        tl = tl_row.iloc[0]
        pool_short = tl.get("Pools", f"{tl['Pool Name']} - {tl['Tab']}")
        pool_time = tl["Pool Up"].strftime("%H:%M")

        active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)]
        if active_rows.empty:
            status = "Not Started"
            color = "#cccc00"
        elif all(get_status(row, pool_df)[0] == "Complete" for _, row in active_rows.iterrows()):
            status = "Completed"
            color = "#00cc66"
        else:
            status = "In Progress"
            color = "#ffaa00"

        block = html.Div([
            html.Div(pool_short, style={"fontWeight": "bold", "fontSize": "0.75rem"}),
            html.Div(pool_time, style={"fontSize": "0.7rem", "color": "#999"}),
            html.Div(status, style={"color": color, "fontSize": "0.8rem", "fontWeight": "bold"})
        ], className="mini-pool-box", style={
            "backgroundColor": "#1a1a1a",
            "borderRadius": "8px",
            "padding": "6px 12px",
            "marginRight": "6px",
            "textAlign": "center",
            "minWidth": "100px"
        })
        rows.append(block)

    return html.Div([
        html.Div("POOL PROGRESS", style={"color": "#ccc", "fontWeight": "bold", "marginBottom": "4px", "fontSize": "0.85rem"}),
        html.Div(rows, style={"display": "flex", "overflowX": "auto"})
    ], style={"marginBottom": "12px"})

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"font-size": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-timer", className="text-end countdown-glow", style={"font-size": "0.75rem"}), width=6)
    ], align="center"),

    dcc.Interval(id="auto-refresh", interval=15000, n_intervals=0),
    dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0),

    html.Div(id="current-pool"),
    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)
], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

# --- Tracker ---
last_updated_timestamp = datetime.now()

# --- Callbacks ---
@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    global last_updated_timestamp
    last_updated_timestamp = datetime.now()

    df = load_data()
    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(9)
    pool_ids = pool_groups["Pool ID"].tolist()

    progress_row = generate_pool_progress_row(df, pool_ids)
    pool_blocks = [html.Div(f"Dummy block for {pid}") for pid in pool_ids]  # Replace with real blocks

    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return [progress_row, pool_blocks[0]], pool_blocks[1:], updated_time

@app.callback(
    Output("countdown-timer", "children"),
    Input("countdown-interval", "n_intervals")
)
def update_countdown(n):
    global last_updated_timestamp
    elapsed = (datetime.now() - last_updated_timestamp).seconds
    remaining = max(0, 15 - elapsed)
    return f"\u23F3 Refreshing in: {remaining:02d}s"

@app.callback(
    Output("previous-pools", "is_open"),
    Input("toggle-collapse", "n_clicks"),
    State("previous-pools", "is_open"),
    prevent_initial_call=True
)
def toggle_previous(n, is_open):
    return not is_open

# --- Run App ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
