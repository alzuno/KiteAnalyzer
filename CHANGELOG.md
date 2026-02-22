# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato esta basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

## [2.3.0] - 2026-02-22

### Agregado
- Soporte de monedas PEN (soles peruanos) y ARS (pesos argentinos) en selector de visualización
- Columna "Moneda Original" en las 3 tablas de optimización (Zombies, Over-Quota, Bajo Consumo): muestra la divisa nativa de cada SIM
- Columna "Kite" en todas las tablas de optimización (reemplaza "country")
- Archivos `.gitignore` y `LICENSE` (MIT) para publicación en GitHub

### Cambiado
- Concepto "Country/País" renombrado a "Kite" en toda la UI, columnas y base de datos (migración automática de schema)
- Análisis de Infrautilización (Bajo Consumo) excluye SIMs zombie (ya aparecen en la sección Zombies)
- Over-Quota: `total_exceso_mb` reemplazado por `Exceso Prom/Mes (MB)` — muestra el promedio de MB excedidos en los meses que sí superaron la cuota, ordenado de mayor a menor

## [2.2.0] - 2026-02-22

### Agregado
- Conversión de moneda automática usando open.er-api.com (tasas cacheadas 1 hora)
- Nuevo módulo `utils/currency.py` con `get_exchange_rates()` y `convert_amount()`
- Selector "Moneda de visualización" en sidebar convierte todos los valores a la moneda elegida
- Nota en sidebar con fecha de última actualización de tasas
- Detección de país/empresa configurable vía `config/country_mapping.json` (sin tocar código)

### Cambiado
- El selector de moneda ya no filtra datos sino que los convierte: ahora se muestran flotas multi-moneda consolidadas
- `utils/parser.py` carga patrones de país/empresa desde `config/country_mapping.json` en vez de tenerlos hardcodeados

## [2.1.1] - 2026-02-20

### Corregido
- Excluidos registros `status_change` y `other` del analisis (`get_analysis_data()`). SIMs desactivadas ya no cuentan como zombies ni inflan conteos de meses

## [2.1.0] - 2026-02-20

### Cambiado
- Renombrado `scripts/load_samples.py` a `scripts/bulk_import.py` para mayor claridad sobre su funcion de carga masiva
- Reemplazado parametro deprecado `use_container_width=True` por `width='stretch'` en todas las llamadas de Streamlit (`st.plotly_chart`, `st.dataframe`)

## [2.0.0] - 2026-02-20

### Cambiado
- **Modelo de datos corregido**: los registros CSV ahora se clasifican por tipo (`fee`, `usage`, `overage`, `status_change`, `other`) basado en el campo DESCRIPTION
- **Panel de Control**: "Datos Consumidos" muestra solo consumo real (`usage_bytes`) en lugar de sumar cuota + consumo + exceso
- **Zombies**: deteccion basada en `usage_bytes == 0` (antes usaba `amount_value` que incluia cuota, causando falsos negativos)
- **Over-Quota**: comparacion `usage_bytes > quota_bytes` con costo de exceso real del CSV en vez de proxy calculado
- **Infrautilizacion**: `Uso % = usage_bytes / quota_bytes * 100`; sugerencia de plan basada en catalogo real extraido de TARIFF (antes era 40% arbitrario)
- **Tendencias**: graficos filtrados por moneda, consumo basado solo en `usage_bytes`

### Agregado
- Columna `record_type` en parser y base de datos para clasificar tipo de registro
- Metodo `get_analysis_data()`: retorna 1 fila por ICC/mes con campos separados (usage_bytes, quota_bytes, monthly_fee, overage_bytes, overage_cost, total_monthly_cost)
- Metodo `get_plan_catalog()`: extrae catalogo de planes reales desde datos TARIFF
- Selector de moneda en sidebar cuando hay multiples monedas (EUR/USD)
- Migracion automatica de schema para bases de datos existentes (agrega `record_type` y lo calcula)
- Soporte multi-moneda: nunca se mezclan costos de distintas monedas en un mismo grafico

### Corregido
- Deteccion de zombies ahora funciona correctamente (antes 0 SIMs detectadas, ahora ~8200)
- Over-quota ahora detecta SIMs reales que exceden su plan
- Ahorro estimado en infrautilizacion basado en diferencia de fee real vs plan sugerido

## [1.0.0] - 2026-02-19

### Agregado
- Dashboard inicial con 4 vistas: Panel de Control, Cargar Reportes, Optimizacion, Tendencias
- Parser de CSVs Kite con soporte para formato Excel `="value"` y deteccion de moneda
- Base de datos DuckDB para almacenamiento persistente
- Deteccion de pais/empresa por nombre de archivo
- Script de carga masiva (`load_samples.py`)
- Soporte para reportes de Espana (EUR) y Ecuador (USD)
