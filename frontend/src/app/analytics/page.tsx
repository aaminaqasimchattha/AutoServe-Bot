'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Summary {
  customers: number;
  orders: number;
  transactions: number;
  revenue: number;
  newCustomers: number;
}
interface VolumeDay { day: string; count: string; }
interface StatusRow  { status: string; count: string; }
interface BankRow    { bank_or_service: string; count: string; }
interface Customer   {
  phone_number: string;
  name: string | null;
  message_count: number;
  last_seen: string;
  last_order_id: string | null;
  created_at: string;
}
interface AnalyticsData {
  summary:         Summary;
  volumeByDay:     VolumeDay[];
  statusBreakdown: StatusRow[];
  topBanks:        BankRow[];
  topCustomers:    Customer[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmtNum(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}
function fmtDate(ts: string) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-PK', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtShortDate(ts: string) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-PK', { day: '2-digit', month: 'short' });
}

// ─── Stat Cards ───────────────────────────────────────────────────────────────
function StatCard({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub?: string; color: string;
}) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'hsl(var(--muted-foreground))', marginBottom: '0.4rem' }}>
            {label}
          </p>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, lineHeight: 1, color: 'hsl(var(--foreground))' }}>
            {value}
          </p>
          {sub && <p style={{ fontSize: '0.7rem', color: 'hsl(var(--muted-foreground))', marginTop: '0.35rem' }}>{sub}</p>}
        </div>
        <div style={{
          width: 44, height: 44, borderRadius: '0.75rem', flexShrink: 0,
          background: `hsl(${color}/0.12)`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: `hsl(${color})`,
        }}>
          {icon}
        </div>
      </div>
    </div>
  );
}

// ─── Bar Chart (7-day volume) ─────────────────────────────────────────────────
function BarChart({ data }: { data: VolumeDay[] }) {
  const maxCount = Math.max(...data.map(d => parseInt(d.count, 10)), 1);
  const chartH   = 120;

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.625rem', height: chartH + 28, paddingBottom: 24, minWidth: 280 }}>
        {data.map((d, i) => {
          const h = Math.max(6, Math.round((parseInt(d.count, 10) / maxCount) * chartH));
          return (
            <div key={d.day} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: '0.65rem', color: 'hsl(var(--muted-foreground))' }}>{d.count}</span>
              <div
                className="bar-animated"
                style={{
                  width: '100%', height: h, borderRadius: '4px 4px 0 0',
                  background: `linear-gradient(to top, hsl(var(--primary)), hsl(var(--accent)/0.7))`,
                  animationDelay: `${i * 0.08}s`,
                  position: 'relative',
                }}
                title={`${d.day}: ${d.count} tx`}
              />
              <span style={{ fontSize: '0.6rem', color: 'hsl(var(--muted-foreground))', whiteSpace: 'nowrap' }}>
                {fmtShortDate(d.day)}
              </span>
            </div>
          );
        })}
        {data.length === 0 && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'hsl(var(--muted-foreground))', fontSize: '0.8rem' }}>
            No data for the last 7 days
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Donut Chart (status breakdown) ──────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  successful: 'hsl(var(--success))',
  failed:     'hsl(var(--danger))',
  pending:    'hsl(var(--warning))',
  unknown:    'hsl(var(--muted-foreground))',
};

function DonutChart({ data }: { data: StatusRow[] }) {
  const total = data.reduce((s, d) => s + parseInt(d.count, 10), 0);
  if (total === 0) {
    return <div className="empty-state" style={{ padding: '2rem' }}>No transaction data</div>;
  }

  const cx = 60; const cy = 60; const r = 46; const stroke = 18;
  const circ  = 2 * Math.PI * r;
  let offset  = 0;

  const slices = data.map(d => {
    const pct   = parseInt(d.count, 10) / total;
    const dash  = pct * circ;
    const gap   = circ - dash;
    const start = offset;
    offset     += dash;
    const color = STATUS_COLORS[(d.status || 'unknown').toLowerCase()] || 'hsl(var(--muted-foreground))';
    return { ...d, dash, gap, offset: start, color, pct };
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
      <svg viewBox="0 0 120 120" width={120} height={120} style={{ flexShrink: 0 }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="hsl(var(--border)/0.4)" strokeWidth={stroke}/>
        {slices.map((s, i) => (
          <circle
            key={i}
            className="donut-animated"
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={stroke}
            strokeDasharray={`${s.dash} ${s.gap}`}
            strokeDashoffset={circ / 4 - s.offset}
            style={{ transition: 'stroke-dashoffset 0.5s ease', animationDelay: `${i * 0.15}s` }}
          />
        ))}
        <text x={cx} y={cy - 5} textAnchor="middle" fontSize="18" fontWeight="700" fill="hsl(var(--foreground))">{fmtNum(total)}</text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">transactions</text>
      </svg>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {slices.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }}/>
            <span style={{ fontSize: '0.78rem', color: 'hsl(var(--foreground))' }}>{s.status || 'Unknown'}</span>
            <span style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))', marginLeft: 'auto', paddingLeft: '0.5rem' }}>
              {s.count} ({(s.pct * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Top Banks Bar ────────────────────────────────────────────────────────────
function TopBanks({ data }: { data: BankRow[] }) {
  const maxCount = Math.max(...data.map(d => parseInt(d.count, 10)), 1);
  if (data.length === 0) {
    return <div className="empty-state" style={{ padding: '2rem' }}>No bank data</div>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {data.map((b, i) => {
        const pct = (parseInt(b.count, 10) / maxCount) * 100;
        return (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'hsl(var(--foreground))' }}>{b.bank_or_service}</span>
              <span style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))' }}>{b.count} tx</span>
            </div>
            <div style={{ height: 6, background: 'hsl(var(--border)/0.4)', borderRadius: 9999, overflow: 'hidden' }}>
              <div
                style={{
                  width: `${pct}%`, height: '100%',
                  background: `linear-gradient(to right, hsl(var(--primary)), hsl(var(--accent)))`,
                  borderRadius: 9999,
                  transition: 'width 1s ease',
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Customer Table ───────────────────────────────────────────────────────────
interface CustFull {
  id: number;
  phone_number: string;
  name: string | null;
  message_count: number;
  last_seen: string;
  last_order_id: string | null;
  last_order_status: string | null;
  last_transaction_ref: string | null;
  email: string | null;
  created_at: string;
}

function CustomersTable() {
  const [custs, setCusts]     = useState<CustFull[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [search, setSearch]   = useState('');
  const [loading, setLoading] = useState(false);
  const limit = 20;

  const fetchCusts = useCallback(async () => {
    setLoading(true);
    try {
      // Use the existing customers API — build a custom fetch
      const params = new URLSearchParams({ page: String(page), limit: String(limit), search });
      const res  = await fetch(`/api/dashboard/customers?${params}`);
      const data = await res.json();
      setCusts(data.customers ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setCusts([]);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => { fetchCusts(); }, [fetchCusts]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border/40">
        <div style={{ position: 'relative', flex: 1, maxWidth: 340 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'hsl(var(--muted-foreground))' }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            id="customers-search"
            className="search-input"
            placeholder="Search by phone, name, email…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>
          {total} customer{total !== 1 ? 's' : ''}
        </div>
        <button
          id="customers-refresh-btn"
          onClick={fetchCusts}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            padding: '0.45rem 0.875rem', borderRadius: '0.5rem',
            background: 'hsl(var(--primary)/0.12)', color: 'hsl(var(--primary))',
            border: '1px solid hsl(var(--primary)/0.25)', fontSize: '0.78rem',
            fontWeight: 500, cursor: 'pointer',
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          Refresh
        </button>
      </div>

      <div className="table-scroll">
        <table className="dash-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Phone</th>
              <th>Name</th>
              <th>Email</th>
              <th>Messages</th>
              <th>Last Order</th>
              <th>Last Seen</th>
              <th>Joined</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8}><div className="empty-state"><div className="spinner" style={{ margin: '0 auto' }}/><span>Loading customers…</span></div></td></tr>
            ) : custs.length === 0 ? (
              <tr><td colSpan={8}>
                <div className="empty-state">
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.4 }}>
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                  </svg>
                  <p>No customers found</p>
                  {search && <p style={{ fontSize: '0.75rem' }}>Try clearing the search filter</p>}
                </div>
              </td></tr>
            ) : custs.map(c => (
              <tr key={c.id}>
                <td style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.75rem' }}>#{c.id}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                      background: 'hsl(var(--primary)/0.15)', display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontSize: '0.65rem', fontWeight: 700, color: 'hsl(var(--primary))',
                    }}>
                      {(c.name || c.phone_number || '?')[0].toUpperCase()}
                    </div>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{c.phone_number}</span>
                  </div>
                </td>
                <td style={{ fontWeight: 500 }}>{c.name || <span style={{ color: 'hsl(var(--muted-foreground))' }}>—</span>}</td>
                <td style={{ fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>{c.email || '—'}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <div style={{
                      background: 'hsl(var(--accent)/0.12)', color: 'hsl(var(--accent))',
                      padding: '0.1rem 0.5rem', borderRadius: 9999, fontSize: '0.75rem', fontWeight: 600,
                    }}>
                      {c.message_count}
                    </div>
                  </div>
                </td>
                <td>
                  {c.last_order_id
                    ? <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'hsl(var(--primary))' }}>{c.last_order_id}</span>
                    : <span style={{ color: 'hsl(var(--muted-foreground))' }}>—</span>}
                </td>
                <td style={{ fontSize: '0.78rem' }}>{fmtDate(c.last_seen)}</td>
                <td style={{ fontSize: '0.78rem', color: 'hsl(var(--muted-foreground))' }}>{fmtDate(c.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 px-5 py-4 border-t border-border/40">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{
              padding: '0.35rem 0.75rem', borderRadius: '0.4rem',
              background: 'hsl(var(--secondary))', border: '1px solid hsl(var(--border)/0.5)',
              color: page === 1 ? 'hsl(var(--muted-foreground))' : 'hsl(var(--foreground))',
              cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: '0.78rem',
            }}
          >← Prev</button>
          <span style={{ fontSize: '0.78rem', color: 'hsl(var(--muted-foreground))' }}>Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{
              padding: '0.35rem 0.75rem', borderRadius: '0.4rem',
              background: 'hsl(var(--secondary))', border: '1px solid hsl(var(--border)/0.5)',
              color: page === totalPages ? 'hsl(var(--muted-foreground))' : 'hsl(var(--foreground))',
              cursor: page === totalPages ? 'not-allowed' : 'pointer', fontSize: '0.78rem',
            }}
          >Next →</button>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [data, setData]       = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [custTab, setCustTab] = useState<'table' | 'top'>('table');

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res  = await fetch('/api/dashboard/analytics');
      const json = await res.json();
      if (!res.ok || json?.ok === false) {
        throw new Error(json?.error || 'Failed to fetch analytics data');
      }
      setData(json);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : 'Could not load analytics data. Check your database connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const summary = data?.summary ?? { customers: 0, orders: 0, transactions: 0, revenue: 0, newCustomers: 0 };

  return (
    <div className="min-h-screen bg-gradient-mesh">
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="animate-fade-in-up flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Analytics & User Records</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Real-time stats and customer insights from your WhatsApp bot.
            </p>
          </div>
          <button
            id="analytics-refresh-btn"
            onClick={fetchAnalytics}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              padding: '0.5rem 1rem', borderRadius: '0.625rem',
              background: 'hsl(var(--primary)/0.12)', color: 'hsl(var(--primary))',
              border: '1px solid hsl(var(--primary)/0.25)', fontSize: '0.8rem',
              fontWeight: 500, cursor: 'pointer',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Refresh
          </button>
        </div>

        {error && (
          <div style={{
            padding: '1rem 1.25rem', borderRadius: '0.75rem',
            background: 'hsl(var(--danger)/0.1)', border: '1px solid hsl(var(--danger)/0.3)',
            color: 'hsl(var(--danger))', fontSize: '0.85rem',
          }}>
            ⚠ {error}
          </div>
        )}

        {/* ─── Summary Cards ─── */}
        <div
          className="animate-fade-in-up"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', animationDelay: '0.05s' }}
        >
          <StatCard
            label="Total Customers"
            value={loading ? '…' : fmtNum(summary.customers)}
            sub={`+${summary.newCustomers} this week`}
            color="var(--primary)"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>}
          />
          <StatCard
            label="Total Orders"
            value={loading ? '…' : fmtNum(summary.orders)}
            sub="All time"
            color="var(--accent)"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>}
          />
          <StatCard
            label="Transactions"
            value={loading ? '…' : fmtNum(summary.transactions)}
            sub="Payment receipts"
            color="var(--accent-secondary)"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>}
          />
          <StatCard
            label="Revenue (PKR)"
            value={loading ? '…' : fmtNum(summary.revenue)}
            sub="Successful transactions"
            color="var(--success)"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>}
          />
          <StatCard
            label="New Customers"
            value={loading ? '…' : fmtNum(summary.newCustomers)}
            sub="Last 7 days"
            color="var(--warning)"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>}
          />
        </div>

        {/* ─── Charts Row ─── */}
        <div
          className="animate-fade-in-up"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', animationDelay: '0.12s' }}
        >
          {/* Volume Chart */}
          <div className="glass-card rounded-2xl p-5">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'hsl(var(--foreground))' }}>Transaction Volume</h2>
                <p style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))' }}>Last 7 days</p>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--primary))" strokeWidth="2">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            {loading ? <div className="empty-state"><div className="spinner" style={{ margin: '0 auto' }}/></div>
                     : <BarChart data={data?.volumeByDay ?? []} />}
          </div>

          {/* Status Donut */}
          <div className="glass-card rounded-2xl p-5">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'hsl(var(--foreground))' }}>Status Breakdown</h2>
                <p style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))' }}>All transactions</p>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--accent))" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
              </svg>
            </div>
            {loading ? <div className="empty-state"><div className="spinner" style={{ margin: '0 auto' }}/></div>
                     : <DonutChart data={data?.statusBreakdown ?? []} />}
          </div>

          {/* Top Banks */}
          <div className="glass-card rounded-2xl p-5">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'hsl(var(--foreground))' }}>Top Banks & Services</h2>
                <p style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))' }}>By transaction count</p>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="hsl(var(--accent-secondary))" strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
              </svg>
            </div>
            {loading ? <div className="empty-state"><div className="spinner" style={{ margin: '0 auto' }}/></div>
                     : <TopBanks data={data?.topBanks ?? []} />}
          </div>
        </div>

        {/* ─── Customer Records ─── */}
        <div className="animate-fade-in-up glass-card rounded-2xl overflow-hidden" style={{ animationDelay: '0.2s' }}>
          {/* Header */}
          <div className="flex items-center gap-3 px-5 pt-4 pb-3 border-b border-border/40">
            <div>
              <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'hsl(var(--foreground))' }}>Customer Records</h2>
              <p style={{ fontSize: '0.72rem', color: 'hsl(var(--muted-foreground))' }}>All WhatsApp users who interacted with the bot</p>
            </div>
            <div className="flex items-center gap-1 ml-auto">
              <button
                id="tab-all-customers"
                className={`tab-btn${custTab === 'table' ? ' active' : ''}`}
                onClick={() => setCustTab('table')}
                style={{ fontSize: '0.78rem' }}
              >
                All Customers
              </button>
              <button
                id="tab-top-customers"
                className={`tab-btn${custTab === 'top' ? ' active' : ''}`}
                onClick={() => setCustTab('top')}
                style={{ fontSize: '0.78rem' }}
              >
                Top Engaged
              </button>
            </div>
          </div>

          {custTab === 'table' ? (
            <CustomersTable />
          ) : (
            /* Top Customers */
            <div className="table-scroll">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Phone</th>
                    <th>Name</th>
                    <th>Messages</th>
                    <th>Last Order</th>
                    <th>Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={6}><div className="empty-state"><div className="spinner" style={{ margin: '0 auto' }}/></div></td></tr>
                  ) : (data?.topCustomers ?? []).length === 0 ? (
                    <tr><td colSpan={6}>
                      <div className="empty-state">
                        <p>No customer data yet</p>
                      </div>
                    </td></tr>
                  ) : (data?.topCustomers ?? []).map((c, i) => (
                    <tr key={c.phone_number}>
                      <td>
                        <div style={{
                          width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: i === 0 ? 'hsl(38 92% 50%/0.15)' : i === 1 ? 'hsl(var(--muted-foreground)/0.1)' : i === 2 ? 'hsl(25 90% 55%/0.1)' : 'hsl(var(--border)/0.4)',
                          color: i === 0 ? 'hsl(38 92% 50%)' : i === 1 ? 'hsl(var(--foreground))' : i === 2 ? 'hsl(25 90% 55%)' : 'hsl(var(--muted-foreground))',
                          fontSize: '0.72rem', fontWeight: 700,
                        }}>
                          {i + 1}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{c.phone_number}</td>
                      <td style={{ fontWeight: 500 }}>{c.name || '—'}</td>
                      <td>
                        <span style={{ background: 'hsl(var(--accent)/0.12)', color: 'hsl(var(--accent))', padding: '0.1rem 0.5rem', borderRadius: 9999, fontSize: '0.75rem', fontWeight: 600 }}>
                          {c.message_count}
                        </span>
                      </td>
                      <td>
                        {c.last_order_id
                          ? <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'hsl(var(--primary))' }}>{c.last_order_id}</span>
                          : <span style={{ color: 'hsl(var(--muted-foreground))' }}>—</span>}
                      </td>
                      <td style={{ fontSize: '0.78rem' }}>{fmtDate(c.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
