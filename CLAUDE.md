# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KiteAnalyzer is a Streamlit dashboard for analyzing IoT SIM card fleet data from Telefónica's Kite platform. It processes CSV billing reports from multiple countries (Spain, Ecuador), stores them in DuckDB, and provides cost optimization recommendations.

## Commands

- **Run app**: `streamlit run app.py`
- **Bulk load CSVs**: `python scripts/bulk_import.py` (loads all CSVs from `Files/` directory)
- **Python**: 3.11, venv at `.venv/`
- **Install deps**: `pip install -r requirements.txt`

## Architecture

- `app.py` — Single-file Streamlit app with 4 views: Panel de Control (dashboard), Cargar Reportes (upload), Optimización (optimization recommendations), Análisis de Tendencias (trends)
- `utils/parser.py` — `KiteParser`: parses semicolon-delimited Kite CSVs, cleans Excel-style `="value"` formatting, detects currency from headers, infers country/company from filename patterns
- `utils/database.py` — `KiteDatabase`: DuckDB wrapper (`kite_data.db`), handles CRUD for the single `reports` table
- `scripts/bulk_import.py` — CLI script to bulk-import CSVs from `Files/` directory

## Key Domain Concepts

- **ICC**: SIM card identifier (primary key for analysis)
- **Zombie SIMs**: SIMs with recurring costs but zero data consumption across all months
- **Over-Quota**: SIMs exceeding their plan's data allowance (`quota_bytes` extracted from TARIFF field)
- **Underutilized**: SIMs using <25% of quota in ≥60% of months — candidates for plan downgrade
- Data amounts are stored in bytes; display is in MB (÷ 1024²)
- Costs are multi-currency (EUR, USD) — grouped and displayed per currency

## Conventions

- UI language is Spanish
- Country detection relies on filename substrings: `eu_location` → Spain, `location_world_demo` → Ecuador
- CSV format: semicolon-separated, UTF-8 BOM, may contain `="value"` Excel quoting
