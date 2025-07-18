import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output
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

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H3("📊 Live Pool Dashboard"), width=12)
    ]),

    dcc.Interval(id="auto-refresh", interval=60*1000, n_intervals=0),

    dbc.Row([
        dbc.Col(html.Div(id="pool-current"), width=4),
        dbc.Col(html.Div(id="pool-prev1"), width=4),
        dbc.Col(html.Div(id="pool-prev2"), width=4),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="duration-hist"), md=4),
        dbc.Col(dcc.Graph(id="load-pie"), md=4),
        dbc.Col(dcc.Graph(id="load-line"), md=4),
    ]),

    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-end text-secondary mt-2"), width=12)
    ])
], fluid=True)

# --- Callback ---
@app.callback(
    [Output("duration-hist", "figure"),
     Output("load-pie", "figure"),
     Output("load-line", "figure"),
     Output("pool-current", "children"),
     Output("pool-prev1", "children"),
     Output("pool-prev2", "children"),
     Output("last-update", "children")],
    Input("auto-refresh", "n_intervals")
)
def update_charts(n):
    df = load_data()

    # Identify unique pools by Pool ID and latest Pool Up
    pool_groups = df[df["Pool Up"].notna()].groupby("Pool ID")["Pool Up"].max().reset_index()
    pool_groups = pool_groups.sort_values("Pool Up", ascending=False).head(3)

    pool_ids = pool_groups["Pool ID"].tolist()
    pools = []

    for pool_id in pool_ids:
        pool_df = df[df["Pool ID"] == pool_id]
        pool_title = html.H5(pool_id)
        task_list = html.Ul([
            html.Li(f"{row['Name']}: Load {row['Load']}, Start: {row['Start Time']}, End: {row['End Time']}")
            for _, row in pool_df.iterrows()
        ])
        pools.append(html.Div([pool_title, task_list]))

    # Chart data (from whole dataframe, not limited to current pool)
    df = df[df["Start Time"].notna() & df["End Time"].notna()]

    fig_dur = px.histogram(df, x="Duration", nbins=20, title="Duration Histogram")
    fig_pie = px.pie(df.groupby("Name")["Load"].sum().reset_index(),
                     names="Name", values="Load", title="Load Distribution")
    fig_line = px.line(df.sort_values("Start Time"), x="Start Time", y="Load",
                       title="Load Over Time", markers=True)

    return (
        fig_dur,
        fig_pie,
        fig_line,
        pools[0] if len(pools) > 0 else html.Div("No Current Pool"),
        pools[1] if len(pools) > 1 else html.Div("No Previous Pool 1"),
        pools[2] if len(pools) > 2 else html.Div("No Previous Pool 2"),
        f"Last updated: {pd.Timestamp.now():%d/%m/%Y %H:%M:%S}"
    )

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
