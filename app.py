import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Google Sheet CSV ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"

# --- Load Data ---
def load_data():
    df = pd.read_csv(SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# --- Determine Pool Progress Status ---
def calculate_pool_progress(df):
    summary = []
    grouped = df.groupby("Pool ID")

    for pool_id, pool_df in grouped:
        total_load = int(pool_df[pool_df["Pool Up"].notna()]['Load'].max() or 0)
        in_progress = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)].shape[0] > 0
        has_started = pool_df["Start Time"].notna().any()

        if total_load > 0 and not in_progress and not has_started:
            status = "Not Started"
            color = "#ffee58"  # Yellow
        elif total_load > 0 and (in_progress or has_started):
            status = "In Progress"
            color = "#ffcc80"  # Orange
        elif total_load > 0:
            status = "Done"
            color = "#a5d6a7"  # Green
        else:
            status = "Not Started"
            color = "#eeeeee"  # Gray fallback

        summary.append({
            "pool_id": pool_id,
            "load": total_load,
            "status": status,
            "color": color
        })

    return summary

# --- Pool Progress Block ---
def generate_pool_progress_block(summary):
    def make_cell(content, color):
        return html.Div(content, style={
            "padding": "6px 10px", "margin": "2px",
            "textAlign": "center", "fontSize": "0.7rem",
            "backgroundColor": color, "borderRadius": "6px",
            "minWidth": "90px"
        })

    row1 = [make_cell("Pool Progress", "#263238"), make_cell("Date: " + datetime.now().strftime("%d/%m/%Y"), "#263238")]
    pool_names = [make_cell(item["pool_id"], item["color"]) for item in summary]
    loads = [make_cell(str(item["load"]), item["color"]) for item in summary]
    statuses = [make_cell(item["status"], item["color"]) for item in summary]

    return html.Div([
        html.Div(row1, style={"display": "flex", "justifyContent": "space-between", "marginBottom": "0.5rem", "color": "#fff"}),
        html.Div(pool_names, style={"display": "flex", "flexWrap": "wrap"}),
        html.Div(loads, style={"display": "flex", "flexWrap": "wrap"}),
        html.Div(statuses, style={"display": "flex", "flexWrap": "wrap"}),
    ], style={"marginBottom": "1.5rem"})

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

    html.Div(id="pool-progress"),
    html.Hr(className="bg-light"),
    html.Div(id="current-pool"),
    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)
], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

# --- Timestamp Tracker ---
last_updated_timestamp = datetime.now()

# --- Callbacks ---
@app.callback(
    Output("pool-progress", "children"),
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    global last_updated_timestamp
    last_updated_timestamp = datetime.now()

    df = load_data()
    summary = calculate_pool_progress(df)
    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(9)
    pool_ids = pool_groups["Pool ID"].tolist()

    from app import generate_status_block
    pool_blocks = [generate_status_block(df[df["Pool ID"] == pid]) for pid in pool_ids]
    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")

    return generate_pool_progress_block(summary), pool_blocks[0], pool_blocks[1:], updated_time

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
