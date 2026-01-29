/**
 * LiveKit Token Generation API
 * 
 * Generates JWT tokens for LiveKit room access
 * Tokens are signed with LIVEKIT_API_KEY and LIVEKIT_API_SECRET
 */

import { NextRequest, NextResponse } from 'next/server';
import { AccessToken, RoomServiceClient, AgentDispatchClient } from 'livekit-server-sdk';

export async function POST(request: NextRequest) {
  try {
    const { roomName, participantName } = await request.json();

    if (!roomName) {
      return NextResponse.json(
        { error: 'Room name is required' },
        { status: 400 }
      );
    }

    // Get LiveKit configuration from environment
    const apiKey = process.env.LIVEKIT_API_KEY || 'devkey';
    const apiSecret = process.env.LIVEKIT_API_SECRET || 'secret';
    // Internal host for RoomServiceClient and AgentDispatchClient (localhost)
    const host = process.env.LIVEKIT_HOST || 'http://localhost:7880';
    const wsUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';

    // Dispatch agent to room explicitly
    // This is the most reliable way in LiveKit 1.9+ to ensure an agent joins
    try {
      const dispatchClient = new AgentDispatchClient(host, apiKey, apiSecret);
      await dispatchClient.createDispatch(roomName, 'BestBoxVoiceAgent', {
        metadata: JSON.stringify({ source: 'token-api' })
      });
      console.log(`[Token API] Dispatched BestBoxVoiceAgent to room ${roomName}`);
    } catch (dispatchErr) {
      console.warn(`[Token API] Failed to dispatch agent explicitly:`, dispatchErr);

      // Fallback: Ensure room exists with metadata at least
      try {
        const roomService = new RoomServiceClient(host, apiKey, apiSecret);
        await roomService.createRoom({
          name: roomName,
          metadata: JSON.stringify({ agent_dispatch: 'BestBoxVoiceAgent' })
        });
        console.log(`[Token API] Fallback: Room ${roomName} ensured with metadata`);
      } catch (roomErr) {
        console.warn(`[Token API] Fallback: Failed to ensure room existence:`, roomErr);
      }
    }

    // Generate participant name if not provided
    const identity = participantName || `user-${Date.now()}`;

    // Create access token
    const token = new AccessToken(apiKey, apiSecret, {
      identity,
      // Token valid for 1 hour
      ttl: 3600,
    });

    // Grant permissions
    token.addGrant({
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canPublishData: true,
      canSubscribe: true,
    });

    // Generate JWT
    const jwt = await token.toJwt();

    return NextResponse.json({
      token: jwt,
      url: wsUrl,
      roomName,
      identity,
    });
  } catch (error) {
    console.error('[LiveKit Token API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to generate token' },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json(
    { error: 'Method not allowed. Use POST with { roomName, participantName? }' },
    { status: 405 }
  );
}
