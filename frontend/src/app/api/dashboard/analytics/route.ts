import { NextResponse } from 'next/server';
import { db } from '../../../../db/dbClient';
import { sql } from 'drizzle-orm';

export async function GET() {
  try {
    // 1. Summary counts
    const [custCount, orderCount, txCount] = await Promise.all([
      db.execute(sql`SELECT COUNT(*) as total FROM customers`),
      db.execute(sql`SELECT COUNT(*) as total FROM orders`),
      db.execute(sql`SELECT COUNT(*) as total FROM transaction_data`),
    ]);

    // 2. Total revenue from successful transactions.
    // Use regexp_match so formatted values like "Rs. 1,500" and "PKR 2500.50" can still be summed safely.
    const revenueRes = await db.execute(sql`
      SELECT COALESCE(SUM(
        COALESCE((regexp_match(REPLACE(amount, ',', ''), '([0-9]+(?:\.[0-9]+)?)'))[1], '0')::numeric
      ), 0) as total
      FROM transaction_data
      WHERE status ILIKE '%success%'
        AND amount IS NOT NULL
        AND amount ~ '[0-9]'
    `);

    // 3. Last 7 days transaction volume (group by date)
    const volumeRes = await db.execute(sql`
      SELECT DATE(created_at) as day, COUNT(*) as count
      FROM transaction_data
      WHERE created_at >= NOW() - INTERVAL '7 days'
      GROUP BY DATE(created_at)
      ORDER BY day ASC
    `);

    // 4. Status breakdown
    const statusRes = await db.execute(sql`
      SELECT COALESCE(status, 'Unknown') as status, COUNT(*) as count
      FROM transaction_data
      GROUP BY status
      ORDER BY count DESC
    `);

    // 5. Top banks / services
    const banksRes = await db.execute(sql`
      SELECT bank_or_service, COUNT(*) as count
      FROM transaction_data
      WHERE bank_or_service IS NOT NULL
      GROUP BY bank_or_service
      ORDER BY count DESC
      LIMIT 6
    `);

    // 6. New customers in last 7 days
    const newCustRes = await db.execute(sql`
      SELECT COUNT(*) as total
      FROM customers
      WHERE created_at >= NOW() - INTERVAL '7 days'
    `);

    // 7. Top customers by message count
    const topCustRes = await db.execute(sql`
      SELECT phone_number, name, message_count, last_seen, last_order_id, created_at
      FROM customers
      ORDER BY message_count DESC
      LIMIT 5
    `);

    return NextResponse.json({
      ok: true,
      summary: {
        customers:       parseInt((custCount  as any).rows?.[0]?.total  ?? '0', 10),
        orders:          parseInt((orderCount as any).rows?.[0]?.total  ?? '0', 10),
        transactions:    parseInt((txCount    as any).rows?.[0]?.total  ?? '0', 10),
        revenue:         parseFloat((revenueRes as any).rows?.[0]?.total ?? '0'),
        newCustomers:    parseInt((newCustRes  as any).rows?.[0]?.total  ?? '0', 10),
      },
      volumeByDay:     (volumeRes  as any).rows ?? [],
      statusBreakdown: (statusRes  as any).rows ?? [],
      topBanks:        (banksRes   as any).rows ?? [],
      topCustomers:    (topCustRes as any).rows ?? [],
    });
  } catch (err: any) {
    console.error('Analytics fetch failed:', err?.message || err);
    return NextResponse.json({
      ok: false,
      error: 'Failed to fetch analytics',
      summary: { customers: 0, orders: 0, transactions: 0, revenue: 0, newCustomers: 0 },
      volumeByDay: [],
      statusBreakdown: [],
      topBanks: [],
      topCustomers: [],
    }, { status: 500 });
  }
}
