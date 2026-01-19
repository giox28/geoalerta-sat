# ==============================================================================
# SCRIPT MAESTRO: main.py (Versión v2.0 - Con Notificaciones Reales)
# ==============================================================================
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

# --- CONFIGURACIÓN ---
COORDENADAS = {'lat': 7.1193, 'lon': -73.1227} # Santander
SUSCEPTIBILIDAD_ESTATICA = 0.90 

# --- 1. INGESTA ---
def obtener_datos():
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": COORDENADAS['lat'], 
        "longitude": COORDENADAS['lon'],
        "hourly": ["precipitation", "soil_moisture_0_to_1cm"],
        "timezone": "auto", "past_days": 3, "forecast_days": 1
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
    return df

# --- 2. PROCESAMIENTO ---
def procesar_amenaza(df):
    df['lluvia_3d'] = df['lluvia_mm'].rolling(window=72).sum()
    
    def semaforo(fila):
        if (fila['lluvia_3d'] > 60) or (fila['humedad_suelo'] > 0.4 and fila['lluvia_3d'] > 20): return 3
        elif fila['lluvia_3d'] > 40: return 2
        elif fila['lluvia_3d'] > 15: return 1
        return 0
    
    df['alerta_clima'] = df.apply(semaforo, axis=1)
    return df

# --- 3. DECISIÓN ---
def evaluar_riesgo(df, susc):
    dato = df.iloc[-1]
    amenaza = dato['alerta_clima']
    nivel = 0
    mensaje = "Condiciones Normales"
    
    if susc > 0.8:
        if amenaza >= 2: nivel, mensaje = 3, "🚨 ROJA: Evacuación Inmediata"
        elif amenaza == 1: nivel, mensaje = 2, "🟠 NARANJA: Preparar respuesta"
        elif amenaza == 0 and dato['lluvia_3d'] > 5: nivel, mensaje = 1, "🟡 AMARILLA: Monitoreo activado"
    
    # --- MODO PRUEBA: Forzar alerta para verificar que el email funciona ---
    # (Borra estas 2 líneas cuando ya esté en producción real)
   # if nivel == 0: 
   #     nivel, mensaje = 1, "🟡 PRUEBA DE SISTEMA: Verificando envío de correo"
        
    return nivel, mensaje, dato

# --- 4. NOTIFICACIÓN (Email Real) ---
def enviar_email(nivel, mensaje, datos):
    usuario = os.environ.get('EMAIL_USER')
    password = os.environ.get('EMAIL_PASS')
    
    if not usuario or not password:
        print("⚠️ No se configuraron las credenciales de correo. Saltando envío.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"GEOALERTA: Nivel {nivel} - {datetime.now().strftime('%d/%m %H:%M')}"
    msg['From'] = usuario
    msg['To'] = usuario # Te lo envías a ti mismo
    
    contenido = f"""
    ⚠️ REPORTE AUTOMÁTICO DE AMENAZA
    --------------------------------
    NIVEL: {nivel}
    ESTADO: {mensaje}
    
    DATOS TÉCNICOS:
    - Ubicación: {COORDENADAS}
    - Lluvia 3 Días: {datos['lluvia_3d']:.1f} mm
    - Humedad Suelo: {datos['humedad_suelo']:.2f} m3/m3
    
    Acción requerida: Verificar condiciones locales.
    """
    msg.set_content(contenido)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(usuario, password)
            smtp.send_message(msg)
        print("✅ ¡CORREO ENVIADO EXITOSAMENTE!")
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")

# --- EJECUCIÓN ---
if __name__ == "__main__":
    df = procesar_amenaza(obtener_datos())
    nivel, msg, dato = evaluar_riesgo(df, SUSCEPTIBILIDAD_ESTATICA)
    
    print(f"Estado: {msg}")
    if nivel > 0:
        enviar_email(nivel, msg, dato)
