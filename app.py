import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Google Sheets CSV ---
MAIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
SEQUENCE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=973487960"

# --- Load Sequences ---
def load_pool_sequences():
    df = pd.read_csv(SEQUENCE_SHEET_URL)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    df["Short"] = df["Pools id"]
    return df

# --- Load Main Sheet ---
def load_main_data():
    df = pd.read_csv(MAIN_SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# --- Determine Pool Status ---
def get_pool_status(pool_id, main_df):
    pool_df = main_df[main_df["Pool ID"] == pool_id]
    if pool_df.empty:
        return "not-started", 0
    if pool_df["Pool Up"].notna().any():
        completed = pool_df["End Time"].notna().sum()
        active = pool_df["Start Time"].notna().sum()
        return ("complete" if completed == active else "in-progress"), pool_df["Load"].sum()
    return "not-started", pool_df["Load"].sum()

# --- Generate Status Block ---
def generate_status_block(pool_df, short_label):
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
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            time_taken = row["End Time"] - row["Start Time"]
            duration_str = str(time_taken).replace("0 days ", "").split(".")[0]
        else:
            duration_str = "-"

        overdue = False
        late_reason = ""
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]) and load > 0:
            actual_duration = (row["End Time"] - row["Start Time"]).total_seconds() / 60
            expected_duration = (load / 2.5) + 5
            if actual_duration > expected_duration:
                overdue = True
                late_reason = f"Expected ≤ {int(expected_duration)}min, got {int(actual_duration)}min"

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0

        visual_rows.append(
            html.Div([
                html.Div(name, className="staff-name"),
                html.Div(f"{int(load)}", className="load-display"),
                html.Div(duration_str, className="duration-display"),
                html.Div(late_reason, className="late-reason") if late_reason else None,
                dbc.Progress(value=load_percent, color="warning" if overdue else "success", style={"height": "16px"})
            ], className="card-content")
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Div(f"{tl_name}", className="tl-name"),
                html.Div(f"{short_label}", className="pool-title"),
                html.Div(f"⬆ Pool Up: {pool_up}", className="pool-time"),
                html.Div([
                    html.Span("🟢 Complete", className="complete"),
                    html.Span("  🔶 In Progress", className="in-progress"),
                    html.Span("  🔴 Late", className="late")
                ], className="pool-status"),
                html.Div([
                    html.Span(f"Total Count: {total_count}", style={"marginRight": "12px"}),
                    html.Span(f"Manpower: {manpower}", style={"marginRight": "12px"}),
                    html.Span(f"Expected Completion: {expected_time.strftime('%H:%M:%S') if expected_time else '-'}")
                ], className="pool-info-box")
            ], className="pool-header")
        ]),
        dbc.CardBody(html.Div(visual_rows, className="seat-grid", style={"padding": "10px"}))
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

app.layout = dbc.Container([
    dcc.Store(id="main-data"),
    dcc.Store(id="sequence-data"),

    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"font-size": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-timer", className="text-end countdown-glow", style={"font-size": "0.75rem"}), width=6)
    ], align="center"),

    dcc.Interval(id="auto-refresh", interval=180000, n_intervals=0),
    dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0),

    html.Div(id="current-pool"),
    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)
], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

# --- Callback: Refresh Data ---
@app.callback(
    Output("main-data", "data"),
    Output("sequence-data", "data"),
    Input("auto-refresh", "n_intervals")
)
def refresh_data(n):
    main_df = load_main_data()
    seq_df = load_pool_sequences()
    return main_df.to_dict("records"), seq_df.to_dict("records")

# --- Callback: Render Pool Blocks ---
@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("main-data", "data"),
    Input("sequence-data", "data")
)
def render_blocks(main_data, seq_data):
    main_df = pd.DataFrame(main_data)
    seq_df = pd.DataFrame(seq_data)

    short_map = seq_df.set_index("Pool ID")["Short"].to_dict()
    latest_pools = (
        main_df[main_df["Pool Up"].notna()]
        .groupby("Pool ID")["Pool Up"]
        .max()
        .reset_index()
        .sort_values("Pool Up", ascending=False)
    )

    pool_ids = latest_pools["Pool ID"].tolist()
    current_id = pool_ids[0] if pool_ids else None
    previous_ids = pool_ids[1:4] if len(pool_ids) > 1 else []

    def block(pool_id):
        pool_df = main_df[main_df["Pool ID"] == pool_id]
        short = short_map.get(pool_id, pool_id)
        return generate_status_block(pool_df, short)

    current = block(current_id) if current_id else html.Div("No current pool.")
    previous = [block(pid) for pid in previous_ids if pid in main_df["Pool ID"].unique()]
    return current, previous, f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
