"""Create transaction_data table in Supabase/Postgres.

Usage:
  Set the environment variable `DATABASE_URL` or `DB_URI` to your Supabase connection string,
  then run: python create_transaction_table.py
"""
import os
import sys

try:
    import psycopg2
except Exception as e:
    print("psycopg2 is required. Install with: pip install psycopg2-binary")
    raise


def main():
    db_url = os.getenv("DB_URI") or os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL".upper())
    if not db_url:
        print("Error: No DATABASE_URL or DB_URI environment variable set.")
        sys.exit(1)

    kwargs = {}
    if "sslmode" not in db_url:
        kwargs["sslmode"] = "require"

    conn = psycopg2.connect(dsn=db_url, **kwargs)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transaction_data (
                id serial PRIMARY KEY,
                transaction_id varchar(128),
                sender_name text,
                receiver_name text,
                amount text,
                date text,
                time text,
                bank_or_service text,
                status text,
                raw_text text,
                sender_number text,
                saved_at timestamptz DEFAULT now()
            )
            """
        )
        conn.commit()
        print("transaction_data table created or already exists.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
