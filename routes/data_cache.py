import geopandas as gpd
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

EXCEL_PATH = os.path.join(DATA_DIR, "universidades_colegios.xlsx")
SHEET_UNI = "Universidades"
CSV_EST = os.path.join(DATA_DIR, "ubicacionEstudiantesPeriodo.csv")
GJSON_RURAL = os.path.join(DATA_DIR, "parroquiasRurales.geojson")
GJSON_URB = os.path.join(DATA_DIR, "parroquiasUrbanas.geojson")
CARRERAS_PATH = os.path.join(DATA_DIR, "baseCarreras.xlsx")
GJSON_BUSES = os.path.join(DATA_DIR, "estacionesBuses.geojson")
GJSON_METRO = os.path.join(DATA_DIR, "estacionesMetro.geojson")
GJSON_PARADAS_BUSES = os.path.join(DATA_DIR, "paradasBuses.geojson")

# Cachear al iniciar
df_all = pd.read_csv(CSV_EST, sep=";").rename(columns={"Semestre": "periodo"})
df_all["periodo"] = df_all["periodo"].astype(str)

gdf_rurales = gpd.read_file(GJSON_RURAL).rename(columns={"DPA_DESPAR": "nombre"})
gdf_urbanas = gpd.read_file(GJSON_URB).rename(columns={"dpa_despar": "nombre"})
gdf_buses = gpd.read_file(GJSON_BUSES).to_crs("EPSG:4326")
gdf_metro = gpd.read_file(GJSON_METRO).to_crs("EPSG:4326")
gdf_paradas = gpd.read_file(GJSON_PARADAS_BUSES).to_crs("EPSG:4326")

df_uni = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_UNI).rename(columns=lambda c: c.strip())
df_uni["UNIVERSIDAD"] = df_uni["UNIVERSIDAD"].str.strip()
df_carr = pd.read_excel(CARRERAS_PATH)
df_carr["PERIODO"] = df_carr["PERIODO"].astype(str)
