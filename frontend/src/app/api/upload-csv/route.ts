import { NextRequest, NextResponse } from "next/server";

const apiURL =
  process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const data = await request.formData();

    const resp = await fetch(`${apiURL}/api/upload`, {
      method: "POST",
      body: data,
    });

    const contentType = resp.headers.get("content-type") || "";

    if (resp.ok) {
      const body = contentType.includes("application/json") ? await resp.json() : { message: await resp.text() };
      return NextResponse.json(body, { status: resp.status });
    }

    // upstream returned non-OK
    const text = await resp.text();
    return NextResponse.json({ message: text || `Upstream returned ${resp.status}` }, { status: resp.status });
  } catch (error: any) {
    console.error("[upload-csv route]", error);
    return NextResponse.json({ message: error?.message || String(error) }, { status: 500 });
  }
}
