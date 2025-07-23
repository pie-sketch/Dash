# --- Imports ---
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Constants ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
GRACE_MINUTES = 5

# --- Load Data ---
def load_data():
    df = pd.read_csv(SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# --- Status Assignment ---
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

# --- Main Visual Block ---
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
    total_load = tl_row["Load"].max() if not tl_row.empty else 0
    manpower = len(active_rows)
    target_load = total_load / manpower if manpower else 1
    expected_time = pool_up_time + timedelta(hours=1, minutes=5) if pool_up_time else None

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_display = f"{int(load)}"

        # Duration calculation
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            time_taken = row["End Time"] - row["Start Time"]
            duration_str = str(time_taken).split(".")[0]  # HH:MM:SS
        else:
            time_taken = None
            duration_str = "-"

        # Late logic with grace
        overdue = False
        late_reason = ""
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]) and total_load:
            actual_duration = row["End Time"] - row["Start Time"]
            expected_minutes = (row["Load"] / 2.5) + GRACE_MINUTES
            if actual_duration.total_seconds() > expected_minutes * 60:
                overdue = True
                late_reason = f"Late: took {int(actual_duration.total_seconds() // 60)}m vs expected {int(expected_minutes)}m"

        box_class = "card-content glow-card"
        progress_wrapper_class = ""
        if status == "In Progress":
            progress_wrapper_class = "animated-progress"
        if overdue:
            progress_wrapper_class = "animated-late"
            box_class += " overdue-box"

        visual_rows.append(
            html.Div([
                html.Div(name, className="staff-name"),
                html.Div(
                    dbc.Progress(
                        value=load_percent,
                        color=color,
                        striped=(status == "In Progress"),
                        style={"height": "16px", "width": "100%"},
                        title=late_reason if overdue else None
                    ),
                    className=progress_wrapper_class
                ),
                html.Div(load_display, className="load-display"),
                html.Div(duration_str, className="duration-display"),
                html.Div(late_reason, className="late-reason") if overdue else None
            ], className=box_class)
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Div(tl_name, className="tl-name"),
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
                    html.Span(f"Expected Completion: {expected_time.strftime('%H:%M:%S') if expected_time else '-'}")
                ], className="pool-info-box")
            ], className="pool-header")
        ]),
        dbc.CardBody(
            html.Div(visual_rows, className="seat-grid")
        )
    ], className="mb-4")

# --- App Setup ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

app.layout = dbc.Container([
    dcc.Interval(id="auto-refresh", interval=180000, n_intervals=0),
    html.Div(id="current-pool")
], fluid=True)

@app.callback(
    Output("current-pool", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    df = load_data()
    latest_pool_id = df[df["Pool Up"].notna()].sort_values("Pool Up", ascending=False).iloc[0]["Pool ID"]
    pool_df = df[df["Pool ID"] == latest_pool_id]
    return generate_status_block(pool_df)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)

