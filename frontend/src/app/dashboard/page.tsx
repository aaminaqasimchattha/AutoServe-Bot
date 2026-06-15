'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Order {
  id: number;
  order_id: string;
  product: string;
  quantity: number;
  address: string;
  status: string;
  sender_number: string | null;
  created_at: string;
}

interface Transaction {
  id: number;
  transaction_id: string | null;
  sender_name: string | null;
  receiver_name: string | null;
  amount: string | null;
  date: string | null;
  time: string | null;
  bank_or_service: string | null;
  status: string | null;
  sender_number: string | null;
  created_at: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function statusBadge(status: string | null) {
  const s = (status || 'unknown').toLowerCase();
  let cls = 'badge badge-neutral';
  if (s.includes('success') || s.includes('complet') || s.includes('deliver') || s.includes('paid'))
    cls = 'badge badge-success';
  else if (s.includes('fail') || s.includes('declin') || s.includes('cancel'))
    cls = 'badge badge-danger';
  else if (s.includes('pend') || s.includes('process'))
    cls = 'badge badge-warning';
  return <span className={cls}>{status || 'Unknown'}</span>;
}

function fmtDate(ts: string) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-PK', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtTime(ts: string) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString('en-PK', { hour: '2-digit', minute: '2-digit' });
}

function Spinner() {
  return <div className="spinner" style={{ margin: '0 auto' }} />;
}

// ─── Orders Table ─────────────────────────────────────────────────────────────
function OrdersTable() {
  const [orders, setOrders]   = useState<Order[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [search, setSearch]   = useState('');
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<keyof Order>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const limit = 25;

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(limit), search });
      const res  = await fetch(`/api/dashboard/orders?${params}`);
      const data = await res.json();
      setOrders(data.orders ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  const sorted = [...orders].sort((a, b) => {
    const av = String(a[sortKey] ?? '');
    const bv = String(b[sortKey] ?? '');
    return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  function toggleSort(key: keyof Order) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  function SortIcon({ col }: { col: keyof Order }) {
    if (sortKey !== col) return <span style={{ opacity: 0.3 }}>↕</span>;
    return <span style={{ color: 'hsl(var(--primary))' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border/40">
        <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'hsl(var(--muted-foreground))' }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            id="orders-search"
            className="search-input"
            placeholder="Search by order ID, product, status…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>
          {total} order{total !== 1 ? 's' : ''}
        </div>
        <button
          id="orders-refresh-btn"
          onClick={fetchOrders}
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

      {/* Table */}
      <div className="table-scroll">
        <table className="dash-table">
          <thead>
            <tr>
              <th onClick={() => toggleSort('id')}># <SortIcon col="id"/></th>
              <th onClick={() => toggleSort('order_id')}>Order ID <SortIcon col="order_id"/></th>
              <th onClick={() => toggleSort('product')}>Product <SortIcon col="product"/></th>
              <th>Qty</th>
              <th>Address</th>
              <th onClick={() => toggleSort('status')}>Status <SortIcon col="status"/></th>
              <th>Customer</th>
              <th onClick={() => toggleSort('created_at')}>Date <SortIcon col="created_at"/></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8}><div className="empty-state"><Spinner/><span>Loading orders…</span></div></td></tr>
            ) : sorted.length === 0 ? (
              <tr><td colSpan={8}>
                <div className="empty-state">
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.4 }}>
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <path d="M3 9h18M9 21V9"/>
                  </svg>
                  <p>No orders found</p>
                  {search && <p style={{ fontSize: '0.75rem' }}>Try clearing the search filter</p>}
                </div>
              </td></tr>
            ) : sorted.map(o => (
              <tr key={o.id}>
                <td style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.75rem' }}>#{o.id}</td>
                <td>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'hsl(var(--primary))' }}>
                    {o.order_id}
                  </span>
                </td>
                <td style={{ fontWeight: 500 }}>{o.product}</td>
                <td style={{ color: 'hsl(var(--accent))' }}>{o.quantity}</td>
                <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'hsl(var(--muted-foreground))' }}>
                  {o.address}
                </td>
                <td>{statusBadge(o.status)}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>
                  {o.sender_number || '—'}
                </td>
                <td>
                  <div style={{ fontSize: '0.78rem' }}>{fmtDate(o.created_at)}</div>
                  <div style={{ fontSize: '0.7rem', color: 'hsl(var(--muted-foreground))' }}>{fmtTime(o.created_at)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
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
          <span style={{ fontSize: '0.78rem', color: 'hsl(var(--muted-foreground))' }}>
            Page {page} of {totalPages}
          </span>
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

// ─── Transactions Table ───────────────────────────────────────────────────────
function TransactionsTable() {
  const [txns, setTxns]       = useState<Transaction[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [search, setSearch]   = useState('');
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<keyof Transaction>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const limit = 25;

  const fetchTxns = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(limit), search });
      const res  = await fetch(`/api/dashboard/transactions?${params}`);
      const data = await res.json();
      setTxns(data.transactions ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setTxns([]);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => { fetchTxns(); }, [fetchTxns]);

  const sorted = [...txns].sort((a, b) => {
    const av = String(a[sortKey] ?? '');
    const bv = String(b[sortKey] ?? '');
    return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  function toggleSort(key: keyof Transaction) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  function SortIcon({ col }: { col: keyof Transaction }) {
    if (sortKey !== col) return <span style={{ opacity: 0.3 }}>↕</span>;
    return <span style={{ color: 'hsl(var(--primary))' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  const totalPages = Math.ceil(total / limit);

  function bankBadge(bank: string | null) {
    if (!bank) return <span style={{ color: 'hsl(var(--muted-foreground))' }}>—</span>;
    const colors: Record<string, string> = {
      Easypaisa: 'badge-success', JazzCash: 'badge-warning',
      HBL: 'badge-accent', UBL: 'badge-accent', Meezan: 'badge-accent',
    };
    return <span className={`badge ${colors[bank] || 'badge-neutral'}`}>{bank}</span>;
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border/40">
        <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'hsl(var(--muted-foreground))' }}>
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            id="tx-search"
            className="search-input"
            placeholder="Search by TXN ID, sender, bank, status…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>
          {total} transaction{total !== 1 ? 's' : ''}
        </div>
        <button
          id="tx-refresh-btn"
          onClick={fetchTxns}
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

      {/* Table */}
      <div className="table-scroll">
        <table className="dash-table">
          <thead>
            <tr>
              <th>#</th>
              <th onClick={() => toggleSort('transaction_id')}>TXN ID <SortIcon col="transaction_id"/></th>
              <th onClick={() => toggleSort('sender_name')}>Sender <SortIcon col="sender_name"/></th>
              <th onClick={() => toggleSort('receiver_name')}>Receiver <SortIcon col="receiver_name"/></th>
              <th onClick={() => toggleSort('amount')}>Amount <SortIcon col="amount"/></th>
              <th onClick={() => toggleSort('bank_or_service')}>Bank / Service <SortIcon col="bank_or_service"/></th>
              <th onClick={() => toggleSort('status')}>Status <SortIcon col="status"/></th>
              <th>Customer</th>
              <th onClick={() => toggleSort('created_at')}>Saved At <SortIcon col="created_at"/></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9}><div className="empty-state"><Spinner/><span>Loading transactions…</span></div></td></tr>
            ) : sorted.length === 0 ? (
              <tr><td colSpan={9}>
                <div className="empty-state">
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.4 }}>
                    <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
                    <line x1="1" y1="10" x2="23" y2="10"/>
                  </svg>
                  <p>No transactions found</p>
                  {search && <p style={{ fontSize: '0.75rem' }}>Try clearing the search filter</p>}
                </div>
              </td></tr>
            ) : sorted.map(t => (
              <tr key={t.id}>
                <td style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.75rem' }}>#{t.id}</td>
                <td>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'hsl(var(--primary))' }}>
                    {t.transaction_id || '—'}
                  </span>
                </td>
                <td style={{ fontWeight: 500 }}>{t.sender_name || '—'}</td>
                <td style={{ color: 'hsl(var(--muted-foreground))' }}>{t.receiver_name || '—'}</td>
                <td>
                  <span style={{ fontWeight: 600, color: 'hsl(var(--accent-secondary))' }}>
                    {t.amount || '—'}
                  </span>
                </td>
                <td>{bankBadge(t.bank_or_service)}</td>
                <td>{statusBadge(t.status)}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'hsl(var(--muted-foreground))' }}>
                  {t.sender_number || '—'}
                </td>
                <td>
                  <div style={{ fontSize: '0.78rem' }}>{fmtDate(t.created_at)}</div>
                  <div style={{ fontSize: '0.7rem', color: 'hsl(var(--muted-foreground))' }}>{fmtTime(t.created_at)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
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
          <span style={{ fontSize: '0.78rem', color: 'hsl(var(--muted-foreground))' }}>
            Page {page} of {totalPages}
          </span>
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
export default function DashboardPage() {
  const [tab, setTab] = useState<'orders' | 'transactions'>('orders');

  return (
    <div className="min-h-screen bg-gradient-mesh">
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Page Header */}
        <div className="animate-fade-in-up mb-8">
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Records & Transactions</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Browse all customer orders and payment transactions captured via WhatsApp.
          </p>
        </div>

        {/* Card */}
        <div className="animate-fade-in-up glass-card rounded-2xl overflow-hidden" style={{ animationDelay: '0.1s' }}>
          {/* Tab Bar */}
          <div className="flex items-center gap-2 px-5 pt-4 pb-0 border-b border-border/40">
            <button
              id="tab-orders"
              className={`tab-btn${tab === 'orders' ? ' active' : ''}`}
              onClick={() => setTab('orders')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <path d="M3 9h18M9 21V9"/>
              </svg>
              Orders
            </button>
            <button
              id="tab-transactions"
              className={`tab-btn${tab === 'transactions' ? ' active' : ''}`}
              onClick={() => setTab('transactions')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
                <line x1="1" y1="10" x2="23" y2="10"/>
              </svg>
              Transactions
            </button>

            {/* Legend */}
            <div className="ml-auto flex items-center gap-3 pb-3" style={{ fontSize: '0.7rem', color: 'hsl(var(--muted-foreground))' }}>
              <span className="badge badge-success">Successful</span>
              <span className="badge badge-warning">Pending</span>
              <span className="badge badge-danger">Failed</span>
            </div>
          </div>

          {/* Tab Content */}
          <div key={tab} className="animate-fade-in-up">
            {tab === 'orders'       ? <OrdersTable />       : <TransactionsTable />}
          </div>
        </div>
      </main>
    </div>
  );
}
