#!/usr/bin/env python3
"""
Create the `orders` table in the configured Postgres database (Supabase).

Requirements:
  pip install python-dotenv psycopg2-binary

Usage:
  python scripts/create_orders_table.py
"""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    print('Missing dependency: python-dotenv. Run `pip install python-dotenv`')
    raise

try:
    import psycopg2
except Exception:
    print('Missing dependency: psycopg2-binary. Run `pip install psycopg2-binary`')
    raise


ROOT = Path(__file__).resolve().parents[1]
env_path = ROOT / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))

db_url = os.getenv('DB_URI') or os.getenv('DATABASE_URL') or os.getenv('DATABASE_URL'.upper())
if not db_url:
    print('ERROR: No DB_URI or DATABASE_URL found in environment or .env')
    sys.exit(1)

create_table_sql = '''
CREATE TABLE IF NOT EXISTS orders (
    id serial PRIMARY KEY,
    order_id varchar(64) NOT NULL,
    product text NOT NULL,
    quantity integer NOT NULL,
    address text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'Processing',
    created_at timestamptz NOT NULL DEFAULT now()
);
'''

def main():
    try:
        # Ensure SSL mode for Supabase if not already specified
        kwargs = {}
        if 'sslmode' not in db_url:
            kwargs['sslmode'] = 'require'

        conn = psycopg2.connect(dsn=db_url, **kwargs)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(create_table_sql)
        cur.close()
        conn.close()
        print('`orders` table created (or already exists).')
    except Exception as e:
        print('Failed to create table:', e)
        sys.exit(1)

if __name__ == '__main__':
    main()
