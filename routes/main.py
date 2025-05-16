from flask import Blueprint, render_template, request
import folium
from folium.plugins.treelayercontrol import TreeLayerControl
import pandas as pd
from . import data_cache

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def mapa():
    selected_periodo = request.args.get("periodo")
    df_all = data_cache.df_all
    periodos = sorted(df_all["periodo"].unique())
    if selected_periodo not in periodos:
        selected_periodo = periodos[0]

    # Filtrar carreras por periodo
    df_carr = data_cache.df_carr
    if selected_periodo in ["202410", "202420"]:
        df_carr_filtered = df_carr[df_carr["PERIODO"].isin([selected_periodo, "202400"])]
    else:
        df_carr_filtered = df_carr[df_carr["PERIODO"].isin([selected_periodo, "202520"])]
    uni_to_carr = df_carr_filtered.groupby("UNIVERSIDAD")["CARRERA"].apply(list).to_dict()

    # Parroquias
    gdf_rurales = data_cache.gdf_rurales.copy()
    gdf_rurales["tipo"] = "rural"
    gdf_urbanas = data_cache.gdf_urbanas.copy()
    gdf_urbanas["tipo"] = "urbana"
    gdf_parroquias = pd.concat(
        [gdf_rurales[["nombre", "geometry", "tipo"]],
         gdf_urbanas[["nombre", "geometry", "tipo"]]],
        ignore_index=True
    ).set_crs("EPSG:4326")

    # Mapa base
    m = folium.Map(location=[-0.20, -78.50], zoom_start=11, tiles="cartodbpositron")

    # Parroquias
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

    # Estaciones de buses
    fg_buses = folium.FeatureGroup(name="Estaciones de Buses").add_to(m)
    for _, row in data_cache.gdf_buses.iterrows():
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
        centroide = geom.centroid
        folium.Marker(
            location=[centroide.y, centroide.x],
            icon=folium.Icon(icon="bus", prefix="fa", color="orange"),
            tooltip="Estación de Bus",
        ).add_to(fg_buses)

    # Estaciones de metro
    fg_metro = folium.FeatureGroup(name="Estaciones de Metro").add_to(m)
    for _, row in data_cache.gdf_metro.iterrows():
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
        centroide = geom.centroid
        folium.Marker(
            location=[centroide.y, centroide.x],
            icon=folium.Icon(icon="subway", prefix="fa", color="purple"),
            tooltip=nombre_estacion,
        ).add_to(fg_metro)

    # Paradas de buses (simplificadas en carga)
    fg_paradas = folium.FeatureGroup(name="Paradas de Buses").add_to(m)
    for _, row in data_cache.gdf_paradas.iterrows():
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

    # Universidades
    df_uni = data_cache.df_uni
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
                    color=("red" if uni.upper() == "UNIVERSIDAD DE LAS AMERICAS" else "blue"),
                    icon="university",
                    prefix="fa",
                ),
                careers=uni_to_carr.get(uni, []),
            ).add_to(fg)

    # Tree Layer
    TreeLayerControl(
        overlay_tree=[
            {"label": "Parroquias", "layer": fg_parroquias},
            {
                "label": "Universidades",
                "children": [
                    {"label": "Públicas", "layer": grupo_uni_fin["PUBLICA"]},
                    {"label": "Privadas", "layer": grupo_uni_fin["PRIVADA"]},
                ],
            },
            {
                "label": "Transporte Público",
                "children": [
                    {"label": "Estaciones de Buses", "layer": fg_buses},
                    {"label": "Estaciones de Metro", "layer": fg_metro},
                    {"label": "Paradas de Buses", "layer": fg_paradas},
                ],
            },
        ]
    ).add_to(m)

    # Facultades por nivel
    facultades_por_nivel = {}
    for _, r in df_carr_filtered.iterrows():
        nivel = r["NIVEL"].strip().upper()
        facultad = r["FACULTAD"].strip()
        carrera = r["CARRERA"].strip()
        if facultad.upper() == "SIN REGISTRO":
            continue
        facultades_por_nivel.setdefault(nivel, {}).setdefault(facultad, set()).add(carrera)
    for nivel in facultades_por_nivel:
        for fac in facultades_por_nivel[nivel]:
            facultades_por_nivel[nivel][fac] = sorted(facultades_por_nivel[nivel][fac])

    return render_template(
        "index.html",
        mapa=m.get_root().render(),
        map_name=m.get_name(),
        periodos=periodos,
        selected_periodo=selected_periodo,
        facultades=facultades_por_nivel,
    )
