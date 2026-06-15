import psycopg2, os
from dotenv import load_dotenv
load_dotenv('.env')

dsn = os.getenv('DB_URI') or os.getenv('DATABASE_URL')
conn = psycopg2.connect(dsn)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sender_number varchar(32);")
    conn.commit()
    print("Added sender_number to orders table.")
    
    cur.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_orders_customer'
      ) THEN
        ALTER TABLE orders
          ADD CONSTRAINT fk_orders_customer
          FOREIGN KEY (sender_number)
          REFERENCES customers(phone_number)
          ON DELETE SET NULL
          ON UPDATE CASCADE;
      END IF;
    END $$;
    """)
    conn.commit()
    print("Linked orders table to customers via sender_number!")
except Exception as e:
    print("Error:", e)
conn.close()
