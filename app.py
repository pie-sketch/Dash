import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State
import pandas as pd
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
    df["Duration"] = (df["End Time"] - df["Start Time"]).dt.total_seconds() / 15
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

def generate_status_block(pool_df):
    tl_row = pool_df[pool_df["Pool Up"].notna()]
    if not tl_row.empty:
        tl = tl_row.iloc[0]
        pool_name = tl["Pool Name"]
        tab = tl["Tab"]
        pool_up_time = tl["Pool Up"]
        pool_up = pool_up_time.strftime("%d/%m/%Y %H:%M:%S")
        tl_name = tl["Name"]
        total_count = int(tl["Count"]) if "Count" in tl else 0
    else:
        pool_name, tab, pool_up, tl_name = "-", "-", "-", "-"
        total_count = 0

    active_rows = pool_df[(pool_df["Pool Up"].isna()) & (pool_df["Load"] > 0)].copy()
    total_load = tl_row["Load"].max() if not tl_row.empty else 0
    num_staff = len(active_rows)
    target_load = total_load / num_staff if num_staff else 1

    expected_time = pool_up_time + timedelta(hours=1, minutes=5) if not pd.isna(pool_up_time) else "-"

    visual_rows = []
    for _, row in active_rows.iterrows():
        name = row["Name"]
        load = row["Load"]
        status, color = get_status(row, pool_df)

        load_percent = min(100, int((load / target_load) * 100)) if target_load else 0
        load_display = f"{int(load)}"

        completion_time = row["End Time"] - row["Start Time"]
        completion_time_str = str(timedelta(seconds=int(completion_time.total_seconds()))) if pd.notna(completion_time) else "-"

        visual_rows.append(
            html.Div([
                html.Div(name, style={"font-weight": "bold", "font-size": "0.8rem", "text-align": "center"}),
                dbc.Progress(value=load_percent, color=color, striped=(status == "In Progress"), style={"height": "16px", "width": "100%"}),
                html.Div(load_display, style={"font-size": "0.75rem", "text-align": "center", "marginTop": "4px"}),
                html.Div(completion_time_str, style={"font-size": "0.7rem", "text-align": "center", "marginTop": "2px", "color": "#aaa"})
            ], className="card-content glow-card")
        )

    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.Div([
                    html.Div([f"Total Count: {total_count}"], style={"font-size": "0.8rem", "color": "#aaa"}),
                    html.Div([f"Individual Count: {num_staff}"], style={"font-size": "0.8rem", "color": "#aaa"}),
                    html.Div([f"Expected Completion: {expected_time.strftime('%H:%M:%S') if expected_time != '-' else '-'}"], style={"font-size": "0.8rem", "color": "#aaa"})
                ], style={"text-align": "left", "position": "absolute"}),

                html.Div(f"{tl_name}", className="pool-title"),
                html.Div(f"{pool_name} - {tab}", className="pool-title"),
                html.Div(f"⬆ Pool Up: {pool_up}", className="pool-time"),
                html.Div("🟢 Complete    🟠 In Progress", className="pool-status")
            ], className="pool-header")
        ]),
        dbc.CardBody(
            html.Div(
                visual_rows,
                style={"display": "flex", "flexWrap": "wrap", "justifyContent": "center", "gap": "12px", "padding": "10px"}
            )
        )
    ], className="mb-4", style={"backgroundColor": "#0d1b2a", "borderRadius": "15px"})

# Other parts of the app remain unchanged, including countdown logic and layout
