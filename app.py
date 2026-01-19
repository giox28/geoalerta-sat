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

# --- 1. MOTOR DE CÁLCULO ---
@st.cache_data(ttl=3600)
def obtener_datos(lat, lon):
    # Configuración del cliente con caché
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["precipitation", "soil_moisture_0_to_1cm"],
        "timezone": "auto", "past_days": 3, "forecast_days": 2
    }
    
    # Ingesta
    try:
        response = openmeteo.weather_api(url, params=params)[0]
        hourly = response.Hourly()
        
        # --- CORRECCIÓN PANDAS 2.0 (Método Robusto) ---
        # 1. Obtenemos inicio, fin e intervalo como números simples
        start = hourly.Time()
        end = hourly.TimeEnd()
        interval = hourly.Interval()
        
        # 2. Generamos rango de enteros (segundos Unix)
        #    Usamos range() nativo de Python que es infalible
        unix_seconds = range(start, end, interval)
        
        # 3. Construimos el DataFrame
        df = pd.DataFrame({
            "date": pd.to_datetime(unix_seconds, unit='s', utc=True),
            "lluvia_mm": hourly.Variables(0).ValuesAsNumpy(),
            "humedad_suelo": hourly.Variables(1).ValuesAsNumpy()
        })
        
        # 4. Ajuste de Zona Horaria (UTC-5 para Colombia)
        #    Usamos el método oficial de Pandas para evitar restas manuales
        df['date'] = df['date'].dt.tz_convert('America/Bogota')
        
        return df
        
    except Exception as e:
        st.error(f"Error técnico al procesar fechas: {e}")
        return pd.DataFrame() # Retorna vacío para no romper la app

def procesar_riesgo(df, susc_estatica):
    if df.empty:
        return 0, "ERROR DATOS", "gray", {}, df
        
    # Cálculo de acumulados
    df['lluvia_3d'] = df['lluvia_mm'].rolling(window=72).sum()
    
    # Lógica de Semáforo
    ultimo = df.iloc[-1]
    lluvia_acum = ultimo['lluvia_3d']
    humedad = ultimo['humedad_suelo']
    
    nivel = 0
    mensaje = "NORMAL"
    color = "green"
    
    # Matriz de Decisión Climática
    amenaza_clima = 0
    if (lluvia_acum > 60) or (humedad > 0.4 and lluvia_acum > 20): amenaza_clima = 3
    elif lluvia_acum > 40: amenaza_clima = 2
    elif lluvia_acum > 15: amenaza_clima = 1
    
    # Cruce con Susceptibilidad
    if susc_estatica > 0.8:
        if amenaza_clima >= 2: nivel, mensaje, color = 3, "🔴 ALARMA ROJA", "#FF0000"
        elif amenaza_clima == 1: nivel, mensaje, color = 2, "🟠 ALERTA NARANJA", "#FFA500"
        elif amenaza_clima == 0 and lluvia_acum > 5: nivel, mensaje, color = 1, "🟡 PREVENTIVA", "#FFD700"
    
    return nivel, mensaje, color, ultimo, df

# --- 2. INTERFAZ GRÁFICA ---

# Sidebar
with st.sidebar:
    st.title("⚙️ Configuración")
    lat_input = st.number_input("Latitud", value=7.1193, format="%.4f")
    lon_input = st.number_input("Longitud", value=-73.1227, format="%.4f")
    susc_input = st.slider("Susceptibilidad (Mapa GEE)", 0.0, 1.0, 0.91)
    
    st.info("""
    **Leyenda:**
    🟢 Normal | 🟡 Preventiva
    🟠 Alerta | 🔴 Alarma
    """)
    
    if st.button("🔄 Actualizar"):
        st.cache_data.clear()

# Panel Principal
st.title("🏔️ GeoAlerta SAT: Tablero de Control")
st.markdown(f"**Monitoreo en Tiempo Real:** Santander, Colombia")

df_raw = obtener_datos(lat_input, lon_input)

if not df_raw.empty:
    nivel, msg, color, data_now, df_proc = procesar_riesgo(df_raw, susc_input)

    # KPI ROW
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Nivel de Alerta", f"Nivel {nivel}", msg, delta_color="off")
    kpi2.metric("Lluvia 72h", f"{data_now['lluvia_3d']:.1f} mm", "Umbral: 15mm")
    kpi3.metric("Humedad Suelo", f"{data_now['humedad_suelo']:.2f} m³/m³", "Saturación")
    kpi4.metric("Susceptibilidad", f"{susc_input:.2f}", "Alta")
    
    # Color del Estado
    st.markdown(f"""
    <div style="background-color:{color}; padding:10px; border-radius:5px; text-align:center; color:white; font-weight:bold;">
        ESTADO ACTUAL: {msg}
    </div>
    """, unsafe_allow_html=True)

    # GRÁFICO
    st.divider()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_proc['date'], y=df_proc['lluvia_mm'], name='Lluvia (mm)', marker_color='blue', opacity=0.6))
    fig.add_trace(go.Scatter(x=df_proc['date'], y=df_proc['humedad_suelo'], name='Humedad', yaxis='y2', line=dict(color='brown', width=3)))
    
    fig.update_layout(
        title="Dinámica Hidrometeorológica (Pasado + Pronóstico)",
        xaxis_title="Hora Local",
        yaxis=dict(title="Lluvia (mm)"),
        yaxis2=dict(title="Humedad (m3/m3)", overlaying='y', side='right', range=[0, 0.6]),
        height=400,
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    # MAPA
    col_map, col_info = st.columns([2, 1])
    with col_map:
        st.subheader("📍 Ubicación")
        m = folium.Map(location=[lat_input, lon_input], zoom_start=13)
        folium.CircleMarker(
            [lat_input, lon_input], radius=25, color=color, fill=True, fill_color=color, fill_opacity=0.6
        ).add_to(m)
        st_folium(m, height=300, use_container_width=True)
    
    with col_info:
        st.subheader("📋 Acciones")
        if nivel == 0: st.success("✅ Sin riesgo inminente.")
        elif nivel == 1: st.warning("👁️ Realizar inspección visual.")
        elif nivel >= 2: st.error("⚠️ Activar comité de emergencias.")

else:
    st.warning("Esperando conexión con satélites...")
