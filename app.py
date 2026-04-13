import os
import pandas as pd
import numpy as np

import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px

# =========================
# 1) DATA
# =========================
DATA_PATH = os.environ.get("DATA_PATH", "supermarket_sales.csv")
df = pd.read_csv(DATA_PATH)

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])

df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

# Week start (Monday)
df["Week"] = df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")

cities = sorted(df["City"].dropna().unique().tolist())
genders = sorted(df["Gender"].dropna().unique().tolist())

# Plotly global style
px.defaults.template = "plotly_white"


# =========================
# 2) HELPERS
# =========================
def fmt_compact(x: float) -> str:
    x = float(x)
    if abs(x) >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"{x/1_000:.0f}k"
    return f"{x:,.0f}".replace(",", " ")

def kpi_card(title: str, value: str, subtitle: str):
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
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
    fig.add_annotation(
        text="Aucune donnée pour ce filtre.",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
    )
    return fig


# =========================
# 3) APP + LAYOUT
# =========================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="Supermarket Sales")
server = app.server  # for Render/gunicorn

app.layout = dbc.Container([

    # ---------- HEADER ----------
    dbc.Row([
        dbc.Col([
            html.Div("Supermarket Sales", className="app-title"),
            html.Div("Dashboard interactif (Sexe + Ville)", className="app-subtitle"),
        ], md=5),

        dbc.Col([
            html.Div("Ville", className="filter-label"),
            dcc.Dropdown(
                id="dd_city",
                options=[{"label": c, "value": c} for c in cities],
                value=cities,
                multi=True,
                clearable=False,
                className="dd",
            ),
        ], md=4),

        dbc.Col([
            html.Div("Sexe", className="filter-label"),
            dcc.Dropdown(
                id="dd_gender",
                options=[{"label": g, "value": g} for g in genders],
                value=genders,
                multi=True,
                clearable=False,
                className="dd",
            ),
        ], md=3),
    ], className="header g-2"),

    # ---------- KPIs ----------
    dbc.Row([
        dbc.Col(html.Div(id="kpi_total"), md=6),
        dbc.Col(html.Div(id="kpi_rating"), md=6),
    ], className="g-2 mt-2"),

    # ---------- GRAPHS ----------
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Nombre d’achats par ville et sexe", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_bar", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=6
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Répartition des catégories (Product line)", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_pie", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=6
        ),
    ], className="g-2 mt-2"),

    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Évolution hebdomadaire du montant total (par ville)", className="panel-title"),
                dcc.Loading(dcc.Graph(id="fig_week", config={"displayModeBar": False}), type="dot")
            ]), className="panel-card"),
            md=12
        )
    ], className="g-2 mt-2"),

], fluid=True)


# =========================
# 4) CALLBACK
# =========================
@app.callback(
    Output("kpi_total", "children"),
    Output("kpi_rating", "children"),
    Output("fig_bar", "figure"),
    Output("fig_pie", "figure"),
    Output("fig_week", "figure"),
    Input("dd_city", "value"),
    Input("dd_gender", "value"),
)
def update_dashboard(city_values, gender_values):
    # sécurité: si l'utilisateur vide tout, on remet "toutes"
    if not city_values:
        city_values = cities
    if not gender_values:
        gender_values = genders

    dff = df[df["City"].isin(city_values) & df["Gender"].isin(gender_values)].copy()

    if dff.empty:
        return (
            kpi_card("Montant total des achats", "0", "Somme de Total"),
            kpi_card("Évaluation moyenne", "NA", "Moyenne de Rating"),
            empty_fig("Barres"),
            empty_fig("Donut"),
            empty_fig("Semaine"),
        )

    # ----- KPIs -----
    total_sum = dff["Total"].sum()
    avg_rating = dff["Rating"].mean()

    kpi1 = kpi_card("Montant total des achats", fmt_compact(total_sum), "Somme de Total")
    kpi2 = kpi_card("Évaluation moyenne", f"{avg_rating:.2f}", "Moyenne de Rating")

    # ----- Graph 1: Barres (nb achats par ville & sexe) -----
    bar_df = (
        dff.groupby(["City", "Gender"])["Invoice ID"]
        .nunique()
        .reset_index(name="Nb_achats")
    )
    # ordre des villes par volume total
    city_order = (
        bar_df.groupby("City")["Nb_achats"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    fig_bar = px.bar(
        bar_df,
        x="City",
        y="Nb_achats",
        color="Gender",
        barmode="group",
        category_orders={"City": city_order},
        text="Nb_achats",
    )
    fig_bar.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Sexe")
    fig_bar.update_traces(textposition="outside", cliponaxis=False)
    fig_bar.update_yaxes(title_text="Nombre d’achats")

    # ----- Graph 2: Donut Product line -----
    pie_df = (
        dff.groupby("Product line")["Invoice ID"]
        .nunique()
        .reset_index(name="Nb_achats")
        .sort_values("Nb_achats", ascending=False)
    )
    fig_pie = px.pie(
        pie_df,
        names="Product line",
        values="Nb_achats",
        hole=0.45,
    )
    fig_pie.update_traces(textinfo="percent+label")
    fig_pie.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))

    # ----- Graph 3: Weekly evolution Total by City -----
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
        markers=True,
        line_shape="spline",
    )
    fig_week.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Ville")
    fig_week.update_yaxes(title_text="Montant total (Total)")
    fig_week.update_xaxes(title_text="Semaine")

    return kpi1, kpi2, fig_bar, fig_pie, fig_week


# =========================
# 5) RUN (Render-ready)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)