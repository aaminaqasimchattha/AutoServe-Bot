import psycopg2, os
from dotenv import load_dotenv
load_dotenv('.env')

dsn = os.getenv('DB_URI') or os.getenv('DATABASE_URL')
conn = psycopg2.connect(dsn)
cur = conn.cursor()

# 1. Insert any missing customers that exist in transaction_data safely
cur.execute("""
INSERT INTO customers (phone_number)
SELECT DISTINCT sender_number
FROM transaction_data 
WHERE sender_number IS NOT NULL 
ON CONFLICT (phone_number) DO NOTHING;
""")
conn.commit()

# 2. Link transaction_data -> customers
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
print("Cleaned up missing references and applied foreign keys successfully!")
