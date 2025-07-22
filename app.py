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

# --- Get Status for Staff ---
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

# --- Get Pool Progress Block ---
def generate_pool_progress(df):
    pool_blocks = []

    grouped = df[df["Pool Up"].notna()].groupby("Pool ID")
    for pool_id, group in grouped:
        tl = group[group["Pool Up"].notna()].iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_label = f"{pool_name} - {tab}"
        total_load = int(tl["Load"])
        pool_staff = df[(df["Pool ID"] == pool_id) & (df["Pool Up"].isna()) & (df["Load"] > 0)]

        if pool_staff.empty:
            status = "Not Started"
            color = "#FFD700"  # Yellow
        elif pool_staff["End Time"].notna().all():
            status = "Complete"
            color = "#2ECC71"  # Green
        else:
            status = "In Progress"
            color = "#FFA500"  # Orange

        card = html.Div([
            html.Div(pool_label, style={"fontSize": "0.65rem", "fontWeight": "bold", "textAlign": "center"}),
            html.Div(f"Total Load: {total_load}", style={"fontSize": "0.6rem", "textAlign": "center"}),
            html.Div(status, style={"fontSize": "0.6rem", "textAlign": "center", "color": "#000", "backgroundColor": color, "borderRadius": "4px", "marginTop": "2px"})
        ], style={
            "width": "100px", "padding": "5px", "margin": "4px",
            "backgroundColor": "#111", "borderRadius": "6px", "boxShadow": "0 0 6px #333"
        })
        pool_blocks.append(card)

    return html.Div([
        html.Div("POOL PROGRESS", style={"fontSize": "0.9rem", "fontWeight": "bold", "textAlign": "center", "marginBottom": "5px"}),
        html.Div(pool_blocks, style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center"})
    ], style={"marginBottom": "15px"})

# --- Main Pool Block ---
def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up_time = tl["Pool Up"]
        pool_up = pool_up_time.strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
        total_count = int(tl["Load"])
    else:
        pool_name, tab, pool_up, tl_name = "-", "-", "-", "-"
        total_count = 0
        pool_up_time = None

    active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)].copy()
    manpower = len(active_rows)
    expected_time = pool_up_time + timedelta(hours=1) if pool_up_time else None

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)

        load_percent = min(100, int((load / 150) * 100)) if load else 0
        load_display = f"{int(load)}"

        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            time_taken = row["End Time"] - row["Start Time"]
            total_seconds = int(time_taken.total_seconds())
            h, r = divmod(total_seconds % 86400, 3600)
            m, s = divmod(r, 60)
            duration_str = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            time_taken = None
            duration_str = "-"

        # ✅ Late logic based on personal load
        overdue = False
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]) and load:
            actual_duration = row["End Time"] - row["Start Time"]
            expected_minutes = (load / 150) * 60
            overdue = actual_duration.total_seconds() > (expected_minutes * 60)

        box_class = "card-content glow-card"
        progress_class = "animated-progress" if status == "In Progress" else ""
        if overdue:
            progress_class = "animated-late"
            box_class += " overdue-box"

        visual_rows.append(
            html.Div([
                html.Div(name, style={"fontWeight": "bold", "fontSize": "0.8rem", "textAlign": "center"}),
                html.Div(
                    dbc.Progress(value=load_percent, color=color, striped=(status == "In Progress"),
                                 style={"height": "16px", "width": "100%"}),
                    className=progress_class
                ),
                html.Div(load_display, style={"fontSize": "0.75rem", "textAlign": "center", "marginTop": "4px"}),
                html.Div(duration_str, style={"fontSize": "0.7rem", "textAlign": "center", "marginTop": "2px", "color": "#aaa"})
            ], className=box_class)
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Div(f"{tl_name}", className="tl-name"),
                html.Div(f"{pool_name} - {tab}", className="pool-title"),
                html.Div(f"⬆ Pool Up: {pool_up}", className="pool-time"),
                html.Div([
                    html.Span("🟢 Complete", className="complete"),
                    html.Span("  🔶 In Progress", className="in-progress"),
                    html.Span("  🔴 Late", className="late")
                ], className="pool-status"),
                html.Div([
                    html.Span(f"Total Count: {total_count}", style={"marginRight": "12px"}),
                    html.Span(f"Manpower: {manpower}", style={"marginRight": "12px"}),
                    html.Span(f"Expected Pool Done: {expected_time.strftime('%H:%M:%S') if expected_time else '-'}")
                ], style={"fontSize": "0.8rem", "color": "#ccc", "marginTop": "6px"})
            ], className="pool-header", style={"textAlign": "center"})
        ]),
        dbc.CardBody(html.Div(visual_rows, className="seat-grid", style={"padding": "10px"}))
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- Dash Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"fontSize": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-timer", className="text-end countdown-glow", style={"fontSize": "0.75rem"}), width=6)
    ], align="center"),

    dcc.Interval(id="auto-refresh", interval=15000, n_intervals=0),
    dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0),

    html.Div(id="pool-progress"),
    html.Div(id="current-pool"),
    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)
], fluid=True, style={"backgroundColor": "#0d1b2a", "padding": "1rem"})

last_updated_timestamp = datetime.now()

# --- Callbacks ---
@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Output("pool-progress", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    global last_updated_timestamp
    last_updated_timestamp = datetime.now()
    df = load_data()

    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(9)
    pool_ids = pool_groups["Pool ID"].tolist()

    pool_blocks = [generate_status_block(df[df["Pool ID"] == pid]) for pid in pool_ids]
    progress_bar = generate_pool_progress(df)
    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return pool_blocks[0], pool_blocks[1:], updated_time, progress_bar

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

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
