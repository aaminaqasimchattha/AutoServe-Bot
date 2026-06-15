import { NextRequest, NextResponse } from 'next/server';
import { db } from '../../../../db/dbClient';
import { sql } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const page  = Math.max(1, parseInt(searchParams.get('page')  || '1', 10));
  const limit = Math.min(100, parseInt(searchParams.get('limit') || '25', 10));
  const offset = (page - 1) * limit;
  const search = (searchParams.get('search') || '').trim();

  try {
    const whereClause = search
      ? sql`WHERE order_id ILIKE ${'%' + search + '%'}
               OR product  ILIKE ${'%' + search + '%'}
               OR status   ILIKE ${'%' + search + '%'}
               OR sender_number ILIKE ${'%' + search + '%'}`
      : sql``;

    const rowsRes = await db.execute(sql`
      SELECT id, order_id, product, quantity, address, status, sender_number, created_at
      FROM   orders
      ${whereClause}
      ORDER  BY created_at DESC
      LIMIT  ${limit} OFFSET ${offset}
    `);

    const countRes = await db.execute(sql`
      SELECT COUNT(*) as total FROM orders ${whereClause}
    `);

    const rows  = (rowsRes as any).rows  ?? [];
    const total = parseInt((countRes as any).rows?.[0]?.total ?? '0', 10);

    return NextResponse.json({ ok: true, orders: rows, total, page, limit });
  } catch (err: any) {
    console.error('Dashboard orders fetch failed:', err?.message || err);
    return NextResponse.json({ ok: false, error: 'Failed to fetch orders', orders: [], total: 0 }, { status: 500 });
  }
}
