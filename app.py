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
    df["Date"] = df["Pool Name"].str.extract(r'(\d{8})').fillna('')
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

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dcc.Store(id="main-data"),
    dcc.Store(id="sequence-data"),

    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"font-size": "0.75rem"}), width=6),
        dbc.Col(html.Div(id="countdown-timer", className="text-end text-secondary", style={"font-size": "0.75rem"}), width=6)
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


# --- Callback: Render UI ---
@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("main-data", "data"),
    Input("sequence-data", "data")
)
def render_pool_blocks(main_data, seq_data):
    main_df = pd.DataFrame(main_data)
    seq_df = pd.DataFrame(seq_data)

    today = datetime.now().strftime("%Y%m%d")
    current_pool_id = None
    previous_pools = []

    for _, row in seq_df.iterrows():
        if row["Date"] == today:
            current_pool_id = row["Pool ID"]
        else:
            previous_pools.append(row["Pool ID"])

    def generate_block(pool_id):
        pool_df = main_df[main_df["Pool ID"] == pool_id]
        if pool_df.empty:
            return None
        return dbc.Card([
            dbc.CardHeader(html.H5(pool_id, className="text-light")),
            dbc.CardBody([
                html.Div([
                    html.Div(f"{row['Name']}: {int(row['Load'])} load", className="text-white")
                    for _, row in pool_df.iterrows()
                ])
            ])
        ], className="mb-3", style={"backgroundColor": "#1e2a38"})

    current = generate_block(current_pool_id) if current_pool_id else html.Div("No current pool.")
    previous = [generate_block(pid) for pid in previous_pools if generate_block(pid)]

    return current, previous, f"Last updated: {datetime.now().strftime('%H:%M:%S')}"

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
