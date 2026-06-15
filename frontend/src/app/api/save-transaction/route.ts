import { saveTransactionHandler, getTransactionsByPhone } from '../../../handler/transactionsHandler';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  return saveTransactionHandler(request as unknown as Request);
}

// GET /api/save-transaction?phone=<number>  → returns transactions from DB
export async function GET(request: NextRequest) {
  return getTransactionsByPhone(request as unknown as Request);
}
