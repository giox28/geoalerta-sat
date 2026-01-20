import streamlit as st
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="GeoAlerta Antioquia", page_icon="🏔️", layout="wide")

# URL RAW del CSV en tu repositorio (Para que Streamlit lo lea)
# ¡CAMBIA 'TU_USUARIO' POR TU NOMBRE DE GITHUB! 👇
URL_PUNTOS = "https://raw.githubusercontent.com/giox28/geoalerta-sat/main/puntos_monitoreo.csv"

# --- 1. MOTOR DE DATOS ---
@st.cache_data(ttl=3600)
def cargar_puntos():
    try:
        # Leemos el CSV directamente desde GitHub
        df = pd.read_csv(URL_PUNTOS)
        return df
    except Exception as e:
        st.error(f"Error cargando puntos de monitoreo: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def obtener_clima_regional(lat_centro, lon_centro):
    # Consultamos el clima en el centro de la zona para referencia
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat_centro, "longitude": lon_centro,
        "hourly": ["precipitation", "soil_moisture_0_to_1cm"],
        "timezone": "auto", "past_days": 3, "forecast_days": 2
    }
    
    response = openmeteo.weather_api(url, params=params)[0]
    hourly = response.Hourly()
    
    # Método robusto de fechas
    unix_seconds = range(hourly.Time(), hourly.TimeEnd(), hourly.Interval())
    df = pd.DataFrame({
        "date": pd.to_datetime(unix_seconds, unit='s', utc=True),
        "lluvia_mm": hourly.Variables(0).ValuesAsNumpy(),
        "humedad_suelo": hourly.Variables(1).ValuesAsNumpy()
    })
    df['date'] = df['date'].dt.tz_convert('America/Bogota')
    return df

# --- 2. INTERFAZ ---
st.title("🏔️ SAT Antioquia: Monitoreo de Deslizamientos AI")
st.markdown("**Estado del Sistema:** 🟢 Operativo | **Zona:** Antioquia, Colombia")

# Cargamos los puntos
df_puntos = cargar_puntos()

if not df_puntos.empty:
    # Calculamos centro del mapa
    lat_mean = df_puntos['lat'].mean()
    lon_mean = df_puntos['lon'].mean()
    
    # Obtenemos clima regional
    df_clima = obtener_clima_regional(lat_mean, lon_mean)
    
    # Métricas Regionales
    ultimo = df_clima.iloc[-1]
    lluvia_72h = df_clima['lluvia_mm'].rolling(72).sum().iloc[-1]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Puntos Críticos Vigilados", f"{len(df_puntos)}", "Red Neural Activa")
    col2.metric("Lluvia Regional (72h)", f"{lluvia_72h:.1f} mm", "Umbral: 40mm")
    col3.metric("Humedad Suelo", f"{ultimo['humedad_suelo']:.2f}", "Saturación")

    # --- MAPA DE RIESGO ---
    st.subheader("📍 Mapa de Amenaza en Tiempo Real")
    
    m = folium.Map(location=[lat_mean, lon_mean], zoom_start=9)
    
    # Pintamos los puntos del modelo
    # Color según susceptibilidad estática (del modelo)
    for _, row in df_puntos.iterrows():
        susc = row['susc_modelada']
        color = "red" if susc > 0.8 else "orange"
        
        folium.CircleMarker(
            [row['lat'], row['lon']],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=f"Riesgo Modelo: {susc:.2f}"
        ).add_to(m)
    
    st_folium(m, height=450, use_container_width=True)
    
    # --- GRÁFICA ---
    st.subheader("🌧️ Tendencia Hidrometeorológica")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_clima['date'], y=df_clima['lluvia_mm'], name='Lluvia'))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠️ No se pudieron cargar los puntos de monitoreo. Revisa la URL del CSV.")
