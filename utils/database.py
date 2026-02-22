import duckdb
import pandas as pd
import os

DB_PATH = "kite_data.db"

class KiteDatabase:
    @staticmethod
    def get_connection():
        return duckdb.connect(DB_PATH)

    @classmethod
    def initialize_db(cls):
        conn = cls.get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                ID VARCHAR,
                ICC VARCHAR,
                IMSI VARCHAR,
                MSISDN VARCHAR,
                PERIOD_START TIMESTAMP,
                PERIOD_END TIMESTAMP,
                COMMERCIAL_PLAN VARCHAR,
                SUBSCRIPTION_GROUP VARCHAR,
                ZONE VARCHAR,
                DESTINATION VARCHAR,
                SERVICE VARCHAR,
                DESCRIPTION VARCHAR,
                TARIFF VARCHAR,
                amount_value DOUBLE,
                total_cost DOUBLE,
                quota_bytes BIGINT,
                currency VARCHAR,
                kite VARCHAR,
                company VARCHAR,
                source_file VARCHAR,
                record_type VARCHAR,
                upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: rename country → kite if needed (for existing DBs)
        try:
            conn.execute("SELECT kite FROM reports LIMIT 0")
        except Exception:
            try:
                conn.execute("ALTER TABLE reports RENAME COLUMN country TO kite")
            except Exception:
                conn.execute("ALTER TABLE reports ADD COLUMN kite VARCHAR")

        # Migration: add record_type if missing (for existing DBs)
        try:
            conn.execute("SELECT record_type FROM reports LIMIT 0")
        except Exception:
            conn.execute("ALTER TABLE reports ADD COLUMN record_type VARCHAR")
            conn.execute("""
                UPDATE reports SET record_type = CASE
                    WHEN lower(DESCRIPTION) LIKE '%monthly fee%' THEN 'fee'
                    WHEN lower(DESCRIPTION) LIKE '%usage included%' THEN 'usage'
                    WHEN lower(DESCRIPTION) LIKE '%overage%' THEN 'overage'
                    WHEN lower(DESCRIPTION) LIKE '%non-billable%' OR lower(DESCRIPTION) LIKE '%status%' THEN 'status_change'
                    ELSE 'other'
                END
            """)
        conn.close()

    @classmethod
    def save_report(cls, df, filename):
        conn = cls.get_connection()
        df['source_file'] = filename

        cols = [
            'ID', 'ICC', 'IMSI', 'MSISDN', 'PERIOD_START', 'PERIOD_END',
            'COMMERCIAL_PLAN', 'SUBSCRIPTION_GROUP', 'ZONE', 'DESTINATION',
            'SERVICE', 'DESCRIPTION', 'TARIFF', 'amount_value', 'total_cost',
            'quota_bytes', 'currency', 'kite', 'company', 'source_file',
            'record_type'
        ]

        for col in cols:
            if col not in df.columns:
                df[col] = None

        df_to_save = df[cols]

        conn.register('temp_df', df_to_save)
        conn.execute(f"INSERT INTO reports ({', '.join(cols)}) SELECT * FROM temp_df")
        conn.close()

    @classmethod
    def get_all_data(cls):
        conn = cls.get_connection()
        df = conn.execute("SELECT * FROM reports").df()
        conn.close()
        return df

    @classmethod
    def get_uploaded_files(cls):
        conn = cls.get_connection()
        df = conn.execute("""
            SELECT source_file,
                   MIN(upload_timestamp) as upload_date,
                   COUNT(*) as record_count
            FROM reports
            GROUP BY source_file
            ORDER BY upload_date DESC
        """).df()
        conn.close()
        return df

    @classmethod
    def delete_file(cls, filename):
        conn = cls.get_connection()
        conn.execute("DELETE FROM reports WHERE source_file = ?", [filename])
        conn.close()

    @classmethod
    def is_file_uploaded(cls, filename):
        conn = cls.get_connection()
        res = conn.execute("SELECT 1 FROM reports WHERE source_file = ? LIMIT 1", [filename]).fetchone()
        conn.close()
        return res is not None

    @classmethod
    def get_summary_by_country(cls):
        conn = cls.get_connection()
        df = conn.execute("""
            SELECT kite, currency,
                   COUNT(DISTINCT ICC) as total_sims,
                   SUM(CASE WHEN record_type = 'fee' THEN total_cost ELSE 0 END) +
                   SUM(CASE WHEN record_type = 'overage' THEN total_cost ELSE 0 END) as total_cost,
                   SUM(CASE WHEN record_type = 'usage' THEN amount_value ELSE 0 END) / (1024*1024) as total_mb
            FROM reports
            GROUP BY kite, currency
        """).df()
        conn.close()
        return df

    @classmethod
    def get_analysis_data(cls):
        """Returns 1 row per ICC/month with separated usage, quota, fee, and overage fields."""
        conn = cls.get_connection()
        df = conn.execute("""
            SELECT
                ICC,
                strftime(PERIOD_START, '%Y-%m') as month,
                kite,
                currency,
                MAX(COMMERCIAL_PLAN) as COMMERCIAL_PLAN,
                MAX(TARIFF) as TARIFF,
                SUM(CASE WHEN record_type = 'usage' THEN amount_value ELSE 0 END) as usage_bytes,
                MAX(CASE WHEN record_type = 'fee' THEN quota_bytes ELSE 0 END) as quota_bytes,
                SUM(CASE WHEN record_type = 'fee' THEN total_cost ELSE 0 END) as monthly_fee,
                SUM(CASE WHEN record_type = 'overage' THEN amount_value ELSE 0 END) as overage_bytes,
                SUM(CASE WHEN record_type = 'overage' THEN total_cost ELSE 0 END) as overage_cost,
                SUM(CASE WHEN record_type IN ('fee', 'overage') THEN total_cost ELSE 0 END) as total_monthly_cost
            FROM reports
            WHERE record_type NOT IN ('status_change', 'other')
            GROUP BY ICC, strftime(PERIOD_START, '%Y-%m'), kite, currency
        """).df()
        conn.close()
        return df

    @classmethod
    def get_plan_catalog(cls):
        """Extract real plan catalog from TARIFF field: maps quota_bytes to fee."""
        conn = cls.get_connection()
        df = conn.execute("""
            SELECT DISTINCT
                quota_bytes,
                currency,
                total_cost as fee
            FROM reports
            WHERE record_type = 'fee' AND quota_bytes > 0 AND total_cost > 0
        """).df()
        conn.close()
        # Deduplicate: take median fee per quota/currency
        if not df.empty:
            catalog = df.groupby(['quota_bytes', 'currency']).agg({'fee': 'median'}).reset_index()
            catalog = catalog.sort_values(['currency', 'quota_bytes'])
            return catalog
        return pd.DataFrame(columns=['quota_bytes', 'currency', 'fee'])

if __name__ == "__main__":
    KiteDatabase.initialize_db()
    print("Database initialized.")
