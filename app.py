import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
import plotly.express as px
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

# --- Get Status Color ---
def get_status(row):
    if pd.isna(row["Start Time"]):
        return "Not Started", "secondary"
    elif pd.isna(row["End Time"]):
        return "In Progress", "warning"
    else:
        return "Complete", "success"

# --- Status Table Generator ---
def generate_status_table(pool_df):
    rows = []
    for _, row in pool_df.iterrows():
        status, color = get_status(row)
        pill = dbc.Badge(status, color=color, className="ms-1", pill=True)
        rows.append(
            html.Tr([
                html.Td(row["Name"]),
                html.Td(int(row["Load"])),
                html.Td(pill)
            ])
        )
    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Name"), html.Th("Load"), html.Th("Status")]))] + [html.Tbody(rows)],
        bordered=True, hover=True, responsive=True, striped=True, className="mt-2"
    )

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H3("📊 Live Pool Dashboard"), width=8),
        dbc.Col(html.Div(id="last-update", className="text-end text-secondary mt-2"), width=4)
    ]),

    dcc.Interval(id="auto-refresh", interval=60000, n_intervals=0),

    # --- Current Pool ---
    html.H5("Current Pool", className="mt-4"),
    html.Div(id="current-pool"),

    # --- Previous Pools (Collapsed) ---
    html.Hr(),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2"),
    dbc.Collapse(id="previous-pools", is_open=False),

], fluid=True)

# --- Callback ---
@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    df = load_data()
    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(3)
    pool_ids = pool_groups["Pool ID"].tolist()

    pool_blocks = []
    for pid in pool_ids:
        sub_df = df[df["Pool ID"] == pid]
        table = generate_status_table(sub_df)
        block = dbc.Card([
            dbc.CardHeader(html.H6(pid)),
            dbc.CardBody(table)
        ], className="mb-3")
        pool_blocks.append(block)

    current = pool_blocks[0] if pool_blocks else html.Div("No current pool found.")
    previous = pool_blocks[1:] if len(pool_blocks) > 1 else []

    return current, previous, f"Last updated: {pd.Timestamp.now():%d/%m/%Y %H:%M:%S}"

# --- Collapse Toggle ---
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

