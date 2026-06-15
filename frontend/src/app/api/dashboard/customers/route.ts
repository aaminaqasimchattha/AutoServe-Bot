import { NextRequest, NextResponse } from 'next/server';
import { db } from '../../../../db/dbClient';
import { sql } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const page   = Math.max(1, parseInt(searchParams.get('page')  || '1', 10));
  const limit  = Math.min(100, parseInt(searchParams.get('limit') || '20', 10));
  const offset = (page - 1) * limit;
  const search = (searchParams.get('search') || '').trim();

  try {
    const whereClause = search
      ? sql`WHERE phone_number ILIKE ${'%' + search + '%'}
               OR name         ILIKE ${'%' + search + '%'}
               OR email        ILIKE ${'%' + search + '%'}`
      : sql``;

    const rowsRes = await db.execute(sql`
      SELECT id, phone_number, name, email, message_count,
             last_seen, last_order_id, last_order_status,
             last_transaction_ref, created_at
      FROM   customers
      ${whereClause}
      ORDER  BY message_count DESC, last_seen DESC
      LIMIT  ${limit} OFFSET ${offset}
    `);

    const countRes = await db.execute(sql`
      SELECT COUNT(*) as total FROM customers ${whereClause}
    `);

    const rows  = (rowsRes  as any).rows ?? [];
    const total = parseInt((countRes as any).rows?.[0]?.total ?? '0', 10);

    return NextResponse.json({ ok: true, customers: rows, total, page, limit });
  } catch (err: any) {
    console.error('Dashboard customers fetch failed:', err?.message || err);
    return NextResponse.json({ ok: false, error: 'Failed to fetch customers', customers: [], total: 0 }, { status: 500 });
  }
}
