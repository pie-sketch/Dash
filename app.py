# Final complete Dash app with:
# 1. Default circular carousel-style Pool Progress Overview for today
# 2. Responsive glow-effect cards
# 3. Click-to-jump toggle for full detail view of selected pool
# 4. Uses Google Sheets as source (main + pool sequence)

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, ctx
import pandas as pd
from datetime import datetime, timedelta
import os

# Google Sheet URLs
MAIN_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
SEQ_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=973487960"

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Data Loaders ---
def load_main():
    df = pd.read_csv(MAIN_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

def load_sequence():
    df = pd.read_csv(SEQ_URL)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    df["Short"] = df["Pools id"]
    return df

# --- Pool Card & Detail Block ---
def get_status(row, df):
    if not pd.isna(row["Pool Up"]): return "TL", "secondary", ""
    if row["Load"] == 0: return "Helper", "secondary", ""
    tl = df[df["Pool Up"].notna()]
    max_load = tl["Load"].max() if not tl.empty else 1
    peers = df[(df["Pool Up"].isna()) & (df["Load"] > 0)]
    avg = max_load / len(peers) if len(peers) else 1
    return ("Complete", "success", "") if abs(row["Load"] - avg) <= 3 else ("In Progress", "warning", "")

def make_detail_block(df):
    tl = df[df["Pool Up"].notna()].iloc[0] if not df[df["Pool Up"].notna()].empty else None
    if not tl: return html.Div("Invalid Pool")

    pool_up_time = tl["Pool Up"]
    header = html.Div([
        html.Div(tl["Name"], className="tl-name"),
        html.Div(f"{tl['Pool Name']} - {tl['Tab']}", className="pool-title"),
        html.Div(f"\u2B06 Pool Up: {pool_up_time.strftime('%d/%m/%Y %H:%M:%S') if isinstance(pool_up_time, pd.Timestamp) else '-'}", className="pool-time"),
        html.Div("\U0001F7E2 Complete  \U0001F7E0 In Progress  \U0001F534 Late", className="pool-status"),
        html.Div([
            html.Span(f"Total Count: {int(tl['Load'])}", style={"marginRight": "10px"}),
            html.Span(f"Manpower: {len(df[(df['Pool Up'].isna()) & (df['Load'] > 0)])}", style={"marginRight": "10px"}),
            html.Span(f"Expected Completion: {(pool_up_time + timedelta(hours=1, minutes=5)).strftime('%H:%M:%S') if pool_up_time else '-'}")
        ], className="pool-info-box")
    ], className="pool-header")

    cards = []
    for _, row in df[(df["Pool Up"].isna()) & (df["Load"] > 0)].iterrows():
        name, load = row["Name"], row["Load"]
        status, color, _ = get_status(row, df)
        percent = min(100, int((load / (tl["Load"] / max(1, len(df)))) * 100))

        duration = "-"
        if pd.notna(row["Start Time"]) and pd.notna(row["End Time"]):
            td = row["End Time"] - row["Start Time"]
            duration = str(td).replace("0 days ", "").split(".")[0]

        expected = (load / 2.5) + 5
        actual = (row["End Time"] - row["Start Time"]).total_seconds() / 60 if pd.notna(row["End Time"]) and pd.notna(row["Start Time"]) else 0
        late_reason = f"Expected ≤ {int(expected)}min, got {int(actual)}min" if actual > expected else ""

        cards.append(html.Div([
            html.Div(name, className="staff-name"),
            html.Div(dbc.Progress(value=percent, color=color, striped=status=="In Progress", style={"height": "16px"}),
                     title=late_reason, className="animated-late" if actual > expected else "animated-progress" if status=="In Progress" else ""),
            html.Div(str(int(load)), className="load-display"),
            html.Div(duration, className="duration-display"),
            html.Div(late_reason, className="late-reason") if late_reason else None
        ], className="card-content glow-card"))

    return dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody(html.Div(cards, className="seat-grid"))
    ], style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- Layout ---
app.layout = dbc.Container([
    dcc.Store(id="main-data"),
    dcc.Store(id="sequence-data"),
    dcc.Store(id="selected-pool", data=None),
    dcc.Interval(id="refresh", interval=180000, n_intervals=0),
    dcc.Interval(id="countdown", interval=1000, n_intervals=0),

    dbc.Row([
        dbc.Col(html.Div(id="last-update", style={"fontSize": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-display", className="countdown-glow", style={"textAlign": "right", "fontSize": "0.75rem"}), width=6),
    ], align="center"),

    html.Div(id="carousel-view"),
    html.Div(id="detail-view"),
], fluid=True, style={"backgroundColor": "#0d1b2a", "padding": "1rem"})

last_updated = datetime.now()

# --- Callbacks ---
@app.callback(
    Output("main-data", "data"),
    Output("sequence-data", "data"),
    Input("refresh", "n_intervals")
)
def refresh_data(n):
    return load_main().to_dict("records"), load_sequence().to_dict("records")

@app.callback(
    Output("carousel-view", "children"),
    Output("detail-view", "children"),
    Output("last-update", "children"),
    Input("main-data", "data"),
    Input("sequence-data", "data"),
    Input("selected-pool", "data"),
)
def render(main_data, seq_data, selected_id):
    global last_updated
    last_updated = datetime.now()
    df, seq = pd.DataFrame(main_data), pd.DataFrame(seq_data)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_seq = seq[seq["Pool Name"].str.contains(today_str[:10].replace("-", ""))]

    if selected_id:
        detail = make_detail_block(df[df["Pool ID"] == selected_id])
        return None, detail, f"Last updated: {last_updated.strftime('%d/%m/%Y %H:%M:%S')}"

    cards = []
    for _, row in today_seq.iterrows():
        pid = row["Pool ID"]
        short = row["Short"]
        total = df[df["Pool ID"] == pid]["Load"].sum()
        cards.append(html.Div(short, className="progress-card", id={"type": "pool-card", "index": pid}, style={"backgroundColor": "#333", "boxShadow": "0 0 10px #39f"}))

    return html.Div(cards, className="carousel-wrap"), None, f"Last updated: {last_updated.strftime('%d/%m/%Y %H:%M:%S')}"

@app.callback(
    Output("selected-pool", "data"),
    Input({"type": "pool-card", "index": dash.ALL}, "n_clicks"),
    State({"type": "pool-card", "index": dash.ALL}, "id"),
    prevent_initial_call=True
)
def click_card(n_clicks, ids):
    for i, n in enumerate(n_clicks):
        if n:
            return ids[i]["index"]
    return dash.no_update

@app.callback(
    Output("countdown-display", "children"),
    Input("countdown", "n_intervals")
)
def update_countdown(n):
    remain = max(0, 180 - (datetime.now() - last_updated).seconds)
    return f"\u23F3 Refreshing in: {remain:02d}s"

@app.callback(
    Output("countdown-timer", "children"),
    Input("countdown-interval", "n_intervals")
)
def update_countdown(n):
    elapsed = (datetime.now() - last_updated_timestamp).seconds
    remaining = max(0, 180 - elapsed)
    return f"⏳ Refreshing in: {remaining:02d}s"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
