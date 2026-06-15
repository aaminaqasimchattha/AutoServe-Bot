import { NextResponse } from 'next/server';
import { uploadOrderHandler, getOrderHandler } from '../../../handler/ordersHandler';

export async function POST(request: Request) {
  return uploadOrderHandler(request);
}

export async function GET(request: Request) {
  return getOrderHandler(request);
}
