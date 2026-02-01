import { NextRequest, NextResponse } from "next/server";

const AGENT_API_URL = process.env.AGENT_API_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ image_id: string }> }
) {
  const { image_id } = await params;

  try {
    // Proxy request to backend
    const backendUrl = new URL(
      `/api/troubleshooting/images/${encodeURIComponent(image_id)}`,
      AGENT_API_URL
    ).toString();
    const response = await fetch(backendUrl);

    if (!response.ok) {
      return new NextResponse("Image not found", { status: 404 });
    }

    // Get image data and content type
    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "image/jpeg";

    // Return image with proper headers
    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=86400", // Cache for 1 day
      },
    });
  } catch (error) {
    console.error("Error fetching image:", error);
    return new NextResponse("Internal server error", { status: 500 });
  }
}
