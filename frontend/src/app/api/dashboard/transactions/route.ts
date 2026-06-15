import { NextRequest, NextResponse } from 'next/server';
import { db } from '../../../../db/dbClient';
import { sql } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const page   = Math.max(1, parseInt(searchParams.get('page')  || '1', 10));
  const limit  = Math.min(100, parseInt(searchParams.get('limit') || '25', 10));
  const offset = (page - 1) * limit;
  const search = (searchParams.get('search') || '').trim();

  try {
    const whereClause = search
      ? sql`WHERE transaction_id ILIKE ${'%' + search + '%'}
               OR sender_name    ILIKE ${'%' + search + '%'}
               OR receiver_name  ILIKE ${'%' + search + '%'}
               OR bank_or_service ILIKE ${'%' + search + '%'}
               OR status         ILIKE ${'%' + search + '%'}
               OR sender_number  ILIKE ${'%' + search + '%'}`
      : sql``;

    const rowsRes = await db.execute(sql`
      SELECT id, transaction_id, sender_name, receiver_name,
             amount, date, time, bank_or_service, status, sender_number, created_at
      FROM   transaction_data
      ${whereClause}
      ORDER  BY created_at DESC
      LIMIT  ${limit} OFFSET ${offset}
    `);

    const countRes = await db.execute(sql`
      SELECT COUNT(*) as total FROM transaction_data ${whereClause}
    `);

    const rows  = (rowsRes as any).rows  ?? [];
    const total = parseInt((countRes as any).rows?.[0]?.total ?? '0', 10);

    return NextResponse.json({ ok: true, transactions: rows, total, page, limit });
  } catch (err: any) {
    console.error('Dashboard transactions fetch failed:', err?.message || err);
    return NextResponse.json({ ok: false, error: 'Failed to fetch transactions', transactions: [], total: 0 }, { status: 500 });
  }
}
