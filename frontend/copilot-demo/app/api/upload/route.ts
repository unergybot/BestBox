
import { NextRequest, NextResponse } from "next/server";
import { writeFile } from "fs/promises";
import { join } from "path";
import { mkdir } from "fs/promises";

export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();
        const file = formData.get("file") as File | null;

        if (!file) {
            return NextResponse.json(
                { error: "No file uploaded" },
                { status: 400 }
            );
        }

        const bytes = await file.arrayBuffer();
        const buffer = Buffer.from(bytes);

        // Create unique filename to avoid collisions
        const timestamp = Date.now();
        const safeName = file.name.replace(/[^a-zA-Z0-9.-]/g, "_");
        const filename = `${timestamp}-${safeName}`;

        // Ensure upload directory exists
        const uploadDir = join(process.cwd(), "public", "uploads");
        try {
            await mkdir(uploadDir, { recursive: true });
        } catch (e) {
            // Ignore if exists
        }

        const path = join(uploadDir, filename);
        await writeFile(path, buffer);

        // Return the absolute path for the agent to use
        // Note: The agent is running locally on the same machine/container in this setup.
        // If agent was remote, we'd need to return a URL and the agent would need to download it.
        // Given the context of "local-first" / "copilot-demo", returning absolute path is easiest for tools.

        return NextResponse.json({
            success: true,
            filepath: path,
            filename: filename,
            url: `/uploads/${filename}` // For frontend display if needed
        });

    } catch (error) {
        console.error("Upload error:", error);
        return NextResponse.json(
            { error: "Upload failed" },
            { status: 500 }
        );
    }
}
