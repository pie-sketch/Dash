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
    return df

# --- App Init ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "Live Pool Dashboard"

# --- Layout ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("📊 Live Pool Dashboard", className="text-center text-light mb-4"), width=12)
    ]),

    dcc.Interval(id="auto-refresh", interval=60*1000, n_intervals=0),

    dbc.Row([
        dbc.Col(dcc.Graph(id="duration-hist"), md=4),
        dbc.Col(dcc.Graph(id="load-pie"), md=4),
        dbc.Col(dcc.Graph(id="load-line"), md=4),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(html.Div(id="last-update", className="text-end text-secondary"), width=12)
    ])
], fluid=True)

# --- Callback ---
@app.callback(
    [Output("duration-hist", "figure"),
     Output("load-pie", "figure"),
     Output("load-line", "figure"),
     Output("last-update", "children")],
    Input("auto-refresh", "n_intervals")
)
def update_charts(n):
    df = load_data()
    df = df[df["Start Time"].notna() & df["End Time"].notna()]

    # --- Duration Histogram ---
    fig_dur = px.histogram(df, x="Duration", nbins=20, title="Duration Histogram",
                           color_discrete_sequence=["#8e44ad"])

    # --- Load Pie Chart ---
    pie_data = df.groupby("Name")["Load"].sum().reset_index()
    fig_pie = px.pie(pie_data, names="Name", values="Load", title="Load Distribution by Person",
                     color_discrete_sequence=px.colors.sequential.RdBu)

    # --- Line Chart ---
    df_sorted = df.sort_values("Start Time")
    fig_line = px.line(df_sorted, x="Start Time", y="Load", markers=True, title="Load Over Time",
                       color_discrete_sequence=["#fab1a0"])

    for fig in [fig_dur, fig_pie, fig_line]:
        fig.update_layout(paper_bgcolor="#111", plot_bgcolor="#222", font_color="white")

    return fig_dur, fig_pie, fig_line, f"Last updated: {pd.Timestamp.now():%d/%m/%Y %H:%M:%S}"

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
