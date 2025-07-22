# app.py
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
    df["Duration"] = (df["End Time"] - df["Start Time"]).dt.total_seconds() / 60
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# --- Get Status ---
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

def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up_time = tl["Pool Up"]
        pool_up = pool_up_time.strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
        total_count = int(tl["Load"]) if pd.notna(tl["Load"]) else 0
    else:
        pool_name, tab, pool_up, tl_name = "-", "-", "-", "-"
        total_count = 0

    active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)].copy()
    total_load = tl_row["Load"].max() if not tl_row.empty else 0
    num_staff = len(active_rows)
    target_load = total_load / num_staff if num_staff else 1

    expected_time = pool_up_time + timedelta(hours=1, minutes=5) if not pd.isna(pool_up_time) else "-"

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_display = f"{int(load)}"

        completion_time = row["End Time"] - row["Start Time"]
        completion_time_str = str(timedelta(seconds=int(completion_time.total_seconds()))) if pd.notna(completion_time) else "-"

        visual_rows.append(
            html.Div([
                html.Div(name, style={"font-weight": "bold", "font-size": "0.8rem", "text-align": "center"}),
                dbc.Progress(value=load_percent, color=color, striped=(status == "In Progress"), style={"height": "16px", "width": "100%"}),
                html.Div(load_display, style={"font-size": "0.75rem", "text-align": "center", "marginTop": "4px"}),
                html.Div(completion_time_str, style={"font-size": "0.7rem", "text-align": "center", "marginTop": "2px", "color": "#aaa"})
            ], className="card-content glow-card")
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Div([
                    html.Div(f"{tl_name}", className="pool-title"),
                    html.Div(f"{pool_name} - {tab}", className="pool-title"),
                    html.Div(f"⬆ Pool Up: {pool_up}", className="pool-time"),
                    html.Div("🟢 Complete    🔶 In Progress", className="pool-status")
                ], className="pool-header"),

                html.Div([
                    html.Div([f"Total Count: {total_count}"], className="top-info"),
                    html.Div([f"Individual Count: {num_staff}"], className="top-info"),
                    html.Div([f"Expected Completion: {expected_time.strftime('%H:%M:%S') if expected_time != '-' else '-'}"], className="top-info")
                ], className="header-side-info")
            ], style={"position": "relative"})
        ]),
        dbc.CardBody(
            html.Div(visual_rows, className="seat-grid", style={"padding": "10px"})
        )
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([html.Div(id="last-update", className="text-start text-secondary", style={"font-size": "0.75rem"})], width=6),
        dbc.Col([html.Div(id="countdown-timer", className="text-end countdown-glow", style={"font-size": "0.75rem"})], width=6)
    ], align="center"),

    dcc.Interval(id="auto-refresh", interval=15000, n_intervals=0),
    dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0),

    html.Div(id="current-pool"),
    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)

], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

last_updated_timestamp = datetime.now()

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

    pool_blocks = []
    for pid in pool_ids:
        sub_df = df[df["Pool ID"] == pid]
        pool_blocks.append(generate_status_block(sub_df))

    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return pool_blocks[0], pool_blocks[1:], updated_time

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
