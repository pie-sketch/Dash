# app.py
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
from datetime import datetime, timedelta
import re
import os

# --- Google Sheet CSV ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=0"
POOL_MAP_URL = "https://docs.google.com/spreadsheets/d/1LltJKL6wsXQt_6Qv3rwjfL9StACcMHsNQ2C_wTKw_iw/export?format=csv&gid=973487960"

# --- Load Data ---
def strip_date(pool_name):
    return re.sub(r"_\d{8}", "", str(pool_name))

def load_data():
    df = pd.read_csv(SHEET_URL)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce", dayfirst=True)
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce", dayfirst=True)
    df["Pool Up"] = pd.to_datetime(df["Pool Up"], errors="coerce", dayfirst=True)
    df["Load"] = pd.to_numeric(df["Load"], errors="coerce").fillna(0)
    df["Pool ID"] = df["Pool Name"] + " - " + df["Tab"]

    pool_map = pd.read_csv(POOL_MAP_URL)
    pool_map["CleanName"] = pool_map["Pool Name"].apply(strip_date)
    pool_map_dict = dict(zip(pool_map["CleanName"] + " - " + pool_map["Tab"], pool_map["Pools"]))

    df["Clean ID"] = df["Pool Name"].apply(strip_date) + " - " + df["Tab"]
    df["Pools"] = df["Clean ID"].map(pool_map_dict)
    return df

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

def generate_pool_progress_row(df, recent_pool_ids):
    rows = []
    for pid in recent_pool_ids:
        pool_df = df[df["Pool ID"] == pid]
        tl_row = pool_df[pool_df["Pool Up"].notna()]
        if tl_row.empty:
            continue

        tl = tl_row.iloc[0]
        short_name = tl.get("Pools", f"{tl['Pool Name']} - {tl['Tab']}")
        pool_time = tl["Pool Up"].strftime("%H:%M")

        active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)]
        if active_rows.empty:
            status = "Not Started"
            color = "#cccc00"
        elif all(get_status(row, pool_df)[0] == "Complete" for _, row in active_rows.iterrows()):
            status = "Completed"
            color = "#00cc66"
        else:
            status = "In Progress"
            color = "#ffaa00"

        block = html.Div([
            html.Div(short_name, style={"fontWeight": "bold", "fontSize": "0.75rem"}),
            html.Div(pool_time, style={"fontSize": "0.7rem", "color": "#999"}),
            html.Div(status, style={"color": color, "fontSize": "0.8rem", "fontWeight": "bold"})
        ], className="mini-pool-box")
        rows.append(block)

    return html.Div([
        html.Div("POOL PROGRESS", className="pool-progress-title"),
        html.Div(list(reversed(rows)), className="pool-progress-row")
    ], style={"marginBottom": "12px"})

def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up = tl["Pool Up"].strftime("%d/%m/%Y %H:%M:%S")
    else:
        pool_name, tab, pool_up = "-", "-", "-"

    active_rows = pool_df[
        (pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)
    ].copy()

    total_load = tl_row["Load"].max() if not tl_row.empty else 0
    num_staff = len(active_rows)
    target_load = total_load / num_staff if num_staff else 1

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_bar = dbc.Progress(
            value=load_percent,
            color=color,
            striped=(status == "In Progress"),
            style={"height": "20px"},
        )

        visual_rows.append(
            dbc.Card([
                dbc.CardBody([
                    html.Div(name, style={"font-weight": "bold", "font-size": "1.1rem"}),
                    load_bar,
                    html.Div(status, style={"font-size": "0.9rem", "color": color})
                ], className="bg-dark text-white")
            ], className="mb-2", color="dark", inverse=True)
        )

    return dbc.Card([
        dbc.CardHeader(html.Div([
            html.Div("\U0001F465 Manpower", className="text-center", style={"font-size": "1.2rem", "font-weight": "bold"}),
            html.Div(f"{pool_name} - {tab}", className="text-center", style={"font-size": "1.2rem"}),
            html.Div(f"\u2B06 Pool Up: {pool_up}", className="text-center", style={"font-size": "1.2rem"})
        ]), className="bg-dark text-white"),

        dbc.CardBody(
            html.Div(
                visual_rows,
                style={"display": "flex", "flexWrap": "wrap", "gap": "1rem", "justifyContent": "center"}
            ),
            className="bg-dark text-white"
        )
    ], className="mb-4", color="dark", inverse=True)


# --- Dash App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

app.layout = html.Div([
    dbc.Container([
        dbc.Row([
            dbc.Col(html.Div(id="last-update", className="text-start text-secondary", style={"fontSize": "0.75rem"}), width=6),
            dbc.Col(html.Div(id="countdown-timer", className="text-end countdown-glow", style={"fontSize": "0.75rem"}), width=6)
        ]),
        dcc.Interval(id="auto-refresh", interval=15000, n_intervals=0),
        dcc.Interval(id="countdown-interval", interval=1000, n_intervals=0),
        html.Div(id="current-pool"),
        html.Hr(className="bg-light"),
        dbc.Button("Show Previous Pools", id="toggle-collapse", color="info", className="mb-2", style={"width": "100%"}),
        dbc.Collapse(id="previous-pools", is_open=False)
    ], fluid=True)
], style={"backgroundColor": "#0d1b2a", "minHeight": "100vh", "padding": "1rem"})


last_updated_timestamp = datetime.now()

@app.callback(
    Output("current-pool", "children"),
    Output("previous-pools", "children"),
    Output("last-update", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_dashboard(n):
    global last_updated_timestamp
    last_updated_timestamp = datetime.now()

    df = load_data()
    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(15)
    pool_ids = pool_groups["Pool ID"].tolist()

    progress_row = generate_pool_progress_row(df, pool_ids)
    pool_blocks = [generate_status_block(df[df["Pool ID"] == pid]) for pid in pool_ids]

    updated_time = last_updated_timestamp.strftime("Last updated: %d/%m/%Y %H:%M:%S")
    return [progress_row, pool_blocks[0]], pool_blocks[1:], updated_time

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
