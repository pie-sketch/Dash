import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
import numpy as np
import plotly.express as px
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

    if pd.notna(row["Duration"]) and row["Duration"] <= 0.83:
        return "Helper", "secondary"

    active_staff = pool_df[
        (pool_df["Pool Up"].isna()) &
        (pool_df["Duration"] > 0.83)
    ]
    
    max_duration = active_staff["Duration"].max()
    duration_tolerance = 5  # minutes

    if pd.notna(row["Duration"]) and abs(row["Duration"] - max_duration) <= duration_tolerance:
        return "Complete", "success"

    return "In Progress", "warning"

# --- Status Bar Generator ---
def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up = tl["Pool Up"].strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
        total_load = tl["Load"]
    else:
        pool_name, tab, pool_up, tl_name, total_load = "-", "-", "-", "-", 0

    active_rows = pool_df[
        (pool_df["Pool Up"].isna()) & 
        (pool_df["Duration"] > 0.83)
    ].copy()

    num_staff = len(active_rows)
    per_person_target = np.ceil(total_load / num_staff) if num_staff else 1

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        duration = row["Duration"]
        status, color = get_status(row, pool_df)

        visual_rows.append(
            dbc.Row([
                dbc.Col(html.Div(name, className="text-white small fw-bold"), width=3),
                dbc.Col(html.Div(f"{duration:.1f} min", className="text-white fw-bold fs-5"), width=3),
                dbc.Col(dbc.Badge(status, color=color, className="ms-1 fs-6", pill=True), width="auto"),
            ], className="mb-2")
        )

    return dbc.Card([
        dbc.CardHeader(html.Div([
            html.Div(f"🧑 {tl_name}", className="text-center text-info small mb-0"),
            html.Div(f"{pool_name} - {tab}", className="text-center text-info small"),
            html.Div(f"⏫ Pool Up: {pool_up}", className="text-center text-info small")
        ])),

        dbc.CardBody(
            dbc.Row([
                # Left section: staff duration + status
                dbc.Col(visual_rows, md=5),

                # Right section: vertical duration bar
                dbc.Col(dcc.Graph(
                    figure=px.bar(
                        active_rows.sort_values("Duration"),
                        x="Name",
                        y="Duration",
                        text=active_rows["Duration"].map(lambda d: f"{d:.1f} min"),
                        color_discrete_sequence=["#66ff66"]
                    ).update_traces(textposition="outside").update_layout(
                        height=400,
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis_title="Staff",
                        yaxis_title="Duration (min)",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font_color="white"
                    )
                ), md=7)
            ])
        )
    ], className="mb-4")

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

    html.H5("Current Pool", className="mt-4"),
    html.Div(id="current-pool"),

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
        block = generate_status_block(sub_df)
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
    print(f"✅ Starting Dash app on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
