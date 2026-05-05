import { NextResponse } from 'next/server';
import { db } from '../db/dbClient';
import { transactions } from '../schema/transactions';
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

export async function saveTransactionHandler(request: Request) {
  const body = await request.json();
  const {
    transaction_id = null,
    sender_name = null,
    receiver_name = null,
    amount = null,
    date = null,
    time = null,
    bank_or_service = null,
    status = null,
    raw_text = null,
    sender_number = null,
  } = body;

  if (!raw_text && !transaction_id) {
    return NextResponse.json({ error: 'Missing transaction data (raw_text or transaction_id required)' }, { status: 400 });
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

    const insertedId = Array.isArray(res) && res[0] && typeof res[0].id !== 'undefined' ? res[0].id : null;
    return NextResponse.json({ ok: true, id: insertedId, inserted: res });
  } catch (err: any) {
    console.error('Transaction insert failed, saving fallback:', err?.message || err);
    await saveFallbackTransaction({ transaction_id, sender_name, receiver_name, amount, date, time, bank_or_service, status: status || 'Unknown', raw_text, sender_number });
    return NextResponse.json({ ok: true, fallback: true, message: 'Saved locally due to DB error' });
  }
}

export default saveTransactionHandler;
