# ocean_surface.py

import dash
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

import geopandas as gpd
from shapely.geometry import Point
import numpy as np
import pandas as pd

# Inicialização do app (página única)
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # Para compatibilidade com implantação

# ========================
# Funções auxiliares
# ========================

def carregar_fronteiras_mundiais():
    url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json"
    mundo = gpd.read_file(url)
    return mundo

def verificar_ponto_em_terra(lat, lon, mundo):
    ponto = Point(lon, lat)
    return "Terra" if any(mundo.contains(ponto)) else "Água"

def gerar_coordenadas_aleatorias(n):
    """Gera coordenadas aleatórias distribuídas globalmente."""
    senos_latitudes = np.random.uniform(-1, 1, n)
    latitudes = np.degrees(np.arcsin(senos_latitudes))
    longitudes = np.random.uniform(-180, 180, n)
    return latitudes, longitudes

# Carrega dados de fronteiras (GeoJSON)
mundo = carregar_fronteiras_mundiais()

# Componente Store para armazenar dados no client-side
store_component = dcc.Store(id='dados-pontos', storage_type='memory')

# ========================
# Callbacks
# ========================

@app.callback(
    Output('dados-pontos', 'data'),
    Input('gerar-pontos', 'n_clicks'),
    Input('remover-pontos', 'n_clicks'),
    State('num-coords', 'value'),
    State('dados-pontos', 'data'),
    prevent_initial_call=True
)
def atualizar_pontos(n_clicks_gerar, n_clicks_remover, num_coords, dados_existentes):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'gerar-pontos':
        latitudes, longitudes = gerar_coordenadas_aleatorias(int(num_coords))
        resultados = []
        for lat, lon in zip(latitudes, longitudes):
            localizacao = verificar_ponto_em_terra(lat, lon, mundo)
            resultados.append({"Latitude": round(lat, 4), "Longitude": round(lon, 4), "Localização": localizacao})

        df_novos = pd.DataFrame(resultados)
        if dados_existentes:
            df_existentes = pd.DataFrame(dados_existentes)
            df_atualizado = pd.concat([df_existentes, df_novos], ignore_index=True)
        else:
            df_atualizado = df_novos

        return df_atualizado.to_dict('records')

    elif button_id == 'remover-pontos':
        return []

    else:
        raise dash.exceptions.PreventUpdate

@app.callback(
    Output('globo-terrestre', 'figure'),
    Input('dados-pontos', 'data'),
    Input({'type': 'table-row', 'index': dash.ALL}, 'n_clicks')
)
def atualizar_globo(dados, row_clicks):
    rot_lon, rot_lat = 0, 0

    if dados and any(row_clicks or []):
        ctx = dash.callback_context
        if ctx.triggered:
            triggered_id = ctx.triggered[0]['prop_id']
            if 'table-row' in triggered_id:
                row_index = int(triggered_id.split('.')[0].split('index":')[1].split('}')[0][0])
                df = pd.DataFrame(dados)
                rot_lat = df.iloc[row_index]['Latitude']
                rot_lon = df.iloc[row_index]['Longitude']

    fig = go.Figure()
    fig.add_trace(
        go.Scattergeo(
            lon=[],
            lat=[],
            mode="markers",
            marker=dict(size=2),
            showlegend=False,
        )
    )
    if dados:
        df = pd.DataFrame(dados)
        fig.add_trace(
            go.Scattergeo(
                lon=df["Longitude"],
                lat=df["Latitude"],
                mode="markers",
                marker=dict(
                    size=10,
                    color=["red" if loc == "Terra" else "green" for loc in df["Localização"]],
                    symbol="circle",
                    line=dict(width=1),
                    opacity=0.8
                ),
                hoverinfo="text",
                text=[
                    f"Lat: {lat}<br>Lon: {lon}<br>Localização: {loc}"
                    for lat, lon, loc in zip(df["Latitude"], df["Longitude"], df["Localização"])
                ],
                name="Pontos Aleatórios",
            )
        )

    fig.update_geos(
        projection_type="orthographic",
        showcountries=True,
        showcoastlines=True,
        coastlinecolor="Gray",
        landcolor="rgb(217, 217, 217)",
        oceancolor="rgb(173, 216, 230)",
        showocean=True,
        projection_rotation=dict(lon=rot_lon, lat=rot_lat),
        center=dict(lon=rot_lon, lat=rot_lat)
    )
    fig.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        height=600,
    )
    return fig

@app.callback(
    Output('resumo-dados', 'children'),
    Input('dados-pontos', 'data')
)
def exibir_resumo(dados):
    if dados:
        df = pd.DataFrame(dados)
        total = len(df)
        terra = df['Localização'].value_counts().get("Terra", 0)
        agua = df['Localização'].value_counts().get("Água", 0)
        terra_pct = (terra / total) * 100
        agua_pct = (agua / total) * 100

        return dbc.Card([
            dbc.CardHeader("Resumo das Coordenadas Geradas", className="card-header-dark"),
            dbc.CardBody([
                dcc.Markdown(f"**Total de Pontos:** {total}", className="text-white"),
                dcc.Markdown(f"**Em Terra:** {terra} ({terra_pct:.2f}%)", className="text-white"),
                dcc.Markdown(f"**Em Água:** {agua} ({agua_pct:.2f}%)", className="text-white"),
            ])
        ], className="mb-4 card-dark-custom")
    return None

@app.callback(
    Output('tabela-coordenadas', 'children'),
    Input('dados-pontos', 'data')
)
def exibir_tabela(dados):
    if dados:
        df = pd.DataFrame(dados).rename_axis('Ponto').reset_index()
        df['Ponto'] = df['Ponto'] + 1

        rows = []
        for i, row in df.iterrows():
            rows.append(html.Tr(
                id={'type': 'table-row', 'index': i},
                children=[
                    html.Td(row['Ponto']),
                    html.Td(row['Latitude']),
                    html.Td(row['Longitude']),
                    html.Td(row['Localização'])
                ]
            ))

        table = dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Ponto"),
                    html.Th("Latitude"),
                    html.Th("Longitude"),
                    html.Th("Localização")
                ])),
                html.Tbody(rows)
            ],
            striped=True, bordered=True, hover=True, className="table-dark"
        )

        scrollable_table = html.Div(table, className="scrollable-table")

        return dbc.Card([
            dbc.CardHeader("Coordenadas", className="card-header-dark"),
            dbc.CardBody(scrollable_table)
        ], className="mb-4 card-dark-custom")
    return None

@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("download-button", "n_clicks"),
    State('dados-pontos', 'data'),
    prevent_initial_call=True
)
def baixar_csv(n_clicks, dados):
    if n_clicks and dados:
        df = pd.DataFrame(dados)
        return dcc.send_data_frame(df.to_csv, "coordenadas_aleatorias.csv", index=False)
    return dash.no_update

@app.callback(
    Output('download-button', 'disabled'),
    Input('dados-pontos', 'data')
)
def toggle_download_button(dados):
    return not bool(dados)

# ========================
# Layout (página única)
# ========================
app.layout = dbc.Container([
    # 1) Linha do topo (com a imagem e o título lado a lado)
    dbc.Row([
        dbc.Col([
            html.Img(
                src="/assets/ocean_surface_card.png",
                style={
                    "maxWidth": "70px",  # Ajuste o tamanho da imagem conforme desejar
                    "height": "auto"
                }
            )
        ], width="auto"),
        dbc.Col([
            html.H1("Estimando a Proporção da Superfície Oceânica", className="heading-page")
        ], width=True)
    ], className="bg-header-page align-items-center"),

    # 2) Linha principal com barra lateral e conteúdo
    dbc.Row([
        # Barra lateral
        dbc.Col([
            dbc.Row([
                dbc.Form([
                    dbc.Row([
                        dbc.Col(
                            html.A(
                                "Teoria",
                                href="https://fcopf.github.io/MEAD/conteudo/intro_bayes/intro-bayes-modelo-bayesiano.html",
                                className="btn btn-link text-white",
                                target="_blank"
                            ),
                            width="auto"
                        ),
                        dbc.Col(
                            html.A(
                                "Inferência Bayesiana",
                                href="https://fcopf-binomial-bayesiana.share.connect.posit.cloud/",
                                className="btn btn-link text-white",
                                target="_blank"
                            ),
                            width="auto",
                            className="mb-4 ms-3"
                        )
                    ])
                ]),
            ]),            
            dbc.Row([
                dbc.Col([
                    dbc.Label("Número de Coordenadas", className="text-white"),
                    dbc.Input(
                        id='num-coords',
                        type='number',
                        min=1,
                        max=1000,
                        step=1,
                        placeholder='Selecione o número entre 1 e 1000.',
                        className="mb-4 dark-input",
                    ),
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "Gerar Pontos Aleatórios",
                        id='gerar-pontos',
                        color='primary',
                        className="mb-4",
                        n_clicks=0
                    ),
                ], width=12),
                dbc.Col([
                    dbc.Button(
                        "Remover Pontos",
                        id='remover-pontos',
                        color='danger',
                        className="mb-4",
                        n_clicks=0
                    ),
                ], width=12),
                dbc.Col([
                    dbc.Button(
                        "Baixar como CSV",
                        id='download-button',
                        color='secondary',
                        className="mb-4",
                        n_clicks=0
                    ),
                ], width=12),
            ]),
            dbc.Row([
                store_component,
                dcc.Download(id="download-dataframe-csv"),
            ]),
        ], width=2, className="sidebar-custom"),

        # Conteúdo principal
        dbc.Col([
            dbc.Row([
                dbc.Col([], width=1),  # Espaçamento à esquerda

                dbc.Col([
                    dcc.Graph(id='globo-terrestre', className="mt-5")
                ], width=6),

                dbc.Col([], width=1),  # Espaçamento à direita

                dbc.Col([
                    html.Div(id='resumo-dados', className="mt-5"),
                    html.Div(id='tabela-coordenadas')
                ], width=4),
            ]),
        ], width=10),
    ]),
], fluid=True, className="bg-black")


# ========================
# Execução do servidor
# ========================
if __name__ == '__main__':
    app.run_server(debug=False, host="0.0.0.0", port=8050)
