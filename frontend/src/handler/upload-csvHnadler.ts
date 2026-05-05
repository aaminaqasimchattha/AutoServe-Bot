function getBackendUrl(): string {
  return (
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    ''
  );
}

export async function uploadCsvHandler(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get('file');

    if (!file || !(file instanceof Blob)) {
      console.warn('[upload] Missing file in form data');
      return new Response(JSON.stringify({ success: false, message: "Missing 'file' in form data" }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      });
    }

    const backendBaseUrl = getBackendUrl();
    if (!backendBaseUrl) {
      throw new Error('Missing backend URL. Set NEXT_PUBLIC_BACKEND_URL or BACKEND_API_URL to your active ngrok URL.');
    }

    const backendUrl = `${backendBaseUrl}/api/upload`;
    const fileName = file instanceof File && file.name ? file.name : 'upload';

    console.log('[upload] Forwarding file to backend', {
      backendUrl,
      fileName,
      size: file.size,
      type: file.type,
    });

    const forwardForm = new FormData();
    forwardForm.append('file', file, fileName);

    const response = await fetch(backendUrl, {
      method: 'POST',
      body: forwardForm,
    });

    const contentType = response.headers.get('content-type') || '';
    const responseBody = contentType.includes('application/json')
      ? await response.json()
      : await response.text();

    console.log('[upload] Backend response received', {
      status: response.status,
      ok: response.ok,
      responseBody,
    });

    return new Response(
      typeof responseBody === 'string' ? responseBody : JSON.stringify(responseBody),
      {
        status: response.status,
        headers: { 'content-type': contentType || 'application/json' },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected error';
    console.error('[upload] Proxy failed', error);
    return new Response(JSON.stringify({ success: false, message }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    });
  }
}
