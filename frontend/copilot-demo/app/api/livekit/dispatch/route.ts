/**
 * LiveKit Agent Dispatch API
 * 
 * Dispatches an agent to join a room when requested
 */

import { NextRequest, NextResponse } from 'next/server';
import { RoomServiceClient, AccessToken, AgentDispatchClient } from 'livekit-server-sdk';

export async function POST(request: NextRequest) {
  try {
    const { roomName } = await request.json();

    if (!roomName) {
      return NextResponse.json(
        { error: 'Room name is required' },
        { status: 400 }
      );
    }

    // Get LiveKit configuration
    const wsUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || 'ws://localhost:7880';
    const apiKey = process.env.LIVEKIT_API_KEY || 'devkey';
    const apiSecret = process.env.LIVEKIT_API_SECRET || 'secret';

    // Convert ws:// to http:// for API calls
    const apiUrl = wsUrl.replace('ws://', 'http://').replace('wss://', 'https://');

    // Check if using LiveKit Cloud
    const isLiveKitCloud = wsUrl.includes('livekit.cloud');

    try {
      // Only create room for self-hosted LiveKit
      // LiveKit Cloud auto-creates rooms when participants join
      if (!isLiveKitCloud) {
        const roomService = new RoomServiceClient(apiUrl, apiKey, apiSecret);
        try {
          // Ensure room exists
          await roomService.createRoom({
            name: roomName,
            emptyTimeout: 300, // 5 minutes
            maxParticipants: 10,
          });
          console.log(`[Agent Dispatch] Room created: ${roomName}`);
        } catch (e: any) {
          if (e.message?.includes('already exists')) {
            console.log(`[Agent Dispatch] Room already exists: ${roomName}`);
          } else {
            console.error(`[Agent Dispatch] Failed to create room:`, e);
            // Don't fail - room might auto-create
          }
        }
      } else {
        console.log(`[Agent Dispatch] Using LiveKit Cloud - room will auto-create`);
      }

      // Create agent token for the room
      const agentToken = new AccessToken(apiKey, apiSecret, {
        identity: `agent-${Date.now()}`,
        ttl: 3600,
      });

      agentToken.addGrant({
        room: roomName,
        roomJoin: true,
        canPublish: true,
        canPublishData: true,
        canSubscribe: true,
      });

      const jwt = await agentToken.toJwt();

      // Trigger agent dispatch by creating an explicit dispatch
      // This tells LiveKit to assign the job to a registered agent worker
      console.log(`[Agent Dispatch] Agent token created for room: ${roomName}`);

      // Skip explicit dispatch for LiveKit Cloud - agents auto-dispatch when room is created
      // Only dispatch for local/self-hosted LiveKit
      if (!isLiveKitCloud) {
        try {
          const dispatchClient = new AgentDispatchClient(apiUrl, apiKey, apiSecret);
          console.log(`[Agent Dispatch] Creating dispatch for room: ${roomName}`);
          // Create dispatch for specific agent
          const dispatchResult = await dispatchClient.createDispatch(roomName, 'BestBoxVoiceAgent');
          console.log(`[Agent Dispatch] Agent dispatched successfully:`, JSON.stringify(dispatchResult, null, 2));
        } catch (dispatchError: any) {
          console.error(`[Agent Dispatch] Dispatch call FAILED:`, dispatchError);
          console.error(`[Agent Dispatch] Error details:`, {
            message: dispatchError.message,
            stack: dispatchError.stack,
            code: dispatchError.code,
          });
          // Don't fail - agent may already be in room
        }
      } else {
        console.log(`[Agent Dispatch] Using LiveKit Cloud - agent will auto-dispatch`);
      }

      return NextResponse.json({
        success: true,
        roomName,
        agentToken: jwt,
        message: 'Agent dispatched to room',
      });
    } catch (e: any) {
      console.error('[Agent Dispatch] Error:', e);
      throw e;
    }
  } catch (error) {
    console.error('[Agent Dispatch] Error:', error);
    return NextResponse.json(
      {
        error: 'Failed to dispatch agent',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
