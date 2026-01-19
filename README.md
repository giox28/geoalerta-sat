# 🌍 GeoAlerta SAT: Sistema de Alerta Temprana por Deslizamientos

![Status](https://img.shields.io/badge/Estado-Operativo-success)
![Python](https://img.shields.io/badge/Python-3.9-blue)
![Automated](https://img.shields.io/badge/GitHub-Actions-orange)
![License](https://img.shields.io/badge/License-MIT-green)

> **GeoAlerta SAT** es un sistema autónomo de monitoreo y alerta temprana que integra Inteligencia Artificial Geoespacial (GeoAI) con telemetría meteorológica en tiempo real para predecir y alertar sobre riesgos de deslizamientos las 24/7.

---

## 🏗️ Arquitectura del Sistema
El sistema opera bajo una arquitectura **Serverless de Costo Cero**, utilizando GitHub Actions como orquestador para ejecutar la vigilancia cada 6 horas sin intervención humana.



### Flujo de Datos (ETL Pipeline):
1.  **Ingesta Satelital:** Conexión vía API a **Open-Meteo** (Modelos ERA5/IFS) para descargar precipitación y humedad del suelo.
2.  **Procesamiento Hidrológico:** Cálculo de **Lluvia Antecedente Efectiva** (acumulados de 3 a 15 días) y saturación del suelo.
3.  **Matriz de Decisión (AI):** Cruce de la amenaza climática dinámica con el mapa de susceptibilidad estática (generado por modelos Stacking RF+XGBoost).
4.  **Notificación:** Envío de alertas vía **SMTP (Email)** a las autoridades competentes si se superan los umbrales de riesgo.

---

## 🧠 Fundamento Científico

El sistema se basa en un modelo híbrido de Machine Learning desarrollado y validado para la geografía andina colombiana.

| Componente | Descripción Técnica |
| :--- | :--- |
| **Modelo Base** | Stacking Classifier (Random Forest + XGBoost) |
| **Rendimiento** | **AUC: 0.84** (Validado con curvas ROC y Precision-Recall) |
| **Variables Clave** | HAND (Hidrología), Rugosidad, Pendiente, Cobertura, Lluvia, Arcillas. |
| **Validación** | Alineado con el estado del arte 2025 (MDPI/Frontiers) en geomorfología cuantitativa. |

---

## 🚦 Lógica de Alerta (Semáforo)

El sistema evalúa el riesgo en tiempo real mediante la siguiente matriz de decisión:

- **🟢 NIVEL 0 (Normal):** Condiciones estables. Lluvia acumulada < 15mm.
- **🟡 NIVEL 1 (Preventiva):** Suelo saturado (>40%) o lluvias moderadas en zonas de alta susceptibilidad.
- **🟠 NIVEL 2 (Naranja):** Lluvia acumulada > 40mm en 72h. Preparación para respuesta.
- **🔴 NIVEL 3 (Roja):** Escenario crítico. Lluvia extrema (>60mm) + Suelo saturado en zonas inestables. **Evacuación sugerida.**

---

## 🛠️ Stack Tecnológico

Este proyecto fue desarrollado utilizando tecnologías Open Source:

* **Lenguaje:** Python 3.9
* **Librerías:** `pandas`, `openmeteo-requests`, `smtplib`.
* **Infraestructura:** GitHub Actions (CI/CD Cron Jobs).
* **Fuente de Datos:** Copernicus (Sentinel-2), NASA (DEM), Open-Meteo.

---

## 🚀 Instalación y Despliegue Local

Si deseas clonar este proyecto para tu propia zona de estudio:

1.  **Clonar repositorio:**
    ```bash
    git clone [https://github.com/TU_USUARIO/geoalerta-sat.git](https://github.com/TU_USUARIO/geoalerta-sat.git)
    cd geoalerta-sat
    ```

2.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configurar Variables de Entorno:**
    Crea un archivo `.env` o exporta las variables:
    ```bash
    export EMAIL_USER="tu_correo@gmail.com"
    export EMAIL_PASS="tu_password_de_aplicacion"
    ```

4.  **Ejecutar:**
    ```bash
    python main.py
    ```

---

## 👨‍💻 Autor

**Ing. Geólogo Giolmer Losiv Gómez Sánchez**
*Especialista en Geociencias Computacionales y Machine Learning.*

Desarrollado como parte de la iniciativa de modernización tecnológica para la Gestión del Riesgo de Desastres.

---
*© 2026 GeoAlerta Project. All Rights Reserved.*
