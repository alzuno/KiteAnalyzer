# KiteAnalyzer

Dashboard de Streamlit para analizar flotas de SIMs IoT desde la plataforma Kite de Telefonica. Procesa reportes CSV de facturacion mensual, los almacena en DuckDB y ofrece recomendaciones de optimizacion de costos.

**Version actual: 2.4.0**

## Caracteristicas

- **Panel de Control**: Metricas globales de la flota (SIMs activas, consumo, costos) con graficos interactivos
- **Carga de Reportes**: Subida de CSVs via web o carga masiva por CLI
- **Optimizacion**: Deteccion automatica de SIMs zombie, over-quota e infrautilizadas con sugerencias de ahorro reales basadas en catalogo de planes
- **Tendencias**: Evolucion temporal de costos y consumo
- **Multi-moneda**: Soporte para EUR y USD con selector de moneda; nunca mezcla monedas en un mismo grafico

## Requisitos

- Python 3.11+
- pip

## Instalacion

```bash
# Clonar el repositorio
git clone <url-del-repo>
cd KiteAnalyzer

# Crear entorno virtual
python3.11 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

### Ejecutar el dashboard

```bash
streamlit run app.py
```

Se abrira en `http://localhost:8501`.

### Carga masiva de CSVs

Coloca los archivos CSV en la carpeta `Files/` y ejecuta:

```bash
python scripts/bulk_import.py
```

### Subida via web

Desde el menu lateral, selecciona **Cargar Reportes** y arrastra los archivos CSV.

---

## Formato de Archivos CSV (Kite)

### Formato general

- **Delimitador**: punto y coma (`;`)
- **Codificacion**: UTF-8 con BOM (`utf-8-sig`)
- **Quoting Excel**: los valores pueden venir envueltos en `="valor"` (ej. `="8934071100297854089"`)
- **Decimales**: coma como separador decimal en reportes en espanol (ej. `0,55`)

### Nombre del archivo

El nombre del archivo determina el pais y la empresa. Los patrones se configuran en `config/country_mapping.json`:

```json
[
  { "pattern": "company_spain", "kite": "CompanyA - España" },
  { "pattern": "company_ecuador", "kite": "CompanyB - Ecuador" }
]
```

Para agregar un nuevo pais basta con añadir una entrada al JSON — no es necesario tocar el código.

Los patrones se evalúan en orden (case-insensitive); el primero que coincide con el nombre del archivo gana. Si ninguno coincide se asigna `Unknown`.

Ejemplo: `MonthlySubscriptionDetail_company_spain_abc123_0_20260131.0.csv`

### Columnas del CSV

| Columna CSV | Descripcion |
|-|-|
| `ID` | Identificador unico del registro |
| `ICC` | Numero de SIM (identificador principal para analisis) |
| `IMSI` | International Mobile Subscriber Identity |
| `MSISDN` | Numero de telefono asociado |
| `PERIOD_START` | Inicio del periodo de facturacion (ISO 8601) |
| `PERIOD_END` | Fin del periodo de facturacion (ISO 8601) |
| `COMMERCIAL_PLAN` | Nombre del plan comercial (ej. `EU_SB_LW_5MB.`) |
| `SUBSCRIPTION_GROUP` | Grupo de suscripcion |
| `ZONE` | Zona de cobertura |
| `DESTINATION` | Destino del trafico |
| `SERVICE` | Tipo de servicio (ej. `DATA`) |
| `DESCRIPTION` | Descripcion del concepto facturado (clave para clasificacion) |
| `DISCOUNT (%)` | Porcentaje de descuento aplicado |
| `TARIFF` | Tarifa con cuota incluida (ej. `0,55EUR/5242880bytes`) |
| `AMOUNT (bytes/SMS/seconds)` | Cantidad en la unidad del servicio |
| `QUANTITY (EUR)` o `QUANTITY (USD)` | Costo en la moneda del reporte |

### Tipos de registro (DESCRIPTION)

Cada SIM puede tener **multiples filas por mes** con semanticas distintas. El sistema las clasifica automaticamente:

| Tipo (`record_type`) | Patron en DESCRIPTION | Significado de AMOUNT | Significado de QUANTITY |
|-|-|-|-|
| `fee` | "Dynamic pool voucher monthly fee" | Tamano de cuota en bytes (ej. 5242880 = 5MB) | Costo de suscripcion mensual (ej. 0.55 EUR) |
| `usage` | "Usage included in pool" | Bytes realmente consumidos | 0 (incluido en fee) |
| `overage` | "Pool overage" | Bytes de exceso sobre cuota | Costo del exceso |
| `status_change` | "Entered in a non-billable status..." | N/A | N/A |
| `other` | Cualquier otro | Variable | Variable |

> **Importante**: Sumar `AMOUNT` sin distinguir tipo de registro mezcla cuota + consumo + exceso, inflando artificialmente el consumo real. El sistema separa estos valores en columnas independientes para analisis correcto.

### Modelo de datos analitico

El metodo `get_analysis_data()` consolida los registros en **1 fila por ICC/mes** con:

| Campo | Fuente | Descripcion |
|-|-|-|
| `usage_bytes` | Filas `usage` | Bytes realmente consumidos |
| `quota_bytes` | Filas `fee` (MAX) | Tamano de la cuota contratada |
| `monthly_fee` | Filas `fee` | Costo de suscripcion mensual |
| `overage_bytes` | Filas `overage` | Bytes consumidos por encima de cuota |
| `overage_cost` | Filas `overage` | Costo real del exceso |
| `total_monthly_cost` | `fee` + `overage` | Costo total mensual |

### Logica de optimizacion

| Analisis | Criterio |
|-|-|
| **Zombie** | `usage_bytes == 0` en todos los meses registrados |
| **Over-Quota** | `usage_bytes > quota_bytes` en al menos 1 mes |
| **Infrautilizacion** | `usage_bytes / quota_bytes < 25%` en >= 60% de los meses |

Para infrautilizacion, el sistema extrae un **catalogo de planes reales** de los datos TARIFF y sugiere el plan mas barato cuya cuota cubra el consumo promedio de la SIM.

---

## Estructura del proyecto

```
KiteAnalyzer/
├── app.py                  # Aplicacion Streamlit (4 vistas)
├── config/
│   └── country_mapping.json  # Patrones de deteccion de pais/empresa por nombre de archivo
├── utils/
│   ├── parser.py           # KiteParser: parseo y clasificacion de CSVs
│   ├── database.py         # KiteDatabase: DuckDB wrapper + queries analiticas
│   └── currency.py         # Conversion de moneda via open.er-api.com
├── scripts/
│   └── bulk_import.py      # Carga masiva de CSVs desde Files/
├── Files/                  # Directorio para CSVs de entrada
├── requirements.txt        # Dependencias Python
├── CLAUDE.md               # Instrucciones para Claude Code
├── CHANGELOG.md            # Historial de cambios por version
└── kite_data.db            # Base de datos DuckDB (generada automaticamente)
```

## Tecnologias

- **Streamlit** - Framework web para el dashboard
- **DuckDB** - Base de datos analitica embebida
- **Pandas** - Procesamiento de datos
- **Plotly** - Graficos interactivos
