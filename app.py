import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Constants ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
REFRESH_INTERVAL_MS = 180000  # 3 minutes

# --- Load Data ---
def load_data():
    df = pd.read_csv(SHEET_URL)
    for col in ["Start Time", "End Time", "Pool Up"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# --- Helper: Determine Status ---
def get_status(row, total_pool_load, target_load):
    if not pd.isna(row["Pool Up"]):
        return "TL", "secondary"
    if row["Load"] == 0:
        return "Helper", "secondary"
    if abs(row["Load"] - target_load) <= 3:
        return "Complete", "success"
    return "In Progress", "warning"

# --- Helper: Format Duration ---
def format_duration(start, end):
    if pd.notna(start) and pd.notna(end):
        seconds = int((end - start).total_seconds())
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}", seconds
    return "-", None

# --- Main Visual Block ---
def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if tl_row.empty:
        return html.Div("No Pool TL Found")

    tl = tl_row.iloc[0]
    pool_name, tab, pool_up_time, tl_name = tl["Pool Name"], tl["Tab"], tl["Pool Up"], tl["Name"]
    pool_up_str = pool_up_time.strftime("%d/%m/%Y %H:%M:%S")
    total_count = int(tl["Load"])
    expected_time = pool_up_time + timedelta(hours=1, minutes=5)

    active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)]
    manpower = len(active_rows)
    target_load = total_count / manpower if manpower else 1

    visual_rows = []
    for _, row in active_rows.iterrows():
        name, load = row["Name"], row["Load"]
        status, color = get_status(row, total_count, target_load)

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_display = str(int(load))

        duration_str, duration_secs = format_duration(row["Start Time"], row["End Time"])

        overdue = False
        if duration_secs and total_count:
            expected_secs = (manpower / total_count) * 150 * 60
            overdue = duration_secs > expected_secs

        box_class = "card-content glow-card"
        progress_class = "animated-late" if overdue else "animated-progress" if status == "In Progress" else ""

        if overdue:
            box_class += " overdue-box"

        visual_rows.append(
            html.Div([
                html.Div(name, style={"font-weight": "bold", "font-size": "0.8rem", "text-align": "center"}),
                html.Div(
                    dbc.Progress(value=load_percent, color=color, striped=(status == "In Progress"), style={"height": "16px"}),
                    className=progress_class
                ),
                html.Div(load_display, style={"font-size": "0.75rem", "text-align": "center", "marginTop": "4px"}),
                html.Div(duration_str, style={"font-size": "0.7rem", "text-align": "center", "marginTop": "2px", "color": "#aaa"})
            ], className=box_class)
        )

    return dbc.Card([
        dbc.CardHeader(html.Div([
            html.Div(tl_name, className="tl-name"),
            html.Div(f"{pool_name} - {tab}", className="pool-title"),
            html.Div(f"⬆ Pool Up: {pool_up_str}", className="pool-time"),
            html.Div([
                html.Span("🟢 Complete", className="complete"),
                html.Span("  🔶 In Progress", className="in-progress"),
                html.Span("  🔴 Late", className="late")
            ], className="pool-status"),
            html.Div([
                html.Span(f"Total Count: {total_count}", style={"marginRight": "12px"}),
                html.Span(f"Manpower: {manpower}", style={"marginRight": "12px"}),
                html.Span(f"Expected Completion: {expected_time.strftime('%H:%M:%S')}")
            ], style={"font-size": "0.8rem", "color": "#ccc", "marginTop": "6px"})
        ], className="pool-header", style={"text-align": "center"})),
        dbc.CardBody(html.Div(visual_rows, className="seat-grid", style={"padding": "10px"}))
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"font-size": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-timer", className="text-end countdown-glow", style={"font-size": "0.75rem"}), width=6)
    ], align="center"),
    dcc.Interval(id="auto-refresh", interval=REFRESH_INTERVAL_MS, n_intervals=0),
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
    pool_ids = (
        df[df["Pool Up"].notna()]
        .groupby("Pool ID")["Pool Up"].max()
        .reset_index()
        .sort_values("Pool Up", ascending=False)["Pool ID"]
        .tolist()
    )

    pool_blocks = [generate_status_block(df[df["Pool ID"] == pid]) for pid in pool_ids[:9]]
    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return pool_blocks[0], pool_blocks[1:], updated_time

@app.callback(
    Output("countdown-timer", "children"),
    Input("countdown-interval", "n_intervals")
)
def update_countdown(n):
    elapsed = (datetime.now() - last_updated_timestamp).seconds
    remaining = max(0, REFRESH_INTERVAL_MS // 1000 - elapsed)
    return f"⏳ Refreshing in: {remaining:02d}s"

@app.callback(
    Output("previous-pools", "is_open"),
    Input("toggle-collapse", "n_clicks"),
    State("previous-pools", "is_open"),
    prevent_initial_call=True
)
def toggle_previous(n, is_open):
    return not is_open

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
