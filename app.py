import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime
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

# --- Status Block Generator ---
def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up = tl["Pool Up"].strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
    else:
        pool_name, tab, pool_up, tl_name = "-", "-", "-", "-"

    active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)].copy()
    total_load = tl_row["Load"].max() if not tl_row.empty else 0
    num_staff = len(active_rows)
    target_load = total_load / num_staff if num_staff else 1

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)
        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0

        visual_rows.append(
            html.Div([
                html.Div(name, style={"font-weight": "bold", "font-size": "0.95rem", "text-align": "center"}),
                dbc.Progress(value=load_percent, color=color, striped=(status == "In Progress"),
                             style={"height": "18px", "width": "100%"}),
                html.Div(f"{load_percent}%", style={"font-size": "0.85rem", "text-align": "center", "marginTop": "4px"})
            ], className="card-content glow-card")
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div(tl_name, className="text-center", style={"font-size": "1.3rem", "fontWeight": "bold"}),
            html.Div(f"{pool_name} - {tab}", className="text-center", style={"font-size": "1rem"}),
            html.Div(f"\u2B06 Pool Up: {pool_up}", className="text-center", style={"font-size": "0.9rem"}),
            html.Div("🟢 Complete &nbsp;&nbsp; 🟠 In Progress", className="text-center mt-2",
                     style={"font-size": "0.85rem", "color": "lightgray"})
        ]),
        dbc.CardBody(
            html.Div(
                visual_rows,
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "justifyContent": "center",
                    "gap": "12px",
                    "padding": "10px"
                }
            )
        )
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H3("Live Pool", className="text-light"), xs=12, md=8),
        dbc.Col(html.Div(id="last-update", className="text-end text-secondary mt-2", style={"font-size": "0.85rem"}), xs=12, md=4)
    ], align="center", className="mb-3"),

    dcc.Interval(id="auto-refresh", interval=60000, n_intervals=0),

    html.H5("Current Pool", className="mt-4 text-light text-center"),
    html.Div(id="current-pool"),

    html.Hr(className="bg-light"),
    dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
    dbc.Collapse(id="previous-pools", is_open=False)

], fluid=True, style={"background-color": "#0d1b2a", "padding": "1rem"})

# --- Callback: Refresh Display ---
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
        block = generate_status_block(sub_df)
        pool_blocks.append(block)

    current = pool_blocks[0] if pool_blocks else html.Div("No current pool found.")
    previous = pool_blocks[1:] if len(pool_blocks) > 1 else []

    updated_time = datetime.now().strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return current, previous, updated_time

# --- Callback: Toggle Previous Pools ---
@app.callback(
    Output("previous-pools", "is_open"),
    Input("toggle-collapse", "n_clicks"),
    State("previous-pools", "is_open"),
    prevent_initial_call=True
)
def toggle_previous(n, is_open):
    return not is_open

# --- Run App ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"\u2705 Starting Dash app on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
