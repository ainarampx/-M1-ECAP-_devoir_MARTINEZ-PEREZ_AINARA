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

# Plotly: style global
px.defaults.template = "plotly_white"
COLORWAY = ["#4F46E5", "#F97316", "#10B981", "#EF4444", "#06B6D4", "#A855F7"]

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

def style_fig(fig):
    fig.update_layout(
        colorway=COLORWAY,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(15,23,42,0.07)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(15,23,42,0.07)")
    return fig

def kpi_card(title: str, value: str, subtitle: str, icon: str):
    return dbc.Card(
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.Div(title, className="kpi-title"),
                    html.Div(value, className="kpi-value"),
                    html.Div(subtitle, className="kpi-subtitle"),
                ]),
                html.Div(html.I(className=f"bi {icon}"), className="kpi-icon"),
            ], className="kpi-row"),
        ]),
        className="card-soft kpi-card"
    )

def empty_fig(title: str):
    fig = px.line(title=title)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    fig.add_annotation(
        text="Aucune donnée pour ce filtre.",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
    )
    return fig

# =========================
# 3) APP + LAYOUT
# =========================
# 👉 Tema + iconos Bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX, dbc.icons.BOOTSTRAP],
    title="Supermarket Sales"
)
server = app.server  # Render

app.layout = dbc.Container([

    # ---------- TOP BAR ----------
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
                placeholder="Ville",
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
                placeholder="Sexe",
            ),
        ], md=3),
    ], className="topbar g-2"),

    # ---------- KPIs ----------
    dbc.Row([
        dbc.Col(html.Div(id="kpi_total"), md=6),
        dbc.Col(html.Div(id="kpi_rating"), md=6),
    ], className="g-2 mt-2"),

    # ---------- CHARTS ----------
    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Nombre d'achats par ville et sexe", className="panel-title"),
                dcc.Loading(
                    dcc.Graph(id="fig_bar", config={"displayModeBar": False}),
                    type="dot"
                )
            ]), className="card-soft"),
            md=6
        ),
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Répartition des catégories (Product line)", className="panel-title"),
                dcc.Loading(
                    dcc.Graph(id="fig_pie", config={"displayModeBar": False}),
                    type="dot"
                )
            ]), className="card-soft"),
            md=6
        ),
    ], className="g-2 mt-2"),

    dbc.Row([
        dbc.Col(
            dbc.Card(dbc.CardBody([
                html.Div("Évolution hebdomadaire du montant total (par ville)", className="panel-title"),
                dcc.Loading(
                    dcc.Graph(id="fig_week", config={"displayModeBar": False}),
                    type="dot"
                )
            ]), className="card-soft"),
            md=12
        )
    ], className="g-2 mt-2 mb-3"),

], fluid=True, className="page")


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
    if not city_values:
        city_values = cities
    if not gender_values:
        gender_values = genders

    dff = df[df["City"].isin(city_values) & df["Gender"].isin(gender_values)].copy()

    if dff.empty:
        return (
            kpi_card("Montant total des achats", "0", "Somme de Total", "bi-cash-coin"),
            kpi_card("Évaluation moyenne", "NA", "Moyenne de Rating", "bi-star-fill"),
            empty_fig("Barres"),
            empty_fig("Donut"),
            empty_fig("Semaine"),
        )

    # KPIs
    total_sum = dff["Total"].sum()
    avg_rating = dff["Rating"].mean()

    kpi1 = kpi_card("Montant total des achats", fmt_compact(total_sum), "Somme de Total", "bi-cash-coin")
    kpi2 = kpi_card("Évaluation moyenne", f"{avg_rating:.2f}", "Moyenne de Rating", "bi-star-fill")

    # 1) Bar chart: nb achats par ville et sexe
    bar_df = (
        dff.groupby(["City", "Gender"])["Invoice ID"]
        .nunique()
        .reset_index(name="Nb_achats")
    )
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
    fig_bar.update_traces(textposition="outside", cliponaxis=False)
    fig_bar.update_yaxes(title_text="Nombre d’achats")
    fig_bar.update_xaxes(title_text="")
    fig_bar.update_layout(height=380)
    fig_bar = style_fig(fig_bar)

    # 2) Donut: Product line
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
        hole=0.55,
    )
    fig_pie.update_traces(textinfo="percent", textposition="inside")
    fig_pie.update_layout(height=380, showlegend=True)
    fig_pie = style_fig(fig_pie)

    # 3) Weekly evolution: Total by city
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
    fig_week.update_layout(height=380)
    fig_week.update_yaxes(title_text="Montant total (Total)")
    fig_week.update_xaxes(title_text="Semaine")
    fig_week.update_traces(line=dict(width=3), marker=dict(size=7))
    fig_week = style_fig(fig_week)

    return kpi1, kpi2, fig_bar, fig_pie, fig_week


# =========================
# 5) RUN (Render-ready)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)