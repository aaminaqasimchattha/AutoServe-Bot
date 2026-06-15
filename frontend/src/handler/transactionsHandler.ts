import { NextResponse } from 'next/server';
import { db } from '../db/dbClient';
import { transactions } from '../schema/transactions';
import { eq, desc } from 'drizzle-orm';
import fs from 'fs/promises';
import path from 'path';

const FALLBACK_DIR = path.resolve(process.cwd(), './data');
const FALLBACK_FILE = path.join(FALLBACK_DIR, 'transactions_fallback.json');

async function saveFallbackTransaction(obj: any) {
  try {
    await fs.mkdir(FALLBACK_DIR, { recursive: true });
    let arr: any[] = [];
    try {
      const txt = await fs.readFile(FALLBACK_FILE, 'utf8');
      arr = JSON.parse(txt || '[]');
    } catch (e) {
      arr = [];
    }
    arr.push({ ...obj, _saved_at: new Date().toISOString() });
    await fs.writeFile(FALLBACK_FILE, JSON.stringify(arr, null, 2), 'utf8');
  } catch (e) {
    console.error('Failed to save fallback transaction:', e);
  }
}

// ─── POST: save a new transaction ─────────────────────────────────────────────
export async function saveTransactionHandler(request: Request) {
  const body = await request.json();
  const {
    transaction_id   = null,
    sender_name      = null,
    receiver_name    = null,
    amount           = null,
    date             = null,
    time             = null,
    bank_or_service  = null,
    status           = null,
    raw_text         = null,
    sender_number    = null,
  } = body;

  if (!raw_text && !transaction_id) {
    return NextResponse.json(
      { error: 'Missing transaction data (raw_text or transaction_id required)' },
      { status: 400 }
    );
  }

  try {
    const res = await db.insert(transactions).values({
      transaction_id,
      sender_name,
      receiver_name,
      amount,
      date,
      time,
      bank_or_service,
      status: status || 'Unknown',
      raw_text,
      sender_number,
    }).returning();

    const insertedId =
      Array.isArray(res) && res[0] && typeof res[0].id !== 'undefined'
        ? res[0].id
        : null;
    return NextResponse.json({ ok: true, id: insertedId, inserted: res });
  } catch (err: any) {
    console.error('Transaction insert failed, saving fallback:', err?.message || err);
    await saveFallbackTransaction({
      transaction_id, sender_name, receiver_name, amount,
      date, time, bank_or_service, status: status || 'Unknown',
      raw_text, sender_number,
    });
    return NextResponse.json({ ok: true, fallback: true, message: 'Saved locally due to DB error' });
  }
}

// ─── GET: fetch transactions by phone number ───────────────────────────────────
/**
 * GET /api/save-transaction?phone=<sender_number>
 * Queries transaction_data table directly — no customers table needed.
 * Returns all transactions for the given phone number.
 */
export async function getTransactionsByPhone(request: Request) {
  const { searchParams } = new URL(request.url);
  const phone = searchParams.get('phone')?.trim() || '';

  if (!phone) {
    return NextResponse.json({ error: 'Missing phone parameter' }, { status: 400 });
  }

  try {
    const rows = await db
      .select({
        id:              transactions.id,
        transaction_id:  transactions.transaction_id,
        sender_name:     transactions.sender_name,
        receiver_name:   transactions.receiver_name,
        amount:          transactions.amount,
        date:            transactions.date,
        time:            transactions.time,
        bank_or_service: transactions.bank_or_service,
        status:          transactions.status,
        created_at:      transactions.created_at,
      })
      .from(transactions)
      .where(eq(transactions.sender_number, phone))
      .orderBy(desc(transactions.created_at))
      .limit(10);

    return NextResponse.json({ ok: true, transactions: rows });
  } catch (err: any) {
    console.error('Transaction lookup failed:', err?.message || err);
    return NextResponse.json({ error: 'Transaction lookup failed' }, { status: 500 });
  }
}

export default saveTransactionHandler;
