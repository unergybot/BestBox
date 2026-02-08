"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import ReasoningTrace from "@/components/ReasoningTrace";

interface Session {
  id: string;
  user_id?: string;
  channel?: string;
  started_at?: string;
  ended_at?: string;
  message_count?: number;
  status?: string;
  rating?: string;
  rating_note?: string;
}

interface ReasoningStep {
  type: "think" | "act" | "observe" | "answer";
  content: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  timestamp: number;
}

interface SessionMessage {
  role: string;
  content: string;
  reasoning_trace?: string | ReasoningStep[];
}

interface SessionDetail extends Session {
  messages: SessionMessage[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function parseReasoningTrace(trace: string | ReasoningStep[] | undefined | null): ReasoningStep[] {
  if (!trace) return [];
  if (Array.isArray(trace)) return trace;
  try {
    const parsed = JSON.parse(trace);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

export default function AdminSessionsPage() {
  const t = useTranslations("AdminNew");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchSessions = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/admin/sessions`, {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          setSessions(data);
        }
      } catch (e) {
        console.error("Failed to fetch sessions:", e);
      }
      setLoading(false);
    };
    fetchSessions();
  }, []);

  const loadSessionDetail = async (sessionId: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/sessions/${sessionId}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedSession(data);
      }
    } catch (e) {
      console.error("Failed to load session:", e);
    }
    setLoading(false);
  };

  const rateSession = async (sessionId: string, rating: "good" | "bad") => {
    await fetch(`${API_BASE}/admin/sessions/${sessionId}/rating`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ rating }),
    });
    await loadSessionDetail(sessionId);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("sessions.title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("sessions.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Session list */}
        <section className="bg-white rounded-lg shadow-sm p-4 lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">{t("nav.sessions")}</h2>
            {loading && <span className="text-xs text-gray-400">{t("common.loading")}</span>}
          </div>
          <div className="space-y-3">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => loadSessionDetail(session.id)}
                className={`w-full text-left p-3 rounded-lg border ${
                  selectedSession?.id === session.id ? "border-blue-500" : "border-gray-200"
                } hover:border-blue-400 transition-colors`}
              >
                <div className="text-sm font-medium text-gray-900">{session.id}</div>
                <div className="text-xs text-gray-500">{session.user_id || "anonymous"}</div>
                <div className="text-xs text-gray-400 mt-1">{session.status || "active"}</div>
              </button>
            ))}
            {sessions.length === 0 && !loading && (
              <div className="text-sm text-gray-500">{t("sessions.noSessions")}</div>
            )}
          </div>
        </section>

        {/* Session detail */}
        <section className="bg-white rounded-lg shadow-sm p-4 lg:col-span-2">
          {!selectedSession && (
            <div className="text-sm text-gray-500">{t("sessions.selectSession")}</div>
          )}
          {selectedSession && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Session {selectedSession.id}</h2>
                  <p className="text-xs text-gray-500">User: {selectedSession.user_id || "anonymous"}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="px-3 py-1 text-sm bg-green-600 text-white rounded"
                    onClick={() => rateSession(selectedSession.id, "good")}
                  >
                    {t("sessions.rateGood")}
                  </button>
                  <button
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded"
                    onClick={() => rateSession(selectedSession.id, "bad")}
                  >
                    {t("sessions.rateBad")}
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                {selectedSession.messages?.map((msg, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg p-3">
                    <div className="text-xs uppercase text-gray-400 mb-2">{msg.role}</div>
                    <div className="text-sm text-gray-800 whitespace-pre-wrap mb-3">{msg.content}</div>
                    {msg.reasoning_trace && parseReasoningTrace(msg.reasoning_trace).length > 0 && (
                      <ReasoningTrace steps={parseReasoningTrace(msg.reasoning_trace)} />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

