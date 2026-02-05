"use client";

import { useEffect, useState } from "react";
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

interface SessionMessage {
  role: string;
  content: string;
  reasoning_trace?: Array<{
    type: "think" | "act" | "observe" | "answer";
    content: string;
    tool_name?: string;
    tool_args?: Record<string, unknown>;
    timestamp: number;
  }>;
}

interface SessionDetail extends Session {
  messages: SessionMessage[];
}

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminToken) return;
    localStorage.setItem("admin_token", adminToken);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    setIsAuthenticated(false);
    setSessions([]);
    setSelectedSession(null);
  };

  useEffect(() => {
    const stored = localStorage.getItem("admin_token");
    if (stored) {
      setAdminToken(stored);
      setIsAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchSessions = async () => {
      setLoading(true);
      const res = await fetch("/admin/sessions", {
        headers: { "admin-token": adminToken },
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
      setLoading(false);
    };
    fetchSessions();
  }, [isAuthenticated, adminToken]);

  const loadSessionDetail = async (sessionId: string) => {
    setLoading(true);
    const res = await fetch(`/admin/sessions/${sessionId}`, {
      headers: { "admin-token": adminToken },
    });
    if (res.ok) {
      const data = await res.json();
      setSelectedSession(data);
    }
    setLoading(false);
  };

  const rateSession = async (sessionId: string, rating: "good" | "bad") => {
    await fetch(`/admin/sessions/${sessionId}/rating`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "admin-token": adminToken,
      },
      body: JSON.stringify({ rating }),
    });
    await loadSessionDetail(sessionId);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Admin Access</h1>
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              type="password"
              placeholder="Admin token"
              value={adminToken}
              onChange={(e) => setAdminToken(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Session Review</h1>
            <p className="text-sm text-gray-500 mt-1">
              Review ReAct traces and session details
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="bg-white rounded-lg shadow-sm p-4 lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Sessions</h2>
            {loading && <span className="text-xs text-gray-400">Loading...</span>}
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
              <div className="text-sm text-gray-500">No sessions found.</div>
            )}
          </div>
        </section>

        <section className="bg-white rounded-lg shadow-sm p-4 lg:col-span-2">
          {!selectedSession && (
            <div className="text-sm text-gray-500">Select a session to view details.</div>
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
                    Good
                  </button>
                  <button
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded"
                    onClick={() => rateSession(selectedSession.id, "bad")}
                  >
                    Bad
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                {selectedSession.messages?.map((msg, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg p-3">
                    <div className="text-xs uppercase text-gray-400 mb-2">{msg.role}</div>
                    <div className="text-sm text-gray-800 whitespace-pre-wrap mb-3">{msg.content}</div>
                    {msg.reasoning_trace && msg.reasoning_trace.length > 0 && (
                      <ReasoningTrace steps={msg.reasoning_trace} />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
