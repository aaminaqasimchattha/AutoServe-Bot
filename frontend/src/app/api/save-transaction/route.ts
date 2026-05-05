import { saveTransactionHandler } from '../../../handler/transactionsHandler';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  return saveTransactionHandler(request as unknown as Request);
}
