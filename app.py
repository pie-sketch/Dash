import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import os

# Google Sheets CSV
MAIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
SEQUENCE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=973487960"

# Load Pool Sequences
def load_pool_sequences():
    df = pd.read_csv(SEQUENCE_SHEET_URL)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    df["Date"] = df["Pool Name"].str.extract(r'(\d{8})').fillna('')
    df["Short"] = df["Pools id"]
    return df

# Load main sheet data
def load_main_data():
    df = pd.read_csv(MAIN_SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

# Determine Pool Status
def get_pool_status(pool_id, main_df):
    pool_df = main_df[main_df["Pool ID"] == pool_id]
    if pool_df.empty:
        return "not-started", 0
    if pool_df["Pool Up"].notna().any():
        completed = pool_df["End Time"].notna().sum()
        active = pool_df["Start Time"].notna().sum()
        return ("complete" if completed == active else "in-progress"), pool_df["Load"].sum()
    return "not-started", pool_df["Load"].sum()

# Pool Progress Cards
def generate_pool_progress_cards(seq_df, main_df):
    cards = []
    for _, row in seq_df.iterrows():
        pool_id = row["Pool ID"]
        display = row["Short"]
        status, load = get_pool_status(pool_id, main_df)
        color_map = {
            "complete": "#99ffcc",
            "in-progress": "#ffe0b3",
            "not-started": "#ffff99"
        }
        card = html.Div(
            html.Div([
                html.Div(display, className="progress-label"),
                html.Div(f"Load: {int(load)}", className="progress-load")
            ], className="progress-card", id={"type": "scroll-target", "index": pool_id}, style={"backgroundColor": color_map[status]}),
            className="progress-card-wrapper",
            n_clicks=0,
            id={"type": "progress-card", "index": pool_id}
        )
        cards.append(card)
    return cards

def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up_time = tl["Pool Up"]
        pool_up = pool_up_time.strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
        total_count = int(tl["Load"]) if "Load" in tl else 0
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
        status, color, _ = get_status(row, pool_df)
        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_display = f"{int(load)}"

        # Duration display
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            time_taken = row["End Time"] - row["Start Time"]
            duration_str = str(time_taken).replace("0 days ", "").split(".")[0]
        else:
            time_taken = None
            duration_str = "-"

        # Late logic
        overdue = False
        late_reason = ""
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]) and load > 0:
            actual_duration = (row["End Time"] - row["Start Time"]).total_seconds() / 60
            expected_duration = (load / 2.5) + 5  # minutes
            if actual_duration > expected_duration:
                overdue = True
                late_reason = f"Expected ≤ {int(expected_duration)}min, got {int(actual_duration)}min"

        box_class = "card-content glow-card"
        progress_wrapper_class = ""
        if status == "In Progress":
            progress_wrapper_class = "animated-progress"
        if overdue:
            progress_wrapper_class = "animated-late"
            box_class += " overdue-box"

        # ✅ Wrap Progress with tooltip-compatible html.Div
        progress_component = html.Div(
            dbc.Progress(
                value=load_percent,
                color=color,
                striped=(status == "In Progress"),
                style={"height": "16px", "width": "100%"}
            ),
            title=late_reason if late_reason else None,
            className=progress_wrapper_class
        )

        visual_rows.append(
            html.Div([
                html.Div(name, className="staff-name"),
                progress_component,
                html.Div(load_display, className="load-display"),
                html.Div(duration_str, className="duration-display"),
                html.Div(late_reason, className="late-reason") if late_reason else None
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
                    html.Span(f"Expected Completion: {expected_time.strftime('%H:%M:%S') if expected_time else '-'}")
                ], className="pool-info-box")
            ], className="pool-header")
        ]),
        dbc.CardBody(
            html.Div(visual_rows, className="seat-grid", style={"padding": "10px"})
        )
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

app.layout = dbc.Container([
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

last_updated_timestamp = datetime.now()

@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("auto-refresh", "n_intervals")
)
def refresh_data(n):
    main_df = load_main_data()
    seq_df = load_pool_sequences()
    return main_df.to_dict("records"), seq_df.to_dict("records")

@app.callback(
    Output("progress-cards", "children"),
    Output("pool-blocks", "children"),
    Input("main-data", "data"),
    Input("sequence-data", "data")
)
def update_ui(main_data, seq_data):
    main_df = pd.DataFrame(main_data)
    seq_df = pd.DataFrame(seq_data)
    cards = generate_pool_progress_cards(seq_df, main_df)
    blocks = []
    for pool_id in seq_df["Pool ID"]:
        pool_df = main_df[main_df["Pool ID"] == pool_id]
        if not pool_df.empty:
            block = html.Div(
                generate_status_block(pool_df),
                id={"type": "pool-block", "index": pool_id}
            )
            blocks.append(block)
    return cards, blocks

@app.callback(
    Output("pool-blocks", "children", allow_duplicate=True),
    Input({"type": "progress-card", "index": dash.ALL}, "n_clicks"),
    State("pool-blocks", "children"),
    prevent_initial_call=True
)
def scroll_to_pool(n_clicks, children):
    triggered = dash.callback_context.triggered[0]["prop_id"]
    pool_id = eval(triggered.split(".")[0])["index"]
    scroll_script = html.Script(f'document.getElementById("{{\"type\":\"pool-block\",\"index\":\"{pool_id}\"}}")?.scrollIntoView({{behavior: "smooth"}});')
    return children + [scroll_script]

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)



