import { NextResponse } from 'next/server';
import { upsertCustomerHandler, getCustomerHandler } from '../../../handler/customersHandler';

export async function POST(request: Request) {
  return upsertCustomerHandler(request);
}

export async function GET(request: Request) {
  return getCustomerHandler(request);
}
