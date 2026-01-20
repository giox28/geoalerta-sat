# 🏔️ GeoAlerta SAT: Sistema de Alerta Temprana (Antioquia)

![Status](https://img.shields.io/badge/Estado-Operativo-success)
![Monitoreo](https://img.shields.io/badge/Puntos_Activos-58-red)
![Area](https://img.shields.io/badge/Zona-Antioquia_COL-blue)

> **GeoAlerta SAT** es un sistema autónomo de inteligencia artificial que monitorea en tiempo real el riesgo de deslizamientos en el departamento de Antioquia.

🔗 **[VER TABLERO DE CONTROL EN VIVO](https://share.streamlit.io/TU_USUARIO/geoalerta-sat/main/app.py)**
*(Sustituye el link anterior por el link real de tu app)*

---

## 🚨 ¿Cómo funciona?

El sistema opera bajo una arquitectura distribuida de tres fases:

### 1. Fase de Modelado (Google Earth Engine + Colab)
Se entrenó un modelo de **Machine Learning (Random Forest)** utilizando:
* **Base de Datos:** 2,000+ eventos históricos (SGC/NASA/Datos Locales).
* **Variables:** 16 factores geo-ambientales (Pendiente, Geología, HAND, NDVI, Lluvia, etc.).
* **Resultado:** Un mapa de susceptibilidad del cual se extrajeron **58 Puntos Centinela** de Riesgo Extremo (>80% probabilidad).

### 2. Fase de Vigilancia (GitHub Actions)
Un robot autónomo (`main.py`) se despierta **cada 6 horas** y:
1.  Lee las coordenadas de los 58 puntos críticos.
2.  Consulta la API de **Open-Meteo** para obtener la lluvia acumulada (72h) y humedad del suelo en esos puntos.
3.  Aplica una **Matriz de Decisión** dinámica.
4.  Si detecta peligro, envía una alerta vía Email.

### 3. Fase de Visualización (Streamlit)
Un Dashboard interactivo permite a las autoridades y ciudadanos visualizar:
* Ubicación de los puntos críticos.
* Nivel de alerta en tiempo real.
* Gráficas de precipitación reciente.

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Función |
| :--- | :--- | :--- |
| **Backend AI** | Python, GEE API | Entrenamiento y extracción de características. |
| **Orquestación** | GitHub Actions | Ejecución programada (Cron Job) Serverless. |
| **Frontend** | Streamlit, Folium | Visualización interactiva web. |
| **Datos Clima** | Open-Meteo (ERA5) | Telemetría satelital en tiempo real. |

---

## 📊 Matriz de Alerta

El sistema activa alertas basado en la siguiente lógica combinada:

| Nivel | Color | Criterio (Lluvia 72h + Suelo) | Acción |
| :--- | :--- | :--- | :--- |
| **0** | 🟢 Verde | Lluvia < 15mm | Monitoreo Normal |
| **1** | 🟡 Amarilla | Lluvia > 15mm | Vigilancia Preventiva |
| **2** | 🟠 Naranja | Lluvia > 40mm | **Alistamiento** |
| **3** | 🔴 Roja | Lluvia > 60mm + Suelo Saturado | **Evacuación Inmediata** |

---

## 👨‍💻 Autor
Desarrollado como prototipo de ingeniería para la Gestión del Riesgo de Desastres.
*© 2026 GeoAlerta Project.*
