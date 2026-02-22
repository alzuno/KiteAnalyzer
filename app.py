import streamlit as st
import pandas as pd
import plotly.express as px
from utils.parser import KiteParser
from utils.database import KiteDatabase
from utils.currency import get_exchange_rates, convert_amount
import os

# Configuración de Página
st.set_page_config(
    page_title="KiteAnalyzer | Dashboard Global IoT",
    page_icon="📡",
    layout="wide",
)

# Estética Premium y Correcciones de Color
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.8rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
        font-size: 1rem !important;
    }
    .stMetric {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    h1, h2, h3 {
        color: #58a6ff !important;
        font-family: 'Inter', sans-serif;
    }
    .stAlert {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Base de Datos
KiteDatabase.initialize_db()

# Navegación Lateral
st.sidebar.title("📡 KiteAnalyzer")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegación", ["Panel de Control", "Cargar Reportes", "Optimización", "Análisis de Tendencias"])

# Currency selector in sidebar
raw_data = KiteDatabase.get_all_data()
if not raw_data.empty:
    currencies = sorted(raw_data['currency'].dropna().unique())
    all_currencies = sorted(set(currencies) | {"EUR", "USD", "PEN", "ARS"})
    if currencies:
        selected_currency = st.sidebar.selectbox("Moneda de visualización", all_currencies, index=all_currencies.index(currencies[0]))
    else:
        selected_currency = None
else:
    selected_currency = None

# Fetch exchange rates and show update date
_rates_cache = None
_rates_update_date = ""
if selected_currency:
    try:
        _rates_data = get_exchange_rates(selected_currency)
        _rates_cache = _rates_data["rates"]
        _rates_update_date = _rates_data["time_last_update_utc"]
        if _rates_update_date:
            st.sidebar.caption(f"Tasas actualizadas: {_rates_update_date[:16]}")
    except Exception:
        st.sidebar.warning("No se pudieron obtener tasas de cambio. Se muestran valores originales.")

def apply_currency_conversion(df: pd.DataFrame, target_currency: str, rates: dict) -> pd.DataFrame:
    """Convert cost columns to target_currency for all rows with a different currency."""
    if df.empty or rates is None:
        return df
    df = df.copy()
    cost_cols = ['total_monthly_cost', 'monthly_fee', 'overage_cost']
    for col in cost_cols:
        if col in df.columns:
            df[col] = df.apply(
                lambda row: convert_amount(row[col], row['currency'], target_currency, rates)
                if row['currency'] != target_currency else row[col],
                axis=1
            )
    df['currency'] = target_currency
    return df


if menu == "Cargar Reportes":
    st.title("📤 Cargar Reportes Kite")
    st.write("Sube archivos CSV de las plataformas Kite (España, Ecuador, etc.).")

    uploaded_files = st.file_uploader("Elige archivos CSV de Kite", accept_multiple_files=True, type=['csv'])

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if KiteDatabase.is_file_uploaded(uploaded_file.name):
                st.info(f"El archivo '{uploaded_file.name}' ya ha sido procesado previamente. Se omitirá.")
            else:
                df = KiteParser.parse(uploaded_file)
                KiteDatabase.save_report(df, uploaded_file.name)
                st.success(f"Reporte procesado con éxito: {uploaded_file.name}")
                with st.expander(f"Ver vista previa de {uploaded_file.name}"):
                    st.dataframe(df.head())

    st.markdown("---")
    st.subheader("🗂️ Archivos Procesados")

    files_df = KiteDatabase.get_uploaded_files()

    if files_df.empty:
        st.write("No hay archivos registrados en la base de datos.")
    else:
        for _, row in files_df.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{row['source_file']}**")
            with col2:
                st.caption(f"Cargado: {row['upload_date']} ({row['record_count']} filas)")
            with col3:
                if st.button("Eliminar", key=f"del_{row['source_file']}"):
                    KiteDatabase.delete_file(row['source_file'])
                    st.rerun()

elif menu == "Panel de Control":
    st.title("📊 Resumen Global de SIMs")

    analysis = KiteDatabase.get_analysis_data()

    if analysis.empty:
        st.info("No hay datos disponibles. Por favor, carga algunos reportes primero.")
    else:
        if selected_currency:
            analysis = apply_currency_conversion(analysis, selected_currency, _rates_cache)

        st.subheader("Estado de la Flota")

        total_sims = analysis['ICC'].nunique()
        active_kites = analysis['kite'].nunique()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total SIMs", f"{total_sims:,}")
        col4.metric("Kites", active_kites)

        if selected_currency:
            total_cost = analysis['total_monthly_cost'].sum()
            total_usage_mb = analysis['usage_bytes'].sum() / (1024 * 1024)
            col2.metric("Costo Total", f"{total_cost:,.2f} {selected_currency}")
            col3.metric("Datos Consumidos", f"{total_usage_mb:,.2f} MB")
        else:
            col2.metric("Costo Total", "N/A")
            col3.metric("Datos Consumidos", "N/A")

        st.markdown("---")

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Evolución de Costos por Kite")
            if selected_currency:
                cost_kite = analysis.groupby(['month', 'kite'])['total_monthly_cost'].sum().reset_index()
                fig_cost = px.line(cost_kite, x='month', y='total_monthly_cost', color='kite',
                                   markers=True,
                                   labels={'total_monthly_cost': f'Costo ({selected_currency})', 'month': 'Mes', 'kite': 'Kite'},
                                   color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_cost, width='stretch')

        with c2:
            st.subheader("Uso Total (MB) por Kite")
            if selected_currency:
                usage_kite = analysis.groupby(['month', 'kite'])['usage_bytes'].sum().reset_index()
                usage_kite['MB'] = usage_kite['usage_bytes'] / (1024 * 1024)
                fig_usage = px.bar(usage_kite, x='month', y='MB', color='kite', barmode='stack',
                                  labels={'MB': 'Megabytes', 'month': 'Mes', 'kite': 'Kite'},
                                  color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_usage, width='stretch')

        st.markdown("---")

        # Optimization KPIs and cost breakdown
        zombie_iccs = analysis.groupby('ICC').filter(lambda g: (g['usage_bytes'] == 0).all())['ICC'].unique()
        overquota_iccs = analysis[(analysis['quota_bytes'] > 0) & (analysis['usage_bytes'] > analysis['quota_bytes'])]['ICC'].unique()

        kcol1, kcol2 = st.columns(2)
        kcol1.metric("SIMs Zombie", len(zombie_iccs), help="SIMs con 0 consumo en todos sus meses registrados")
        kcol2.metric("SIMs Over-Quota", len(overquota_iccs), help="SIMs que superaron su cuota en al menos 1 mes")

        if selected_currency:
            st.subheader("Costo por Tipo (Cuota vs Excedente) por Kite")
            cost_type = analysis.groupby(['month', 'kite']).agg(
                monthly_fee=('monthly_fee', 'sum'),
                overage_cost=('overage_cost', 'sum')
            ).reset_index()
            cost_type_melted = cost_type.melt(
                id_vars=['month', 'kite'],
                value_vars=['monthly_fee', 'overage_cost'],
                var_name='tipo', value_name='costo'
            )
            cost_type_melted['tipo'] = cost_type_melted['tipo'].map({
                'monthly_fee': 'Cuota mensual',
                'overage_cost': 'Excedente'
            })
            fig_cost_type = px.bar(
                cost_type_melted, x='month', y='costo', color='tipo',
                facet_col='kite', barmode='stack',
                labels={'costo': f'Costo ({selected_currency})', 'month': 'Mes', 'tipo': 'Tipo', 'kite': 'Kite'},
                color_discrete_map={'Cuota mensual': '#636EFA', 'Excedente': '#EF553B'}
            )
            fig_cost_type.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig_cost_type, width='stretch')

elif menu == "Optimización":
    st.title("💡 Recomendaciones de Optimización")

    analysis = KiteDatabase.get_analysis_data()

    if analysis.empty:
        st.info("Carga datos para ver recomendaciones.")
    elif selected_currency is None:
        st.info("No se detectó moneda en los datos.")
    else:
        # Preserve original currency before conversion
        analysis['moneda_original'] = analysis['currency']
        analysis = apply_currency_conversion(analysis, selected_currency, _rates_cache)
        monthly_sim = analysis.copy()
        plan_catalog = KiteDatabase.get_plan_catalog()
        # Use original currency plan catalog; if rates available convert fees too
        if _rates_cache is not None:
            plan_catalog = plan_catalog.copy()
            plan_catalog['fee'] = plan_catalog.apply(
                lambda row: convert_amount(row['fee'], row['currency'], selected_currency, _rates_cache),
                axis=1
            )
            plan_catalog['currency'] = selected_currency
        else:
            plan_catalog = plan_catalog[plan_catalog['currency'] == selected_currency]

        tab1, tab2, tab3 = st.tabs(["🧟 SIMs sin Consumo (Zombies)", "🚀 Over-Quota", "📉 Bajo Consumo (Downgrade)"])

        with tab1:
            st.subheader("SIMs Detectadas sin Tráfico")
            st.write("SIMs que generan cargos recurrentes pero mantienen **0 consumo** históricamente.")

            zombie_base = monthly_sim.copy()
            zombie_base['is_zombie'] = zombie_base['usage_bytes'] == 0

            zombie_consistency = zombie_base.groupby(['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency']).agg({
                'is_zombie': ['sum', 'count'],
                'monthly_fee': 'mean',
                'moneda_original': 'first'
            }).reset_index()
            zombie_consistency.columns = ['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency', 'meses_zombie', 'meses_total', 'fee_mensual_prom', 'moneda_original']

            # SIMs zombie in all their recorded months
            zombies = zombie_consistency[zombie_consistency['meses_zombie'] == zombie_consistency['meses_total']].copy()

            if not zombies.empty:
                zombies['Consistencia'] = zombies.apply(lambda r: f"{int(r['meses_zombie'])}/{int(r['meses_total'])} m", axis=1)

                total_monthly_savings = zombies['fee_mensual_prom'].sum()
                st.warning(f"Ahorro mensual estimado al desactivar zombies: {total_monthly_savings:,.2f} {selected_currency}")

                # Pivot: usage in MB per month
                pivot_z = zombie_base[zombie_base['ICC'].isin(zombies['ICC'])].pivot_table(
                    index=['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency'],
                    columns='month', values='usage_bytes', aggfunc='sum'
                ).reset_index()
                month_cols_z = sorted([c for c in pivot_z.columns if isinstance(c, str) and len(c) == 7 and c[4] == '-'])
                for mc in month_cols_z:
                    pivot_z[mc] = pivot_z[mc].fillna(0) / (1024 * 1024)
                    pivot_z.rename(columns={mc: f"{mc} (MB)"}, inplace=True)
                month_cols_z_r = [f"{mc} (MB)" for mc in month_cols_z]

                zombies_display = zombies[['ICC', 'kite', 'COMMERCIAL_PLAN', 'moneda_original', 'Consistencia', 'fee_mensual_prom']].merge(
                    pivot_z[['ICC'] + month_cols_z_r], on='ICC', how='left'
                ).rename(columns={'fee_mensual_prom': f'Fee Mensual ({selected_currency})', 'kite': 'Kite', 'moneda_original': 'Moneda Original'})
                st.dataframe(zombies_display, width='stretch')
                st.caption("📌 Las columnas de mes muestran el consumo real en MB. Todas deberían ser 0 para SIMs zombie.")
            else:
                st.success("¡Excelente! No se detectaron SIMs sin consumo consistente.")

        with tab2:
            st.subheader("Análisis de Exceso de Cuota (Over-Quota)")
            st.write("Identificación de SIMs que superan su franquicia y generan sobrecostos recurrentes.")

            oq_base = monthly_sim[monthly_sim['quota_bytes'] > 0].copy()
            oq_base['is_over'] = oq_base['usage_bytes'] > oq_base['quota_bytes']
            oq_base['exceso_mb'] = (oq_base['usage_bytes'] - oq_base['quota_bytes']).clip(lower=0) / (1024 * 1024)

            oq_over_only = oq_base[oq_base['is_over']].groupby(['ICC'])['exceso_mb'].mean().reset_index().rename(columns={'exceso_mb': 'exceso_mb_promedio'})
            oq_consistency = oq_base.groupby(['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency']).agg({
                'is_over': ['sum', 'count'],
                'overage_cost': 'sum',
                'quota_bytes': 'first',
                'moneda_original': 'first'
            }).reset_index()
            oq_consistency.columns = ['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency', 'meses_over', 'meses_total', 'costo_overage', 'cuota_bytes', 'moneda_original']
            oq_consistency = oq_consistency.merge(oq_over_only, on='ICC', how='left')
            oq_consistency['exceso_mb_promedio'] = oq_consistency['exceso_mb_promedio'].fillna(0)

            over_limit = oq_consistency[oq_consistency['meses_over'] > 0].copy()

            if not over_limit.empty:
                over_limit['Consistencia'] = over_limit.apply(lambda r: f"{int(r['meses_over'])}/{int(r['meses_total'])} m", axis=1)
                over_limit['Cuota (MB)'] = over_limit['cuota_bytes'] / (1024 * 1024)
                st.error(f"Se detectaron {len(over_limit)} SIMs con historial de exceso de consumo.")

                # Pivot: real usage in MB per month
                oq_base['consumo_mb'] = oq_base['usage_bytes'] / (1024 * 1024)
                pivot_oq = oq_base[oq_base['ICC'].isin(over_limit['ICC'])].pivot_table(
                    index=['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency'],
                    columns='month', values='consumo_mb', aggfunc='sum'
                ).reset_index()
                month_cols_oq = sorted([c for c in pivot_oq.columns if isinstance(c, str) and len(c) == 7 and c[4] == '-'])
                for mc in month_cols_oq:
                    pivot_oq[mc] = pivot_oq[mc].fillna(0)
                    pivot_oq.rename(columns={mc: f"{mc} (MB)"}, inplace=True)
                month_cols_oq_r = [f"{mc} (MB)" for mc in month_cols_oq]

                over_display = over_limit[['ICC', 'kite', 'COMMERCIAL_PLAN', 'moneda_original', 'Cuota (MB)', 'Consistencia', 'exceso_mb_promedio', 'costo_overage']].merge(
                    pivot_oq[['ICC'] + month_cols_oq_r], on='ICC', how='left'
                ).rename(columns={
                    'costo_overage': f'Costo Exceso ({selected_currency})',
                    'exceso_mb_promedio': 'Exceso Prom/Mes (MB)',
                    'kite': 'Kite',
                    'moneda_original': 'Moneda Original'
                }).sort_values(by='Exceso Prom/Mes (MB)', ascending=False)
                st.dataframe(over_display, width='stretch')
                st.caption("📌 Las columnas de mes muestran el consumo real (MB). Compara con 'Cuota (MB)' para ver los meses donde se superó la franquicia.")
                st.info("💡 **Tip**: Prioriza cambiar el plan de las SIMs con consistencia alta (ej. 2/2 o 3/3) ya que su sobrecosto es predecible.")
            else:
                st.success("No se detectaron SIMs superando su cuota consistentemente.")

        with tab3:
            st.subheader("Análisis de Infrautilización (Bajo Consumo)")
            st.write("Identificación de SIMs que consumen mucho menos de lo contratado de forma constante.")

            zombie_iccs = zombies['ICC'].unique() if not zombies.empty else []
            idx_base = monthly_sim[(monthly_sim['quota_bytes'] > 0) & (~monthly_sim['ICC'].isin(zombie_iccs))].copy()
            idx_base['Uso %'] = (idx_base['usage_bytes'] / idx_base['quota_bytes']) * 100
            idx_base['is_low'] = idx_base['Uso %'] < 25
            idx_base['consumo_mb'] = idx_base['usage_bytes'] / (1024 * 1024)

            consistency = idx_base.groupby(['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency']).agg({
                'is_low': ['sum', 'count'],
                'monthly_fee': 'mean',
                'consumo_mb': 'mean',
                'quota_bytes': 'first',
                'moneda_original': 'first'
            }).reset_index()

            consistency.columns = ['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency', 'meses_bajo', 'meses_total', 'fee_mensual', 'consumo_prom_mb', 'cuota_bytes', 'moneda_original']

            under_utilized = consistency[consistency['meses_bajo'] / consistency['meses_total'] >= 0.6].copy()

            if not under_utilized.empty:
                under_utilized['Consistencia'] = under_utilized.apply(lambda r: f"{int(r['meses_bajo'])}/{int(r['meses_total'])} m", axis=1)
                under_utilized['Cuota (MB)'] = under_utilized['cuota_bytes'] / (1024 * 1024)

                # Suggest cheaper plan from real catalog
                def suggest_plan(row):
                    avg_bytes = row['consumo_prom_mb'] * 1024 * 1024
                    current_fee = row['fee_mensual']
                    candidates = plan_catalog[plan_catalog['quota_bytes'] >= avg_bytes].sort_values('fee')
                    if not candidates.empty:
                        best = candidates.iloc[0]
                        if best['fee'] < current_fee:
                            return pd.Series({
                                'Plan Sugerido': f"{best['quota_bytes']/(1024*1024):.0f}MB ({best['fee']:.2f} {selected_currency})",
                                'Ahorro Est.': current_fee - best['fee']
                            })
                    return pd.Series({'Plan Sugerido': 'Plan actual óptimo', 'Ahorro Est.': 0.0})

                suggestions = under_utilized.apply(suggest_plan, axis=1)
                under_utilized['Plan Sugerido'] = suggestions['Plan Sugerido']
                under_utilized['Ahorro Est.'] = suggestions['Ahorro Est.']

                total_savings = under_utilized['Ahorro Est.'].sum()
                if total_savings > 0:
                    st.warning(f"💰 Ahorro Mensual Estimado Total: {total_savings:,.2f} {selected_currency}")

                # Pivot: usage in MB per month
                pivot_low = idx_base[idx_base['ICC'].isin(under_utilized['ICC'])].pivot_table(
                    index=['ICC', 'kite', 'COMMERCIAL_PLAN', 'currency'],
                    columns='month', values='consumo_mb', aggfunc='sum'
                ).reset_index()
                month_cols_low = sorted([c for c in pivot_low.columns if isinstance(c, str) and len(c) == 7 and c[4] == '-'])
                for mc in month_cols_low:
                    pivot_low[mc] = pivot_low[mc].fillna(0)
                    pivot_low.rename(columns={mc: f"{mc} (MB)"}, inplace=True)
                month_cols_low_r = [f"{mc} (MB)" for mc in month_cols_low]

                low_display = under_utilized[['ICC', 'kite', 'COMMERCIAL_PLAN', 'moneda_original', 'Cuota (MB)', 'Consistencia', 'Plan Sugerido', 'Ahorro Est.']].merge(
                    pivot_low[['ICC'] + month_cols_low_r], on='ICC', how='left'
                ).rename(columns={'kite': 'Kite', 'moneda_original': 'Moneda Original'}).sort_values(by='Ahorro Est.', ascending=False)
                st.dataframe(low_display, width='stretch')
                st.caption("📌 Las columnas de mes muestran el consumo real (MB). Compara con 'Cuota (MB)' para confirmar el infrauso.")
                st.success("💡 **Tip**: Estas SIMs mantienen un bajo consumo históricamente. Cambiarlas a un plan menor asegura un ahorro constante.")
            else:
                st.success("No se detectaron SIMs con infrautilización consistente.")


elif menu == "Análisis de Tendencias":
    st.title("📉 Tendencias y KPIs")
    st.write("Evolución de tu flota de IoT a lo largo del tiempo.")

    analysis = KiteDatabase.get_analysis_data()
    if not analysis.empty and selected_currency:
        analysis = apply_currency_conversion(analysis, selected_currency, _rates_cache)
        monthly = analysis.groupby(['month', 'kite']).agg({
            'total_monthly_cost': 'sum',
            'usage_bytes': 'sum'
        }).reset_index()
        monthly['MB'] = monthly['usage_bytes'] / (1024 * 1024)

        c1, c2 = st.columns(2)
        with c1:
            fig_trend_cost = px.line(monthly, x='month', y='total_monthly_cost', color='kite', markers=True,
                               title=f"Evolución de Costos Mensuales ({selected_currency})",
                               labels={'total_monthly_cost': f'Costo Total ({selected_currency})', 'month': 'Mes'})
            fig_trend_cost.update_traces(hovertemplate='Mes: %{x}<br>Costo: %{y:,.2f}')
            st.plotly_chart(fig_trend_cost, width='stretch')
        with c2:
            fig_trend_usage = px.line(monthly, x='month', y='MB', color='kite', markers=True,
                                title="Evolución de Consumo (MB)", labels={'MB': 'Megabytes', 'month': 'Mes'})
            fig_trend_usage.update_traces(hovertemplate='Mes: %{x}<br>Consumo: %{y:,.2f} MB')
            st.plotly_chart(fig_trend_usage, width='stretch')
    else:
        st.info("Los análisis de tendencias aparecerán conforme cargues reportes de diferentes meses.")
