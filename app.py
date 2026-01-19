import streamlit as st
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="GeoAlerta SAT",
    page_icon="🏔️",
    layout="wide"
)

# --- 1. MOTOR DE CÁLCULO (Reutilizando tu lógica) ---
@st.cache_data(ttl=3600) # Guardamos datos en caché 1 hora para no saturar la API
def obtener_datos(lat, lon):
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["precipitation", "soil_moisture_0_to_1cm"],
        "timezone": "auto", "past_days": 3, "forecast_days": 2
    }
    
    response = openmeteo.weather_api(url, params=params)[0]
    hourly = response.Hourly()
    
    df = pd.DataFrame({
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "lluvia_mm": hourly.Variables(0).ValuesAsNumpy(),
        "humedad_suelo": hourly.Variables(1).ValuesAsNumpy()
    })
    # Ajuste manual de zona horaria simple
    df['date'] = df['date'] - pd.Timedelta(hours=5) 
    return df

def procesar_riesgo(df, susc_estatica):
    # Cálculo de acumulados
    df['lluvia_3d'] = df['lluvia_mm'].rolling(window=72).sum()
    
    # Lógica de Semáforo
    ultimo = df.iloc[-1] # Tiempo real
    lluvia_acum = ultimo['lluvia_3d']
    humedad = ultimo['humedad_suelo']
    
    nivel = 0
    mensaje = "NORMAL"
    color = "green"
    
    # Matriz de Decisión
    amenaza_clima = 0
    if (lluvia_acum > 60) or (humedad > 0.4 and lluvia_acum > 20): amenaza_clima = 3
    elif lluvia_acum > 40: amenaza_clima = 2
    elif lluvia_acum > 15: amenaza_clima = 1
    
    # Cruce con Susceptibilidad
    if susc_estatica > 0.8:
        if amenaza_clima >= 2: nivel, mensaje, color = 3, "🔴 ALARMA ROJA", "red"
        elif amenaza_clima == 1: nivel, mensaje, color = 2, "🟠 ALERTA NARANJA", "orange"
        elif amenaza_clima == 0 and lluvia_acum > 5: nivel, mensaje, color = 1, "🟡 PREVENTIVA", "#FFD700"
    
    return nivel, mensaje, color, ultimo, df

# --- 2. INTERFAZ GRÁFICA (FRONTEND) ---

# Sidebar (Controles)
with st.sidebar:
    st.title("⚙️ Configuración")
    lat_input = st.number_input("Latitud", value=7.1193, format="%.4f")
    lon_input = st.number_input("Longitud", value=-73.1227, format="%.4f")
    susc_input = st.slider("Susceptibilidad del Terreno (Mapa GEE)", 0.0, 1.0, 0.90)
    
    st.info("""
    **Niveles de Alerta:**
    🟢 **0:** Condiciones Estables
    🟡 **1:** Monitoreo Visual
    🟠 **2:** Alistamiento
    🔴 **3:** Evacuación
    """)
    
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()

# Título Principal
st.title("🏔️ GeoAlerta SAT: Tablero de Control")
st.markdown(f"**Monitoreo en Tiempo Real:** Santander, Colombia")

# Ejecución de lógica
try:
    df_raw = obtener_datos(lat_input, lon_input)
    nivel, msg, color, data_now, df_proc = procesar_riesgo(df_raw, susc_input)

    # --- BLOQUE DE KPI (Indicadores Clave) ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Nivel de Alerta", f"Nivel {nivel}", delta=msg, delta_color="inverse")
    with col2:
        st.metric("Lluvia Acumulada (72h)", f"{data_now['lluvia_3d']:.1f} mm", "Umbral: 15mm")
    with col3:
        st.metric("Humedad del Suelo", f"{data_now['humedad_suelo']:.2f} m³/m³", "Saturación")
    with col4:
        st.metric("Susceptibilidad", f"{susc_input:.2f}", "Alta")

    # --- GRÁFICOS INTERACTIVOS (Plotly) ---
    st.divider()
    
    # Gráfico Combinado
    fig = go.Figure()
    
    # Barras de Lluvia
    fig.add_trace(go.Bar(
        x=df_proc['date'], y=df_proc['lluvia_mm'],
        name='Lluvia por Hora', marker_color='blue', opacity=0.6
    ))
    
    # Línea de Humedad
    fig.add_trace(go.Scatter(
        x=df_proc['date'], y=df_proc['humedad_suelo'],
        name='Humedad Suelo', yaxis='y2', line=dict(color='brown', width=3)
    ))
    
    # Layout
    fig.update_layout(
        title="Histórico y Pronóstico (48h)",
        xaxis_title="Fecha / Hora",
        yaxis=dict(title="Lluvia (mm)"),
        yaxis2=dict(title="Humedad (m3/m3)", overlaying='y', side='right', range=[0, 0.6]),
        hovermode="x unified",
        height=400
    )
    
    # Línea de "AHORA"
    fig.add_vline(x=pd.Timestamp.now() - pd.Timedelta(hours=5), line_dash="dash", line_color="red", annotation_text="AHORA")
    
    st.plotly_chart(fig, use_container_width=True)

    # --- MAPA TÁCTICO ---
    st.subheader("📍 Ubicación del Punto de Control")
    
    # Mapa base
    m = folium.Map(location=[lat_input, lon_input], zoom_start=12)
    
    # Círculo de Riesgo (Color dinámico)
    folium.CircleMarker(
        location=[lat_input, lon_input],
        radius=20,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.7,
        popup=f"Nivel de Alerta: {nivel}"
    ).add_to(m)
    
    st_folium(m, height=300, use_container_width=True)

except Exception as e:
    st.error(f"Error de conexión con satélites: {e}")
