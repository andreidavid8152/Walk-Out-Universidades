from flask import Blueprint, render_template, request
import geopandas as gpd
import pandas as pd
import folium
from folium.plugins.treelayercontrol import TreeLayerControl
from shapely.geometry import box
import random
import os
import json

main_bp = Blueprint("main", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

EXCEL_PATH = os.path.join(DATA_DIR, "universidades_colegios.xlsx")
SHEET_UNI = "Universidades"
CSV_EST = os.path.join(DATA_DIR, "ubicacionEstudiantesPeriodo.csv")
GJSON_RURAL = os.path.join(DATA_DIR, "parroquiasRurales.geojson")
GJSON_URB = os.path.join(DATA_DIR, "parroquiasUrbanas.geojson")
GJSON_BUSES = os.path.join(DATA_DIR, "estacionesBuses.geojson")
GJSON_METRO = os.path.join(DATA_DIR, "estacionesMetro.geojson")
GJSON_PARADAS_BUSES = os.path.join(DATA_DIR, "paradasBuses.geojson")
GJSON_ALIMENTADORES = os.path.join(DATA_DIR, "alimentadores.geojson")

# Cargar nombres de alimentadores desde JSON
with open(os.path.join(DATA_DIR, "idAlimentadores.json"), encoding="utf-8") as f:
    alimentador_nombre_map = {
        item["code"]: item["name"] for item in json.load(f)["codedValues"]
    }

@main_bp.route("/")
def mapa():
    # 🎯 Incluye solo lógica de parroquias + universidades + filtros

    # Periodo
    selected_periodo = request.args.get("periodo")
    df_all = pd.read_csv(CSV_EST, sep=";").rename(columns={"Semestre": "periodo"})
    df_all["periodo"] = df_all["periodo"].astype(str)
    periodos = sorted(df_all["periodo"].unique())
    if selected_periodo not in periodos:
        selected_periodo = periodos[0]

    # Alimentadores
    gdf_alimentadores = gpd.read_file(GJSON_ALIMENTADORES).to_crs("EPSG:4326")

    # ============================================================
    # 🔹 1. CÁLCULO DE GRILLA PARA ALIMENTADORES
    # ============================================================

    gdf_alimentadores_m = gdf_alimentadores.to_crs(epsg=32717)
    gdf_alimentadores_m["area_m2"] = gdf_alimentadores_m.geometry.area
    mediana_area_alim = gdf_alimentadores_m["area_m2"].median()
    lado_celda_alim = mediana_area_alim**0.5  # lado en metros

    minx_a, miny_a, maxx_a, maxy_a = gdf_alimentadores_m.total_bounds
    grid_cells_a = []
    x = minx_a
    while x < maxx_a:
        y = miny_a
        while y < maxy_a:
            grid_cells_a.append(box(x, y, x + lado_celda_alim, y + lado_celda_alim))
            y += lado_celda_alim
        x += lado_celda_alim

    gdf_grilla_alimentadores = gpd.GeoDataFrame(
        geometry=grid_cells_a, crs="EPSG:32717"
    ).to_crs("EPSG:4326")

    # Intersección y centroides alimentadores
    gdf_grid_alim = gpd.overlay(
        gdf_grilla_alimentadores[["geometry"]],
        gdf_alimentadores[["geometry", "alimentadorid"]],
        how="intersection",
    ).explode(ignore_index=True)

    gdf_grid_alim = gdf_grid_alim[gdf_grid_alim.geometry.geom_type == "Polygon"]
    gdf_grid_alim["area_m2"] = gdf_grid_alim.to_crs("EPSG:32717").area
    gdf_grid_alim = gdf_grid_alim[gdf_grid_alim["area_m2"] > 25]

    gdf_grid_alim_proj = gdf_grid_alim.to_crs("EPSG:32717")
    gdf_grid_alim["centroide"] = gdf_grid_alim_proj.representative_point().to_crs(
        "EPSG:4326"
    )
    gdf_grid_alim = gdf_grid_alim[
        gdf_grid_alim.apply(lambda r: r.geometry.contains(r["centroide"]), axis=1)
    ]

    # Parroquias
    gdf_rurales = gpd.read_file(GJSON_RURAL).rename(columns={"DPA_DESPAR": "nombre"})
    gdf_urbanas = gpd.read_file(GJSON_URB).rename(columns={"dpa_despar": "nombre"})
    gdf_buses = gpd.read_file(GJSON_BUSES).to_crs("EPSG:4326")
    gdf_metro = gpd.read_file(GJSON_METRO).to_crs("EPSG:4326")

    gdf_rurales["tipo"] = "rural"
    gdf_urbanas["tipo"] = "urbana"
    gdf_parroquias = pd.concat(
        [
            gdf_rurales[["nombre", "geometry", "tipo"]],
            gdf_urbanas[["nombre", "geometry", "tipo"]],
        ],
        ignore_index=True,
    ).set_crs("EPSG:4326")

    # ============================================================
    # 🔹 2. CÁLCULO DE GRILLA PARA PARROQUIAS
    # ============================================================

    gdf_parroquias_m = gdf_parroquias.to_crs(epsg=32717)
    gdf_parroquias_m["area_m2"] = gdf_parroquias_m.geometry.area
    mediana_area_parr = gdf_parroquias_m["area_m2"].median()
    lado_celda_parr = mediana_area_parr**0.5  # lado en metros

    minx_p, miny_p, maxx_p, maxy_p = gdf_parroquias_m.total_bounds
    grid_cells_p = []
    x = minx_p
    while x < maxx_p:
        y = miny_p
        while y < maxy_p:
            grid_cells_p.append(box(x, y, x + lado_celda_parr, y + lado_celda_parr))
            y += lado_celda_parr
        x += lado_celda_parr

    gdf_grilla = gpd.GeoDataFrame(geometry=grid_cells_p, crs="EPSG:32717").to_crs(
        "EPSG:4326"
    )

    # Intersección celda × parroquia
    gdf_grid_parr = gpd.overlay(
        gdf_grilla[["geometry"]],
        gdf_parroquias[["geometry", "nombre"]],
        how="intersection",
    ).explode(ignore_index=True)

    gdf_grid_parr_proj = gdf_grid_parr.to_crs("EPSG:32717")
    gdf_grid_parr["centroide"] = gdf_grid_parr_proj.centroid.to_crs("EPSG:4326")

    # Mapa
    m = folium.Map(location=[-0.20, -78.50], zoom_start=11, tiles="cartodbpositron")
    fg_parroquias = folium.FeatureGroup(name="Parroquias").add_to(m)

    for _, row in gdf_parroquias.iterrows():
        folium.GeoJson(
            {
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": {"nombre": row["nombre"]},
            },
            style_function=lambda _: {
                "fillColor": "white",
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.01,
            },
            tooltip=folium.GeoJsonTooltip(fields=["nombre"], aliases=["Parroquia:"]),
        ).add_to(fg_parroquias)

    # Capa de grilla para alimentadores
    fg_grilla_alim = folium.FeatureGroup(name="Grilla Alimentadores", show=False).add_to(m)
    for _, row in gdf_grilla_alimentadores.iterrows():
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _: {
                "fillColor": "none",
                "color": "brown",
                "weight": 0.5,
                "fillOpacity": 0,
            },
        ).add_to(fg_grilla_alim)

    # Capa de centroides para alimentadores
    fg_centroides_alim = folium.FeatureGroup(
        name="Centroides Alimentadores", show=False
    ).add_to(m)
    for _, row in gdf_grid_alim.iterrows():
        c = row["centroide"]
        aid = row["alimentadorid"]
        nombre = alimentador_nombre_map.get(aid, aid)
        folium.CircleMarker(
            location=[c.y, c.x],
            radius=3,
            color="brown",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"Centroide {nombre}",
        ).add_to(fg_centroides_alim)

    # Estaciones buses
    fg_buses = folium.FeatureGroup(name="Estaciones de Buses", show=False).add_to(m)

    for _, row in gdf_buses.iterrows():
        geom = row.geometry
        folium.GeoJson(
            geom.__geo_interface__,
            style_function=lambda _: {
                "fillColor": "orange",
                "color": "orange",
                "weight": 1.5,
                "fillOpacity": 0.4,
            },
            tooltip="Estación de Bus",
        ).add_to(fg_buses)

        # Icono en el centro del polígono
        centroide = geom.centroid
        folium.Marker(
            location=[centroide.y, centroide.x],
            icon=folium.Icon(icon="bus", prefix="fa", color="orange"),
            tooltip="Estación de Bus",
        ).add_to(fg_buses)

    # Estaciones metro
    fg_metro = folium.FeatureGroup(name="Estaciones de Metro", show=False).add_to(m)

    for _, row in gdf_metro.iterrows():
        geom = row.geometry
        nombre_estacion = f"Estación de metro: {row.get('nam', 'Desconocida')}"

        folium.GeoJson(
            geom.__geo_interface__,
            style_function=lambda _: {
                "fillColor": "purple",
                "color": "purple",
                "weight": 1.5,
                "fillOpacity": 0.4,
            },
            tooltip=nombre_estacion,
        ).add_to(fg_metro)

        # Icono centrado
        centroide = geom.centroid
        folium.Marker(
            location=[centroide.y, centroide.x],
            icon=folium.Icon(icon="subway", prefix="fa", color="purple"),
            tooltip=nombre_estacion,
        ).add_to(fg_metro)

    # Paradas de Buses (puntos)
    gdf_paradas = gpd.read_file(GJSON_PARADAS_BUSES).to_crs("EPSG:4326")
    fg_paradas = folium.FeatureGroup(name="Paradas de Buses", show=False).add_to(m)

    for _, row in gdf_paradas.iterrows():
        punto = row.geometry
        folium.CircleMarker(
            location=[punto.y, punto.x],
            radius=4,
            color="darkgreen",
            fill=True,
            fill_color="limegreen",
            fill_opacity=0.8,
            tooltip="Parada de Bus",
        ).add_to(fg_paradas)

    # ALIMENTADORES
    fg_alimentadores_padre = folium.FeatureGroup(name="Zonas de Alimentadores").add_to(m)

    # Colores únicos por nombre
    nombre_ids = [
        alimentador_nombre_map.get(aid, aid) for aid in gdf_alimentadores["alimentadorid"].unique()
    ]
    color_map = {
        name: f"#{random.randint(0, 0xFFFFFF):06x}" for name in nombre_ids
    }

    # Crear subcapas por nombre
    subcapas_alimentadores = {}

    for aid, group in gdf_alimentadores.groupby("alimentadorid"):
        nombre = alimentador_nombre_map.get(aid, aid)  # Usa ID si no hay nombre
        if nombre not in subcapas_alimentadores:
            subcapas_alimentadores[nombre] = folium.FeatureGroup(name=nombre).add_to(fg_alimentadores_padre)

        color = color_map[nombre]
        for _, row in group.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda _, col=color: {
                    "fillColor": col,
                    "color": col,
                    "weight": 1,
                    "fillOpacity": 0.4,
                },
                tooltip=nombre,
            ).add_to(subcapas_alimentadores[nombre])

    # Universidades
    df_uni = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_UNI).rename(
        columns=lambda c: c.strip()
    )
    df_uni["UNIVERSIDAD"] = df_uni["UNIVERSIDAD"].str.strip()

    grupo_uni_fin = {"PUBLICA": [], "PRIVADA": []}
    for tipo in ["PUBLICA", "PRIVADA"]:
        fg = folium.FeatureGroup(name=f"Universidades {tipo.title()}").add_to(m)
        grupo_uni_fin[tipo] = fg
        for _, row in df_uni[df_uni["FINANCIAMIENTO"].str.upper() == tipo].iterrows():
            uni = row["UNIVERSIDAD"]
            folium.Marker(
                location=[row["LATITUD"], row["LONGITUD"]],
                title=uni,
                tooltip=f"{uni} – {row['CAMPUS']}",
                icon=folium.Icon(
                    color=(
                        "red"
                        if uni.upper() == "UNIVERSIDAD DE LAS AMERICAS"
                        else "blue"
                    ),
                    icon="university",
                    prefix="fa",
                ),
                careers=[],
            ).add_to(fg)

    # Capa de grilla
    fg_grilla = folium.FeatureGroup(name="Grilla", show=False).add_to(m)
    for _, row in gdf_grilla.iterrows():
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _: {
                "fillColor": "none",
                "color": "#888",
                "weight": 0.5,
                "fillOpacity": 0,
            },
        ).add_to(fg_grilla)

    # Capa de centroides
    fg_centroides_parr = folium.FeatureGroup(name="Centroides por Intersección", show=False).add_to(m)
    for _, row in gdf_grid_parr.iterrows():
        c = row["centroide"]
        folium.CircleMarker(
            location=[c.y, c.x],
            radius=3,
            color="black",
            fill=True,
            fill_opacity=0.9,
            tooltip="Centroide intersección",
        ).add_to(fg_centroides_parr)

    TreeLayerControl(
        overlay_tree=[
            {
                "label": "Parroquias",
                "layer": fg_parroquias,
            },
            {
                "label": "Universidades",
                "select_all_checkbox": True,
                "children": [
                    {"label": "Públicas", "layer": grupo_uni_fin["PUBLICA"]},
                    {"label": "Privadas", "layer": grupo_uni_fin["PRIVADA"]},
                ],
            },
            {
                "label": "Transporte Público",
                "select_all_checkbox": True,
                "children": [
                    {"label": "Estaciones de Buses", "layer": fg_buses},
                    {"label": "Estaciones de Metro", "layer": fg_metro},
                    {"label": "Paradas de Buses", "layer": fg_paradas},
                ],
            },
            {
                "label": "Grillas",
                "select_all_checkbox": True,
                "children": [
                    {"label": "Grilla Parroquias", "layer": fg_grilla},
                    {"label": "Centroides Parroquias", "layer": fg_centroides_parr},
                    {"label": "Grilla Alimentadores", "layer": fg_grilla_alim},
                    {"label": "Centroides Alimentadores", "layer": fg_centroides_alim},
                ],
            },
            {
                "label": "Alimentadores",
                "select_all_checkbox": True,
                "children": [
                    {"label": nombre, "layer": subcapas_alimentadores[nombre]}
                    for nombre in sorted(subcapas_alimentadores)
                ],
            },
        ]
    ).add_to(m)

    return render_template(
        "index.html",
        mapa=m.get_root().render(),
        map_name=m.get_name(),
        periodos=periodos,
        selected_periodo=selected_periodo,
        ruta_activa="alimentadores"  
    )

