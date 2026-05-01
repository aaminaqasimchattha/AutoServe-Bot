const DEFAULT_BACKEND_URL = 'https://jone-fumiest-unabsorbingly.ngrok-free.dev';

function getBackendUrl(): string {
  return process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_BACKEND_URL;
}

export async function uploadUrlsHandler(request: Request) {
  try {
    const body = await request.text();
    const backendUrl = `${getBackendUrl()}/api/upload-urls`;

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'content-type': request.headers.get('content-type') || 'application/json',
      },
      body,
    });

    const contentType = response.headers.get('content-type') || '';
    const responseBody = contentType.includes('application/json')
      ? await response.json()
      : await response.text();

    return new Response(
      typeof responseBody === 'string' ? responseBody : JSON.stringify(responseBody),
      {
        status: response.status,
        headers: { 'content-type': contentType || 'application/json' },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected error';
    return new Response(JSON.stringify({ success: false, message }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    });
  }
}
