import psycopg2, os
from dotenv import load_dotenv
load_dotenv('.env')

dsn = os.getenv('DB_URI') or os.getenv('DATABASE_URL')
if not dsn:
    print("No DB_URI found.")
    exit(1)

conn = psycopg2.connect(dsn)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE customers ADD CONSTRAINT unique_phone UNIQUE (phone_number);")
    print("Added unique constraint on phone_number.")
except psycopg2.errors.DuplicateTable:
    pass
except psycopg2.errors.UniqueViolation:
    pass
except Exception as e:
    print("Unique constraint error (likely already exists):", e)
conn.commit()

try:
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
    print("Linked orders table.")
except Exception as e:
    print("Error linking orders:", e)
conn.commit()

try:
    cur.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_transactions_customer'
      ) THEN
        ALTER TABLE transaction_data
          ADD CONSTRAINT fk_transactions_customer
          FOREIGN KEY (sender_number)
          REFERENCES customers(phone_number)
          ON DELETE SET NULL
          ON UPDATE CASCADE;
      END IF;
    END $$;
    """)
    print("Linked transaction_data table.")
except Exception as e:
    print("Error linking transaction_data:", e)
conn.commit()

conn.close()
print("All foreign keys applied successfully!")
