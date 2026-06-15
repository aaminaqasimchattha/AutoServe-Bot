import { NextResponse } from 'next/server';
import { db } from '../db/dbClient';
import { sql } from 'drizzle-orm';
import fs from 'fs/promises';
import path from 'path';

const FALLBACK_DIR = path.resolve(process.cwd(), './data');
const FALLBACK_FILE = path.join(FALLBACK_DIR, 'customers_fallback.json');

// ─── Ensure all tables + FK constraints exist ──────────────────────────────────
async function ensureSchema() {
  // 1. customers table
  await db.execute(sql`
    CREATE TABLE IF NOT EXISTS customers (
      id             serial PRIMARY KEY,
      phone_number   varchar(32)  NOT NULL UNIQUE,
      name           text,
      first_seen     timestamptz  NOT NULL DEFAULT now(),
      last_seen      timestamptz  NOT NULL DEFAULT now(),
      message_count  integer      NOT NULL DEFAULT 1,
      last_message   text,
      last_order_id  varchar(64),
      last_order_status varchar(32),
      last_transaction_ref varchar(128),
      notes          text,
      email          text,
      cnic           text,
      created_at     timestamptz  NOT NULL DEFAULT now()
    )
  `);

  // Ensure columns exist if table was created previously without them
  await db.execute(sql`
    DO $$
    BEGIN
      BEGIN
        ALTER TABLE customers ADD COLUMN email TEXT;
      EXCEPTION
        WHEN duplicate_column THEN NULL;
      END;
      BEGIN
        ALTER TABLE customers ADD COLUMN cnic TEXT;
      EXCEPTION
        WHEN duplicate_column THEN 
          ALTER TABLE customers ALTER COLUMN cnic TYPE TEXT;
      END;
    END $$;
  `);

  // 2. Add FK on orders.sender_number → customers.phone_number (idempotent)
  await db.execute(sql`
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_orders_customer'
          AND table_name = 'orders'
      ) THEN
        ALTER TABLE orders
          ADD CONSTRAINT fk_orders_customer
          FOREIGN KEY (sender_number)
          REFERENCES customers(phone_number)
          ON DELETE SET NULL
          ON UPDATE CASCADE;
      END IF;
    END $$;
  `);

  // 3. Add FK on transaction_data.sender_number → customers.phone_number (idempotent)
  await db.execute(sql`
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_transactions_customer'
          AND table_name = 'transaction_data'
      ) THEN
        ALTER TABLE transaction_data
          ADD CONSTRAINT fk_transactions_customer
          FOREIGN KEY (sender_number)
          REFERENCES customers(phone_number)
          ON DELETE SET NULL
          ON UPDATE CASCADE;
      END IF;
    END $$;
  `);
}

// ─── Fallback file helpers ─────────────────────────────────────────────────────
async function saveFallbackCustomer(obj: any) {
  try {
    await fs.mkdir(FALLBACK_DIR, { recursive: true });
    let arr: any[] = [];
    try {
      const txt = await fs.readFile(FALLBACK_FILE, 'utf8');
      arr = JSON.parse(txt || '[]');
    } catch {
      arr = [];
    }
    const idx = arr.findIndex((c: any) => c.phone_number === obj.phone_number);
    if (idx >= 0) {
      arr[idx] = { ...arr[idx], ...obj, _updated_at: new Date().toISOString() };
    } else {
      arr.push({ ...obj, _saved_at: new Date().toISOString() });
    }
    await fs.writeFile(FALLBACK_FILE, JSON.stringify(arr, null, 2), 'utf8');
  } catch (e) {
    console.error('Failed to save fallback customer:', e);
  }
}

// ─── POST /api/customers — upsert customer record ─────────────────────────────
export async function upsertCustomerHandler(request: Request) {
  try {
    const body = await request.json();
    const {
      phone_number,
      name             = null,
      last_message     = null,
      last_order_id    = null,
      last_order_status = null,
      last_transaction_ref = null,
      email            = null,
      cnic             = null,
    } = body;

    if (!phone_number) {
      return NextResponse.json({ error: 'Missing phone_number' }, { status: 400 });
    }

    const now = new Date();

    try {
      await ensureSchema();
    } catch (schemaErr) {
      console.error('Schema sync warning (continuing anyway):', schemaErr);
    }

    try {
      const res = await db.execute(sql`
        INSERT INTO customers
          (phone_number, name, email, cnic, first_seen, last_seen, message_count,
           last_message, last_order_id, last_order_status, last_transaction_ref)
        VALUES
          (${phone_number}, ${name}, ${email}, ${cnic}, ${now}, ${now}, 1,
           ${last_message}, ${last_order_id}, ${last_order_status}, ${last_transaction_ref})
        ON CONFLICT (phone_number) DO UPDATE SET
          last_seen            = EXCLUDED.last_seen,
          message_count        = customers.message_count + 1,
          name                 = COALESCE(EXCLUDED.name,                 customers.name),
          email                = COALESCE(EXCLUDED.email,                customers.email),
          cnic                 = COALESCE(EXCLUDED.cnic,                 customers.cnic),
          last_message         = COALESCE(EXCLUDED.last_message,         customers.last_message),
          last_order_id        = COALESCE(EXCLUDED.last_order_id,        customers.last_order_id),
          last_order_status    = COALESCE(EXCLUDED.last_order_status,    customers.last_order_status),
          last_transaction_ref = COALESCE(EXCLUDED.last_transaction_ref, customers.last_transaction_ref)
        RETURNING *
      `);

      return NextResponse.json({ ok: true, customer: (res as any).rows?.[0] ?? null });
    } catch (dbErr: any) {
      console.error('Database UPSERT failed:', dbErr);
      await saveFallbackCustomer({
        phone_number, name, last_message,
        last_order_id, last_order_status, last_transaction_ref,
      });
      return NextResponse.json({ ok: true, fallback: true, message: 'Saved locally due to DB error', error: dbErr?.message });
    }
  } catch (reqErr: any) {
    console.error('Request processing error in upsertCustomerHandler:', reqErr);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

// ─── GET /api/customers?phone=<number> — full profile with orders + transactions
export async function getCustomerHandler(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const phone = searchParams.get('phone')?.trim() || '';

    if (!phone) {
      return NextResponse.json({ error: 'Missing phone parameter' }, { status: 400 });
    }

    try {
      await ensureSchema();
    } catch (e) {
      console.warn('Schema sync check failed in GET:', e);
    }

    // 1. Customer record
    const custRes = await db.execute(sql`
      SELECT * FROM customers WHERE phone_number = ${phone} LIMIT 1
    `);
    const customer = (custRes as any).rows?.[0] ?? null;

    // 2. Orders linked via FK (sender_number = phone)
    let orders: any[] = [];
    try {
      const ordersRes = await db.execute(sql`
        SELECT id, order_id, product, quantity, address, status, created_at
        FROM   orders
        WHERE  sender_number = ${phone}
        ORDER  BY created_at DESC
        LIMIT  10
      `);
      orders = (ordersRes as any).rows ?? [];
    } catch (e) {
      console.warn('Orders query failed:', e);
    }

    // 3. Transactions linked via FK (sender_number = phone)
    let transactions: any[] = [];
    try {
      const txRes = await db.execute(sql`
        SELECT id, transaction_id, sender_name, receiver_name, amount,
               date, time, bank_or_service, status, created_at
        FROM   transaction_data
        WHERE  sender_number = ${phone}
        ORDER  BY created_at DESC
        LIMIT  10
      `);
      transactions = (txRes as any).rows ?? [];
    } catch (e) {
      console.warn('Transactions query failed:', e);
    }

    return NextResponse.json({
      ok:           true,
      is_returning: !!customer,
      customer,
      orders,
      transactions,
    });
  } catch (err: any) {
    console.error('Customer lookup failed:', err?.message || err);
    return NextResponse.json({ error: 'Customer lookup failed', details: err?.message }, { status: 500 });
  }
}


export default upsertCustomerHandler;
