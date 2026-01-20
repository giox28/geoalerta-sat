import ee
import os
import json
import pandas as pd
import sys

# --- 1. AUTENTICACIÓN ROBÓTICA ---
print("🤖 Iniciando Generador de Puntos Autónomo...")

try:
    # Intentamos leer el secreto desde las variables de entorno (GitHub Actions)
    secreto = os.environ.get('EE_SECRET_JSON')
    
    if secreto:
        # Estamos en la nube (GitHub)
        credenciales_dict = json.loads(secreto)
        credenciales = ee.ServiceAccountCredentials(None, key_data=json.dumps(credenciales_dict))
    else:
        # Estamos en local (PC) - Intentamos buscar el archivo json
        # CAMBIA ESTO SI TU ARCHIVO TIENE OTRO NOMBRE
        if os.path.exists('llave-secreta.json'):
            credenciales = ee.ServiceAccountCredentials(None, key_file='llave-secreta.json')
        else:
            raise Exception("No se encontró llave de autenticación (ni entorno ni archivo).")

    ee.Initialize(credenciales)
    print("✅ Conexión con Earth Engine exitosa.")

except Exception as e:
    print(f"❌ Error crítico de autenticación: {e}")
    sys.exit(1)

# --- 2. CONFIGURACIÓN GEOGRÁFICA ---
# Definimos Antioquia (o tu zona de interés)
ROI = ee.FeatureCollection("FAO/GAUL/2015/level1")\
    .filter(ee.Filter.eq('ADM1_NAME', 'Antioquia'))

# Si quieres usar el CSV local para entrenar, asegúrate de que 'ant.csv' esté en el repo
# Si no está, usaremos datos sintéticos o globales para no romper el script
TIENE_DATOS_LOCALES = os.path.exists('ant.csv')

# --- 3. EL MODELO (Versión Compacta) ---
def obtener_variables(roi):
    # Modelo digital de elevación
    dem = ee.Image("USGS/SRTMGL1_003").clip(roi)
    pendiente = ee.Terrain.slope(dem)
    
    # Lluvia histórica (CHIRPS) - Promedio anual
    lluvia = ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD")\
        .filterDate('2020-01-01', '2021-01-01')\
        .select('precipitation').mean().clip(roi)
    
    # NDVI (Vegetación)
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")\
        .filterBounds(roi)\
        .filterDate('2023-01-01', '2024-01-01')\
        .median().clip(roi)
    
    ndvi = l8.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    
    # Stack final (Apilamos las capas)
    stack = dem.rename('elevation')\
        .addBands(pendiente.rename('slope'))\
        .addBands(lluvia.rename('rain'))\
        .addBands(ndvi)
        
    return stack

try:
    print("📡 Descargando variables satelitales...")
    stack = obtener_variables(ROI)
    
    # --- 4. ENTRENAMIENTO (Lógica Simplificada para Automatización) ---
    # Aquí es donde el robot aprende. 
    # Para producción, idealmente cargarías un CSV 'ant.csv' del repositorio.
    
    puntos_entrenamiento = None
    
    if TIENE_DATOS_LOCALES:
        print("📂 Usando base de datos local 'ant.csv'...")
        df = pd.read_csv('ant.csv', sep=';', on_bad_lines='skip', encoding='latin-1')
        
        # Limpieza rápida (igual que en Colab)
        def limpiar(val):
            try: return float(str(val).replace(',', '.'))
            except: return None
            
        df['lat'] = df['NORTE'].apply(limpiar)
        df['lon'] = df['ESTE'].apply(limpiar)
        df = df.dropna(subset=['lat', 'lon'])
        
        # Convertir a GEE
        features = []
        for _, row in df.head(500).iterrows(): # Limitamos para velocidad
            geom = ee.Geometry.Point([row['lon'], row['lat']])
            features.append(ee.Feature(geom, {'class': 1}))
            
        positivos = ee.FeatureCollection(features)
        
        # Negativos (Zonas seguras aleatorias)
        negativos = ee.FeatureCollection.randomPoints(ROI.geometry(), 500).map(lambda f: f.set('class', 0))
        puntos_entrenamiento = positivos.merge(negativos)
        
    else:
        print("⚠️ No se encontró 'ant.csv'. Usando datos globales NASA (Fallback)...")
        # Fallback si no subiste el csv al repo
        nasa = ee.FeatureCollection("projects/google/GLC").filterBounds(ROI)
        positivos = nasa.map(lambda f: f.set('class', 1))
        negativos = ee.FeatureCollection.randomPoints(ROI.geometry(), positivos.size()).map(lambda f: f.set('class', 0))
        puntos_entrenamiento = positivos.merge(negativos)

    print(f"🧠 Entrenando modelo con {puntos_entrenamiento.size().getInfo()} puntos...")
    
    # Extraer valores para entrenar
    training_data = stack.sampleRegions(
        collection=puntos_entrenamiento,
        properties=['class'],
        scale=100, # Escala 100m para rapidez en GitHub Actions
        tileScale=16,
        geometries=True
    )
    
    # Random Forest
    rf = ee.Classifier.smileRandomForest(50).train(
        features=training_data,
        classProperty='class',
        inputProperties=stack.bandNames()
    )
    
    # Clasificar
    print("🗺️ Generando mapa de riesgo...")
    susceptibilidad = stack.classify(rf.setOutputMode('PROBABILITY'))
    
    # --- 5. EXTRACCIÓN DE PUNTOS CENTINELA ---
    print("🐕 Extrayendo los 50 puntos más críticos...")
    
    # Estrategia 'Sabueso' simplificada
    puntos_criticos = susceptibilidad.gt(0.7).selfMask() # Solo riesgo alto
    
    muestras = puntos_criticos.stratifiedSample(
        numPoints=50,
        classBand='classification',
        region=ROI.geometry(),
        scale=500,
        geometries=True,
        dropNulls=True
    )
    
    # Guardar a CSV
    datos = muestras.getInfo()
    lista_final = []
    
    if 'features' in datos:
        for f in datos['features']:
            coords = f['geometry']['coordinates']
            lista_final.append({
                'lat': coords[1],
                'lon': coords[0],
                'susc_modelada': f['properties'].get('classification', 0.99)
            })
            
    df_export = pd.DataFrame(lista_final)
    df_export.to_csv('puntos_monitoreo.csv', index=False)
    
    print(f"✅ ¡ÉXITO! Se generó 'puntos_monitoreo.csv' con {len(df_export)} puntos.")

except Exception as e:
    print(f"❌ Error en el proceso de modelado: {e}")
    sys.exit(1)
