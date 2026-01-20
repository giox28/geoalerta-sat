import streamlit as st
import pandas as pd
import numpy as np
import openmeteo_requests
import requests_cache
from retry_requests import retry
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="GeoAlerta Antioquia", page_icon="🏔️", layout="wide")

# 👇 ¡CAMBIA ESTO POR TU USUARIO REAL DE GITHUB!
URL_PUNTOS = "https://raw.githubusercontent.com/giox28/geoalerta-sat/main/puntos_monitoreo.csv"

# --- 1. CARGA DE PUNTOS ESTRUCTURALES ---
@st.cache_data(ttl=3600)
def cargar_puntos_base():
    try:
        df = pd.read_csv(URL_PUNTOS)
        return df
    except Exception as e:
        st.error(f"Error cargando CSV: {e}")
        return pd.DataFrame()

# --- 2. MOTOR METEOROLÓGICO MULTIPUNTO (El cambio clave) ---
@st.cache_data(ttl=3600)
def obtener_clima_dinamico(df_puntos):
    # Configuración API
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://api.open-meteo.com/v1/forecast"
    
    # Preparamos la petición MASIVA (todos los puntos a la vez)
    params = {
        "latitude": df_puntos['lat'].tolist(),
        "longitude": df_puntos['lon'].tolist(),
        "hourly": ["precipitation", "soil_moisture_0_to_1cm"],
        "timezone": "auto",
        "past_days": 3,
        "forecast_days": 1
    }
    
    try:
        responses = openmeteo.weather_api(url, params=params)
        
        # Diccionario para guardar la historia horaria de CADA punto
        # Clave: índice del punto, Valor: DataFrame histórico
        historial_por_punto = {}
        
        # Listas para actualizar el DataFrame maestro con datos actuales
        lluvias_72h = []
        humedades_hoy = []
        
        for i, response in enumerate(responses):
            hourly = response.Hourly()
            
            # Construimos la serie de tiempo para este punto
            times = pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )
            
            # Datos brutos
            rain_array = hourly.Variables(0).ValuesAsNumpy()
            soil_array = hourly.Variables(1).ValuesAsNumpy()
            
            # Guardamos historial (para graficar luego)
            historial_por_punto[i] = pd.DataFrame({
                "date": times,
                "lluvia_mm": rain_array,
                "humedad_suelo": soil_array
            })
            
            # Guardamos resumen (para el mapa)
            # Lluvia acumulada 72h (aprox los ultimos 72 registros antes del futuro)
            # Buscamos el índice "ahora"
            now_idx = len(times) - 24 # Aprox, restando el día de pronóstico
            if now_idx < 0: now_idx = len(times)-1
            
            # Calculamos acumulado real (todo el array hasta ahora)
            acumulado = float(np.sum(rain_array[:now_idx][-72:])) # Últimas 72h reales
            ultimo_suelo = float(soil_array[now_idx])
            
            lluvias_72h.append(acumulado)
            humedades_hoy.append(ultimo_suelo)
            
        # Añadimos los datos frescos al DataFrame original
        df_puntos['lluvia_72h'] = lluvias_72h
        df_puntos['humedad_suelo'] = humedades_hoy
        
        return df_puntos, historial_por_punto
        
    except Exception as e:
        st.error(f"Error conectando con satélites: {e}")
        return df_puntos, {}

# --- 3. INTERFAZ ---
st.title("🏔️ SAT Antioquia: Monitoreo Dinámico")

# Carga inicial
df_base = cargar_puntos_base()

if not df_base.empty:
    # Obtenemos clima DE TODOS los puntos
    with st.spinner("🛰️ Conectando con satélites para 58 puntos..."):
        df_completo, dict_historia = obtener_clima_dinamico(df_base)
    
    # --- LÓGICA DE SELECCIÓN ---
    punto_seleccionado_idx = None # Por defecto nadie
    
    # Contenedor superior (Mapa y Métricas)
    col_mapa, col_info = st.columns([2, 1])
    
    with col_mapa:
        st.subheader("📍 Mapa Interactivo (Haz clic en un punto)")
        
        # Centro del mapa
        lat_center = df_completo['lat'].mean()
        lon_center = df_completo['lon'].mean()
        
        m = folium.Map(location=[lat_center, lon_center], zoom_start=9)
        
        # Pintamos puntos
        for idx, row in df_completo.iterrows():
            # Color dinámico según riesgo combinado
            color = "#00FF00" # Verde
            if row['lluvia_72h'] > 40: color = "orange"
            if row['lluvia_72h'] > 60 and row['humedad_suelo'] > 0.4: color = "red"
            
            folium.CircleMarker(
                [row['lat'], row['lon']],
                radius=6,
                color=color,
                fill=True,
                fill_opacity=0.8,
                tooltip=f"Punto {idx}: {row['lluvia_72h']:.1f}mm",
                popup=f"ID: {idx}"
            ).add_to(m)
        
        # ⭐ EL TRUCO: st_folium devuelve el objeto clicado
        mapa_output = st_folium(m, height=450, use_container_width=True)

    # --- PROCESAR CLIC ---
    if mapa_output['last_object_clicked']:
        lat_clic = mapa_output['last_object_clicked']['lat']
        lon_clic = mapa_output['last_object_clicked']['lng']
        
        # Buscamos el punto más cercano en nuestro DataFrame (Distancia Euclidiana simple)
        # (Esto corrige que el clic no sea exacto al milímetro)
        distancias = (df_completo['lat'] - lat_clic)**2 + (df_completo['lon'] - lon_clic)**2
        punto_seleccionado_idx = distancias.idxmin()
    
    # --- MOSTRAR INFORMACIÓN (DINÁMICA) ---
    with col_info:
        if punto_seleccionado_idx is not None:
            # MOSTRAR DATOS DEL PUNTO ELEGIDO
            datos_punto = df_completo.iloc[punto_seleccionado_idx]
            st.info(f"📍 **Analizando Punto #{punto_seleccionado_idx}**")
            
            st.metric("Lluvia Acumulada (72h)", f"{datos_punto['lluvia_72h']:.1f} mm")
            st.metric("Humedad Suelo", f"{datos_punto['humedad_suelo']:.2f} m³/m³")
            st.metric("Susceptibilidad Terreno", f"{datos_punto['susc_modelada']:.2f}")
            
            # Mensaje de estado
            if datos_punto['lluvia_72h'] > 60:
                st.error("🚨 ALERTA ROJA LOCAL")
            elif datos_punto['lluvia_72h'] > 40:
                st.warning("🟠 ALERTA NARANJA")
            else:
                st.success("🟢 Condiciones Normales")
                
        else:
            # MOSTRAR PROMEDIOS REGIONALES (Si no hay clic)
            st.markdown("### 📊 Promedio Regional")
            st.metric("Lluvia Promedio", f"{df_completo['lluvia_72h'].mean():.1f} mm")
            st.metric("Humedad Promedio", f"{df_completo['humedad_suelo'].mean():.2f}")
            st.info("👆 **Haz clic en un punto del mapa** para ver sus condiciones específicas.")

    # --- GRÁFICA INFERIOR (DINÁMICA) ---
    st.divider()
    if punto_seleccionado_idx is not None:
        st.subheader(f"📉 Hidrograma Local (Punto {punto_seleccionado_idx})")
        df_grafica = dict_historia[punto_seleccionado_idx] # Sacamos historial de ESE punto
        
        # Ajuste zona horaria gráfica
        df_grafica['date'] = df_grafica['date'].dt.tz_convert('America/Bogota')
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_grafica['date'], y=df_grafica['lluvia_mm'], name='Lluvia (mm)', marker_color='blue'))
        fig.add_trace(go.Scatter(x=df_grafica['date'], y=df_grafica['humedad_suelo'], name='Humedad', yaxis='y2', line=dict(color='brown')))
        
        fig.update_layout(
            yaxis=dict(title="Lluvia (mm)"),
            yaxis2=dict(title="Humedad", overlaying='y', side='right'),
            height=300, margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠️ No se pudieron cargar los datos. Verifica la URL del CSV.")
