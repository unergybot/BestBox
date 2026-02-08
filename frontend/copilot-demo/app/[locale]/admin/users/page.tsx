"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations } from "next-intl";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface User {
  id: string;
  username: string;
  role: string;
  created_at: string | null;
  last_login: string | null;
}

interface AuditEntry {
  id: number;
  user_id: string | null;
  username: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token") || "";
  if (!token) return {};
  if (token.includes(".")) return { Authorization: `Bearer ${token}` };
  return { "admin-token": token };
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  engineer: "bg-blue-100 text-blue-700",
  viewer: "bg-gray-100 text-gray-700",
};

export default function UsersPage() {
  const t = useTranslations("AdminNew.users");

  const [users, setUsers] = useState<User[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"users" | "audit">("users");

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("engineer");
  const [createError, setCreateError] = useState("");

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/users`, { headers: getAuthHeaders() });
      if (res.ok) setUsers(await res.json());
    } catch (e) {
      console.error("Failed to fetch users:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAuditLog = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/audit-log?limit=100`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data.entries || []);
      }
    } catch (e) {
      console.error("Failed to fetch audit log:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "users") fetchUsers();
    else fetchAuditLog();
  }, [activeTab, fetchUsers, fetchAuditLog]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ username: newUsername, password: newPassword, role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Create failed" }));
        throw new Error(err.detail || "Create failed");
      }
      setShowCreateForm(false);
      setNewUsername("");
      setNewPassword("");
      setNewRole("engineer");
      fetchUsers();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleUpdateRole = async (userId: string, role: string) => {
    try {
      await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ role }),
      });
      fetchUsers();
    } catch (e) {
      console.error("Failed to update role:", e);
    }
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (res.ok) fetchUsers();
    } catch (e) {
      console.error("Failed to delete user:", e);
    }
  };

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("title")}</h1>
        <p className="text-sm text-gray-500 mt-1">{t("subtitle")}</p>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("users")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "users" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("tabs.users")}
        </button>
        <button
          onClick={() => setActiveTab("audit")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "audit" ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("tabs.auditLog")}
        </button>
      </div>

      {/* Users tab */}
      {activeTab === "users" && (
        <div>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
            >
              {showCreateForm ? t("actions.cancel") : t("actions.create")}
            </button>
          </div>

          {/* Create user form */}
          {showCreateForm && (
            <div className="bg-white rounded-lg border border-gray-200 p-5 mb-6 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">{t("modal.title")}</h3>
              <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("table.username")}</label>
                  <input type="text" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" required />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("modal.password")}</label>
                  <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" required />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t("table.role")}</label>
                  <select value={newRole} onChange={(e) => setNewRole(e.target.value)} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm">
                    <option value="admin">{t("roles.admin")}</option>
                    <option value="engineer">{t("roles.engineer")}</option>
                    <option value="viewer">{t("roles.viewer")}</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button type="submit" className="w-full bg-green-600 text-white py-2 rounded-md text-sm hover:bg-green-700">
                    {t("modal.save")}
                  </button>
                </div>
              </form>
              {createError && <p className="text-sm text-red-600 mt-2">{createError}</p>}
            </div>
          )}

          {/* Users table */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t("table.username")}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t("table.role")}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t("table.created")}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t("table.lastLogin")}</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">{t("table.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">{t("empty")}</td></tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{u.username}</td>
                      <td className="px-4 py-3">
                        <select
                          value={u.role}
                          onChange={(e) => handleUpdateRole(u.id, e.target.value)}
                          className={`px-2 py-1 rounded text-xs font-medium ${ROLE_COLORS[u.role] || "bg-gray-100"}`}
                        >
                          <option value="admin">{t("roles.admin")}</option>
                          <option value="engineer">{t("roles.engineer")}</option>
                          <option value="viewer">{t("roles.viewer")}</option>
                        </select>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {u.last_login ? new Date(u.last_login).toLocaleString() : "Never"}
                      </td>
                      <td className="px-4 py-3">
                        <button onClick={() => handleDeleteUser(u.id, u.username)} className="text-xs text-red-600 hover:text-red-800">
                          {t("actions.delete")}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Audit log tab */}
      {activeTab === "audit" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">{t("audit.time")}</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">{t("audit.user")}</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">{t("audit.action")}</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">{t("audit.resource")}</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">{t("audit.details")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
              ) : auditLog.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">{t("audit.empty")}</td></tr>
              ) : (
                auditLog.map((entry) => (
                  <tr key={entry.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{entry.username || "system"}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">{entry.action}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {entry.resource_type}{entry.resource_id && `: ${entry.resource_id.substring(0, 12)}…`}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 max-w-xs truncate">
                      {entry.details ? JSON.stringify(entry.details) : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
