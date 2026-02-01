'use client';

import { useState, useEffect } from 'react';
import { Activity, Users, BarChart3, MessageSquare, Settings, LogOut } from 'lucide-react';
import { SystemStatus } from '@/components/SystemStatus';

type DashboardView = 'system' | 'users' | 'agents' | 'conversations';

export default function AdminPage() {
  const [activeView, setActiveView] = useState<DashboardView>('system');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');

  // Simple password protection (replace with proper auth in production)
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    // TODO: Replace with environment variable or proper auth
    if (password === process.env.NEXT_PUBLIC_ADMIN_PASSWORD || password === 'bestbox2026') {
      setIsAuthenticated(true);
      localStorage.setItem('admin_authenticated', 'true');
    } else {
      alert('Invalid password');
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    localStorage.removeItem('admin_authenticated');
  };

  // Check localStorage on mount
  useEffect(() => {
    if (localStorage.getItem('admin_authenticated') === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
          <div className="flex items-center justify-center mb-6">
            <Settings className="text-blue-600 mr-2" size={32} />
            <h1 className="text-2xl font-bold text-gray-900">Admin Login</h1>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Admin Password
              </label>
              <input
                type="password"
                placeholder="Enter admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Login
            </button>
          </form>

          <p className="text-xs text-gray-500 mt-4 text-center">
            Access restricted to authorized administrators only
          </p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'system' as const, label: 'System Health', icon: Activity },
    { id: 'users' as const, label: 'User Analytics', icon: Users },
    { id: 'agents' as const, label: 'Agent Performance', icon: BarChart3 },
    { id: 'conversations' as const, label: 'Conversation Audit', icon: MessageSquare },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">BestBox Admin Dashboard</h1>
            <p className="text-sm text-gray-500 mt-1">
              System observability and user analytics
            </p>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200">
        <div className="px-6">
          <div className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveView(tab.id)}
                  className={`flex items-center gap-2 py-4 border-b-2 transition-colors font-medium ${
                    activeView === tab.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon size={18} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Dashboard Content */}
      <main className="p-6 space-y-6">
        {/* System Status Widget (always visible) */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity size={20} className="text-blue-600" />
            Service Health
          </h2>
          <SystemStatus />
        </div>

        {/* Main Dashboard Content */}
        <DashboardContent view={activeView} />
      </main>
    </div>
  );
}

function DashboardContent({ view }: { view: DashboardView }) {
  // Map view to Grafana dashboard UID (set in dashboard JSON)
  const dashboardUrls: Record<DashboardView, string> = {
    system: 'http://localhost:3001/d/system-health/bestbox-system-health',
    users: 'http://localhost:3001/d/user-analytics/bestbox-user-analytics',
    agents: 'http://localhost:3001/d/agent-performance/bestbox-agent-performance',
    conversations: 'http://localhost:3001/d/conversation-audit/bestbox-conversation-audit',
  };

  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      {/* Embedded Grafana Dashboard */}
      <iframe
        src={`${dashboardUrls[view]}?orgId=1&kiosk=tv&theme=light`}
        className="w-full h-[calc(100vh-400px)] min-h-[600px]"
        frameBorder="0"
        title={`${view} dashboard`}
        allow="fullscreen"
      />

      {/* Quick Actions Panel */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <QuickActions view={view} />
      </div>
    </div>
  );
}

function QuickActions({ view }: { view: DashboardView }) {
  const actions: Record<DashboardView, Array<{ label: string; url?: string; action?: () => void }>> = {
    system: [
      { label: 'View Jaeger Traces', url: 'http://localhost:16686' },
      { label: 'Prometheus Metrics', url: 'http://localhost:9091' },
      { label: 'Download System Report', action: () => alert('Report download feature coming soon') },
    ],
    users: [
      { label: 'Export User Data (CSV)', action: () => alert('Export feature coming soon') },
      { label: 'User Segmentation Analysis', action: () => alert('Segmentation feature coming soon') },
    ],
    agents: [
      { label: 'View Failed Traces', url: 'http://localhost:16686/search?service=bestbox-agent-api&tags=%7B%22error%22%3A%22true%22%7D' },
      { label: 'Agent Performance Report', action: () => alert('Report generation coming soon') },
    ],
    conversations: [
      { label: 'Export Conversations (JSON)', action: () => alert('Export feature coming soon') },
      { label: 'Search by User ID', action: () => alert('Advanced search coming soon') },
    ],
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      <span className="text-sm text-gray-600 font-medium">Quick Actions:</span>
      {actions[view].map((action, idx) => (
        <button
          key={idx}
          onClick={() => action.url ? window.open(action.url, '_blank') : action.action?.()}
          className="text-sm text-blue-600 hover:text-blue-800 underline hover:no-underline transition-all"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
