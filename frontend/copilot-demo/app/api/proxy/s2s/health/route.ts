import net from 'net';
import { NextResponse } from 'next/server';

const DEFAULT_TIMEOUT_MS = 1000;

function getS2STarget(): { url: string; hostname: string; port: number } {
  const configuredUrl = process.env.NEXT_PUBLIC_S2S_SERVER_URL;
  if (configuredUrl) {
    const parsed = new URL(configuredUrl);
    const port = parsed.port ? Number(parsed.port) : parsed.protocol === 'wss:' ? 443 : 80;
    return { url: configuredUrl, hostname: parsed.hostname, port };
  }

  const port = Number(process.env.NEXT_PUBLIC_S2S_PORT || '8765');
  return { url: `ws://127.0.0.1:${port}`, hostname: '127.0.0.1', port };
}

async function tcpProbe(
  hostname: string,
  port: number,
  timeoutMs: number,
): Promise<{ reachable: boolean; error?: string; latencyMs: number }> {
  const start = Date.now();

  return await new Promise(resolve => {
    const socket = net.createConnection({ host: hostname, port });

    const finalize = (reachable: boolean, error?: string) => {
      const latencyMs = Date.now() - start;
      socket.removeAllListeners();
      socket.destroy();
      resolve({ reachable, error, latencyMs });
    };

    socket.setTimeout(timeoutMs);

    socket.once('connect', () => finalize(true));
    socket.once('timeout', () => finalize(false, 'Timeout'));
    socket.once('error', err => finalize(false, err.message));
  });
}

export async function GET(): Promise<Response> {
  const { url, hostname, port } = getS2STarget();
  const result = await tcpProbe(hostname, port, DEFAULT_TIMEOUT_MS);

  return NextResponse.json(
    {
      ok: result.reachable,
      reachable: result.reachable,
      message: result.reachable
        ? `TCP reachable (${result.latencyMs}ms)`
        : `Not reachable: ${result.error || 'Unknown error'}`,
      url,
      hostname,
      port,
      latency_ms: result.latencyMs,
    },
    {
      // Return 200 even when down, so the dashboard doesn't spam console with "Failed to load resource".
      status: 200,
      headers: {
        'Cache-Control': 'no-store',
      },
    },
  );
}
