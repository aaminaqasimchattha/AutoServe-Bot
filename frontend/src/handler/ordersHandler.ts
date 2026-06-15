import { NextResponse } from 'next/server';
import { db } from '../db/dbClient';
import { orders } from '../schema/users';
import fs from 'fs/promises';
import path from 'path';

const FALLBACK_DIR = path.resolve(process.cwd(), './data');
const FALLBACK_FILE = path.join(FALLBACK_DIR, 'orders_fallback.json');

async function saveFallbackOrder(obj: any) {
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
    console.error('Failed to save fallback order:', e);
  }
}

export async function uploadOrderHandler(request: Request) {
  const body = await request.json();
  const { order_id, product, quantity, address, status } = body;

  if (!order_id || !product || !quantity || !address) {
    return NextResponse.json({ error: 'Missing order fields' }, { status: 400 });
  }

  try {
    const res = await db.insert(orders).values({
      order_id,
      product,
      quantity: Number(quantity),
      address,
      status: status || 'Processing',
    }).returning();

    return NextResponse.json({ ok: true, inserted: res });
  } catch (err: any) {
    console.error('Order insert failed, saving fallback:', err?.message || err);
    // Save to local fallback file so orders are not lost
    await saveFallbackOrder({ order_id, product, quantity, address, status: status || 'Processing' });
    return NextResponse.json({ ok: true, fallback: true, message: 'Saved locally due to DB error' });
  }
}

import { eq } from 'drizzle-orm';
export async function getOrderHandler(request: Request) {
  const { searchParams } = new URL(request.url);
  const order_id = searchParams.get('order_id');
  if (!order_id) {
    return NextResponse.json({ error: 'Missing order_id' }, { status: 400 });
  }
  
  try {
    const results = await db.select().from(orders).where(eq(orders.order_id, order_id)).limit(1);
    if (results.length > 0) {
      return NextResponse.json({ ok: true, order: results[0] });
    } else {
      return NextResponse.json({ ok: false, error: 'Order not found' }, { status: 404 });
    }
  } catch (err: any) {
    console.error('Order fetch failed:', err?.message || err);
    return NextResponse.json({ error: 'Fetch failed' }, { status: 500 });
  }
}

export default uploadOrderHandler;
