import os
import pandas as pd
import numpy as np

import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px


# ============================================================
# 1) DATA
# ============================================================
DATA_PATH = os.environ.get("DATA_PATH", "supermarket_sales.csv")
df = pd.read_csv(DATA_PATH)

# Types
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

# Week start (Monday)
df["Week"] = df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")

# Options
cities = sorted(df["City"].dropna().unique().tolist())
genders = sorted(df["Gender"].dropna().unique().tolist())


# ============================================================
# 2) HELPERS
# ============================================================
def fmt_money(x: float) -> str:
    """Format court: 123456 -> 123k (sin símbolo para ser neutro)."""
    x = float(x)
    if abs(x) >= 1000:
        return f"{x/1000:.0f}k"
    return f"{x:,.0f}".replace(",", " ")

def kpi_card(title: str, value: str, subtitle: str = ""):
    return dbc.Card(
        dbc.CardBody([
            html.Div(title, className="kpi-title"),
            html.Div(value, className="kpi-value"),
            html.Div(subtitle, className="kpi-subtitle"),
        ]),
        className="kpi-card"
    )

def empty_fig(title: str):
    fig = px.line(title=title)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=60, b=10))
    fig.add_annotation(
        text="Aucune donnée pour ce filtre.",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
    )
    return fig


# ============================================================
# 3) APP
# ============================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Supermarket Sales"
)
server = app.server  # <- pour gunicorn (Render)

app.layout = dbc.Container([

    # ---------------- HEADER ----------------
    dbc.Row([
        dbc.Col(
            html.Div("Supermarket Sales", className="app-title"),
            md=4
        ),

        dbc.Col([
            dcc.Dropdown(
                id="dd_city",
                options=[{"label": c, "value": c} for c in cities],
                value=cities,          # défaut: toutes
                multi=True,
                placeholder="Ville",
                className="dd",
                clearable=False,
            )
        ], md=4),

        dbc.Col([
            dcc.Dropdown(
                id="dd_gender",
                options=[{"label": g, "value": g} for g in genders],
                value=genders,         # défaut: tous
                multi=True,
                placeholder="Sexe",
                className="dd",
                clearable=False,
            )
        ], md=4),
    ], className="header g-2"),

    # ---------------- KPIs ----------------
    dbc.Row([
        dbc.Col(html.Div(id="kpi_total"), md=6),
        dbc.Col(html.Div(id="kpi_count"), md=6),
    ], className="g-2 mt-2"),

    # ---------------- GRAPHS ----------------
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Répartition des montants totaux (Total)", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_hist", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=6
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Nombre d’achats (Invoice ID)", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_bar", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=6
        ),
    ], className="g-2 mt-2"),

    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Evolution du montant total par semaine (par ville)", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_week", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=12
        )
    ], className="g-2 mt-2"),

], fluid=True)


# ============================================================
# 4) CALLBACK
# ============================================================
@app.callback(
    Output("kpi_total", "children"),
    Output("kpi_count", "children"),
    Output("fig_hist", "figure"),
    Output("fig_bar", "figure"),
    Output("fig_week", "figure"),
    Input("dd_city", "value"),
    Input("dd_gender", "value"),
)
def update_dashboard(city_values, gender_values):
    dff = df.copy()

    # filtres multi
    if city_values:
        dff = dff[dff["City"].isin(city_values)]
    if gender_values:
        dff = dff[dff["Gender"].isin(gender_values)]

    if dff.empty:
        return (
            kpi_card("Montant total des achats", "0", "Somme de Total"),
            kpi_card("Nombre total d’achats", "0", "Nombre de Invoice ID"),
            empty_fig("Histogramme"),
            empty_fig("Barres"),
            empty_fig("Semaine"),
        )

    # ----- KPI 1: Total purchases -----
    total_sum = dff["Total"].sum()
    kpi1 = kpi_card(
        "Montant total des achats",
        fmt_money(total_sum),
        "Somme de Total"
    )

    # ----- KPI 2: Count purchases -----
    # (Invoice ID est unique par ligne, mais nunique est robuste)
    n_invoices = dff["Invoice ID"].nunique()
    kpi2 = kpi_card(
        "Nombre total d’achats",
        f"{n_invoices:,}".replace(",", " "),
        "Nombre de Invoice ID"
    )

    # ----- Graph 1: Histogramme Total (sex + ville) -----
    # Facet par ville si plusieurs, sinon simple
    facet = "City" if dff["City"].nunique() > 1 else None
    fig_hist = px.histogram(
        dff,
        x="Total",
        color="Gender",
        facet_col=facet,
        facet_col_wrap=3,
        nbins=30,
        barmode="overlay",
        opacity=0.75,
    )
    fig_hist.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Sexe")
    fig_hist.update_xaxes(title_text="Total")
    fig_hist.update_yaxes(title_text="Fréquence")

    # ----- Graph 2: Bar count purchases (sex + ville) -----
    bar_df = (
        dff.groupby(["City", "Gender"])["Invoice ID"]
        .nunique()
        .reset_index(name="Nb_achats")
    )
    fig_bar = px.bar(
        bar_df,
        x="City",
        y="Nb_achats",
        color="Gender",
        barmode="group",
        text="Nb_achats",
    )
    fig_bar.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Sexe")
    fig_bar.update_xaxes(title_text="Ville")
    fig_bar.update_yaxes(title_text="Nombre d’achats")
    fig_bar.update_traces(textposition="outside")

    # ----- Graph 3: Weekly evolution of Total by city -----
    wk = (
        dff.groupby(["Week", "City"])["Total"]
        .sum()
        .reset_index()
        .sort_values("Week")
    )
    fig_week = px.line(
        wk,
        x="Week",
        y="Total",
        color="City",
        markers=True
    )
    fig_week.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Ville")
    fig_week.update_xaxes(title_text="Semaine")
    fig_week.update_yaxes(title_text="Montant total (Total)")

    return kpi1, kpi2, fig_hist, fig_bar, fig_week


# ============================================================
# 5) RUN (local + Render)
# ============================================================
if __name__ == "__main__":
    # Render: must listen on 0.0.0.0 and on PORT env var :contentReference[oaicite:1]{index=1}
    port = int(os.environ.get("PORT", "8050"))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
