import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, ctx
import pandas as pd
from datetime import datetime, timedelta
import os

# --- Google Sheet URLs ---
MAIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
SEQUENCE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=973487960"

# --- Init global for countdown ---
last_updated_timestamp = datetime.now()

# --- Loaders ---
def load_main_data():
    df = pd.read_csv(MAIN_SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    return df

def load_pool_sequences():
    df = pd.read_csv(SEQUENCE_SHEET_URL)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]
    df["Short"] = df["Pools id"]
    return df

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

    html.Div(id="progress-cards"),
    html.Hr(className="bg-light"),
    html.Div(id="current-pool"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False),
    html.Div(id="pool-blocks")
], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

# --- Callbacks ---
@app.callback(
    Output("main-data", "data"),
    Output("sequence-data", "data"),
    Input("auto-refresh", "n_intervals")
)
def refresh_data(n):
    main_df = load_main_data()
    seq_df = load_pool_sequences()
    return main_df.to_dict("records"), seq_df.to_dict("records")

@app.callback(
    Output("progress-cards", "children"),
    Output("pool-blocks", "children"),
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("main-data", "data"),
    Input("sequence-data", "data")
)
def render_blocks(main_data, seq_data):
    global last_updated_timestamp
    last_updated_timestamp = datetime.now()

    main_df = pd.DataFrame(main_data)
    seq_df = pd.DataFrame(seq_data)

    # --- Replace with actual visual generation ---
    cards = [
        html.Div(row["Short"], style={"background": "#fff", "padding": "8px", "margin": "4px"})
        for _, row in seq_df.iterrows()
    ]
    blocks = [
        html.Div(row["Pool ID"], style={"background": "#222", "padding": "8px", "margin": "4px"})
        for _, row in seq_df.iterrows()
    ]
    current = html.Div("Current pool display")
    previous = html.Div("Previous pools")
    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")

    return cards, blocks, current, previous, updated_time

@app.callback(
    Output("countdown-timer", "children"),
    Input("countdown-interval", "n_intervals")
)
def update_countdown(n):
    global last_updated_timestamp
    elapsed = (datetime.now() - last_updated_timestamp).seconds
    remaining = max(0, 180 - elapsed)
    return f"⏳ Refreshing in: {remaining:02d}s"

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
