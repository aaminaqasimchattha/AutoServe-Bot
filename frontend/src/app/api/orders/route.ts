import { NextResponse } from 'next/server';
import { uploadOrderHandler } from '../../../handler/ordersHandler';

export async function POST(request: Request) {
  return uploadOrderHandler(request);
}
