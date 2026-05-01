import { NextResponse } from 'next/server';
import { uploadUrlsHandler } from '../../../handler/upload-urlsHandler';

export async function POST(request: Request) {
  return uploadUrlsHandler(request);
}
