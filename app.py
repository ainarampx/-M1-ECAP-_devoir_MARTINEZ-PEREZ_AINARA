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

# Parse date + numeric
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")  # format type M/D/YYYY in dataset
df = df.dropna(subset=["Date"])

df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

# Week start (Monday)
df["Week"] = df["Date"] - pd.to_timedelta(df["Date"].dt.weekday, unit="D")

cities = sorted(df["City"].dropna().unique().tolist())
genders = sorted(df["Gender"].dropna().unique().tolist())

px.defaults.template = "plotly_white"


# ============================================================
# 2) STYLE (colors + helpers)
# ============================================================
PASTEL_GENDER = {
    "Female": "#A7C7E7",  # pastel blue
    "Male": "#FFB3C1",    # pastel pink
}
PASTEL_CITY = {
    "Mandalay": "#B8E3C9",   # mint
    "Naypyitaw": "#FFD6A5",  # peach
    "Yangon": "#CDB4DB",     # lavender
}
PASTEL_PRODUCT = {
    "Fashion accessories": "#CDB4DB",
    "Food and beverages": "#FFD6A5",
    "Electronic accessories": "#B8E3C9",
    "Sports and travel": "#A7C7E7",
    "Home and lifestyle": "#FFB3C1",
    "Health and beauty": "#FFF1A8",
}
COLORWAY_PASTEL = ["#A7C7E7", "#FFB3C1", "#B8E3C9", "#FFD6A5", "#CDB4DB", "#FFF1A8"]


def fmt_compact(x: float) -> str:
    x = float(x)
    if abs(x) >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"{x/1_000:.0f}k"
    return f"{x:,.0f}".replace(",", " ")


def style_fig(fig):
    """Global aesthetic for all charts (soft grid, transparent paper)."""
    fig.update_layout(
        colorway=COLORWAY_PASTEL,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)")
    return fig


def kpi_card(title: str, value: str, subtitle: str, icon_class: str, tone: str):
    return html.Div(
        [
            html.Div(
                [
                    html.Div(title, className="kpi-title"),
                    html.Div(value, className="kpi-value"),
                    html.Div(subtitle, className="kpi-subtitle"),
                ],
                className="kpi-text",
            ),
            html.Div(html.I(className=icon_class), className=f"kpi-icon {tone}"),
        ],
        className="kpi-card",
    )


def empty_fig(title: str):
    fig = px.line(title=title)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
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
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    title="Supermarket Sales"
)
server = app.server  # for Render / gunicorn

app.layout = dbc.Container(
    [
        # ---------- TOPBAR ----------
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div("Supermarket Sales", className="app-title"),
                        html.Div("Dashboard interactif (Sexe + Ville)", className="app-subtitle"),
                    ],
                    md=5,
                ),

                dbc.Col(
                    [
                        html.Div("Ville", className="filter-label"),
                        dcc.Dropdown(
                            id="dd_city",
                            options=[{"label": c, "value": c} for c in cities],
                            value=cities,       # default: all
                            multi=True,
                            clearable=False,
                            className="dd",
                            placeholder="Ville",
                        ),
                    ],
                    md=4,
                ),

                dbc.Col(
                    [
                        html.Div("Sexe", className="filter-label"),
                        dcc.Dropdown(
                            id="dd_gender",
                            options=[{"label": g, "value": g} for g in genders],
                            value=genders,      # default: all
                            multi=True,
                            clearable=False,
                            className="dd",
                            placeholder="Sexe",
                        ),
                    ],
                    md=3,
                ),
            ],
            className="topbar g-2",
        ),

        # ---------- INFO PILL (useful + dynamic) ----------
        dbc.Row(
            dbc.Col(html.Div(id="info_pill", className="info-pill")),
            className="mt-2"
        ),

        # ---------- KPI ROW ----------
        dbc.Row(
            [
                dbc.Col(html.Div(id="kpi_total"), md=6),
                dbc.Col(html.Div(id="kpi_rating"), md=6),
            ],
            className="g-2 mt-2",
        ),

        # ---------- CHARTS (2 columns) ----------
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Div("Nombre d'achats par ville et sexe", className="panel-title"),
                            dcc.Loading(
                                dcc.Graph(id="fig_bar", config={"displayModeBar": False}),
                                type="dot",
                            ),
                        ],
                        className="panel-card",
                    ),
                    md=6,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Div("Répartition des catégories (Product line)", className="panel-title"),
                            dcc.Loading(
                                dcc.Graph(id="fig_pie", config={"displayModeBar": False}),
                                type="dot",
                            ),
                        ],
                        className="panel-card",
                    ),
                    md=6,
                ),
            ],
            className="g-2 mt-2",
        ),

        # ---------- CHART (full width) ----------
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.Div("Évolution hebdomadaire du montant total (par ville)", className="panel-title"),
                        dcc.Loading(
                            dcc.Graph(id="fig_week", config={"displayModeBar": False}),
                            type="dot",
                        ),
                    ],
                    className="panel-card",
                ),
                md=12,
            ),
            className="g-2 mt-2 mb-3",
        ),
    ],
    fluid=True,
    className="page",
)


# ============================================================
# 4) CALLBACK (everything updates with Sexe + Ville)
# ============================================================
@app.callback(
    Output("info_pill", "children"),
    Output("kpi_total", "children"),
    Output("kpi_rating", "children"),
    Output("fig_bar", "figure"),
    Output("fig_pie", "figure"),
    Output("fig_week", "figure"),
    Input("dd_city", "value"),
    Input("dd_gender", "value"),
)
def update(city_values, gender_values):
    # If user clears all, fallback to "all" (keeps dashboard usable)
    if not city_values:
        city_values = cities
    if not gender_values:
        gender_values = genders

    dff = df[df["City"].isin(city_values) & df["Gender"].isin(gender_values)].copy()

    if dff.empty:
        info = "0 ventes • filtre trop restrictif"
        return (
            info,
            kpi_card("Montant total des achats", "0", "Somme de Total", "bi bi-cash-coin", "tone-mint"),
            kpi_card("Évaluation moyenne", "NA", "Moyenne de Rating", "bi bi-star-fill", "tone-lav"),
            empty_fig("Barres"),
            empty_fig("Donut"),
            empty_fig("Semaine"),
        )

    # ---------- INFO pill ----------
    n_invoices = dff["Invoice ID"].nunique()
    date_min = dff["Date"].min().strftime("%Y-%m-%d")
    date_max = dff["Date"].max().strftime("%Y-%m-%d")
    info = f"{n_invoices} achats • {len(city_values)} ville(s) • {len(gender_values)} sexe(s) • {date_min} → {date_max}"

    # ---------- KPIs (2 indicators) ----------
    total_sum = dff["Total"].sum()
    avg_rating = dff["Rating"].mean()

    kpi1 = kpi_card("Montant total des achats", fmt_compact(total_sum), "Somme de Total", "bi bi-cash-coin", "tone-mint")
    kpi2 = kpi_card("Évaluation moyenne", f"{avg_rating:.2f}", "Moyenne de Rating", "bi bi-star-fill", "tone-peach")

    # ---------- Graph 1 (Bar): nb achats by City + Gender ----------
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
        text="Nb_achats",
        category_orders={"City": city_order},
        color_discrete_map=PASTEL_GENDER,
    )
    fig_bar.update_traces(textposition="outside", cliponaxis=False)
    fig_bar.update_yaxes(title_text="Nombre d’achats")
    fig_bar.update_xaxes(title_text="")
    fig_bar.update_layout(height=360)
    fig_bar = style_fig(fig_bar)

    # ---------- Graph 2 (Pie/Donut): Product line distribution ----------
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
        color="Product line",
        color_discrete_map=PASTEL_PRODUCT,
    )
    fig_pie.update_traces(textinfo="percent", textposition="inside")
    fig_pie.update_layout(height=360, showlegend=True)
    fig_pie = style_fig(fig_pie)

    # ---------- Graph 3 (Line): weekly Total by City ----------
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
        color_discrete_map=PASTEL_CITY,
    )
    fig_week.update_traces(line=dict(width=3), marker=dict(size=7))
    fig_week.update_layout(height=360, hovermode="x unified")
    fig_week.update_yaxes(title_text="Total")
    fig_week.update_xaxes(title_text="Semaine")
    fig_week = style_fig(fig_week)

    return info, kpi1, kpi2, fig_bar, fig_pie, fig_week


# ============================================================
# 5) RUN 
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)