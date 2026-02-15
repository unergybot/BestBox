"use client";

import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotChat, AssistantMessage as CopilotKitAssistantMessage } from "@copilotkit/react-ui";
import { VoiceInput } from "@/components/VoiceInput";
import { ServiceStatusCard } from "@/components/ServiceStatusCard";
import { detectTroubleshootingResults, isTroubleshootingResult, normalizeToTroubleshootingIssue } from "@/lib/troubleshooting-detector";
import { TroubleshootingCard } from "@/components/troubleshooting";
import { ChatMessagesProvider, useChatMessages as useTroubleshootingMessages } from "@/contexts/ChatMessagesContext";
import "@copilotkit/react-ui/styles.css";
import React, { useState, useMemo, useEffect, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import LanguageSwitcher from "../../components/LanguageSwitcher";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";

import { TroubleshootingIssue } from "@/types/troubleshooting";

function AuthBanner({ locale }: { locale: string }) {
  const t = useTranslations("Auth");
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  if (isAuthenticated) return null;

  return (
    <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 flex items-center justify-between gap-2">
      <span className="text-sm text-blue-700">{t("signInPrompt")}</span>
      <button
        onClick={() => router.push(`/${locale}/login?returnUrl=${encodeURIComponent(`/${locale}`)}`)}
        className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 transition-colors"
      >
        {t("signInButton")}
      </button>
    </div>
  );
}

function UserInfoHeader() {
  const t = useTranslations("Auth");
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated || !user) return null;

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          <span className="text-sm font-medium text-blue-700">{user.username[0]?.toUpperCase() || "U"}</span>
        </div>
        <div>
          <div className="text-sm font-medium text-gray-900">{user.username}</div>
          <div className="text-xs text-gray-500 capitalize">{user.role}</div>
        </div>
      </div>
      <button
        onClick={logout}
        className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
      >
        {t("signOutButton")}
      </button>
    </div>
  );
}

function PermissionPrompt({ locale }: { locale: string }) {
  const t = useTranslations("Auth");
  const router = useRouter();

  return (
    <div className="my-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <div className="flex items-center justify-between gap-2">
        <span>{t("permissionPrompt")}</span>
        <button
          onClick={() => router.push(`/${locale}/login?returnUrl=${encodeURIComponent(`/${locale}`)}`)}
          className="shrink-0 rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-700"
        >
          {t("signInButton")}
        </button>
      </div>
    </div>
  );
}

// Context for storing extracted tool results
// Each message gets its own results keyed by message ID
// Session start time prevents fetching for restored (old) messages
const ToolResultsContext = React.createContext<{
  toolResultsMap: Map<string, any>;
  setToolResultsForMessage: (messageId: string, results: any) => void;
  fetchToolResultsForMessage: (messageId: string, messageTimestamp?: number, expectedQuery?: string | null, sessionId?: string | null) => Promise<boolean>;
  clearAllResults: () => void;
  sessionStartTime: number;
}>({
  toolResultsMap: new Map(),
  setToolResultsForMessage: () => {},
  fetchToolResultsForMessage: async () => false,
  clearAllResults: () => {},
  sessionStartTime: 0,
});

function normalizeQueryText(value: string): string {
  return value
    .replace(/\s+/g, "")
    .replace(/[?？!！。．，,、:：;；]/g, "")
    .trim();
}

function isQueryMatch(expected?: string | null, actual?: string | null): boolean {
  if (!expected || !actual) return false;
  const normalizedExpected = normalizeQueryText(expected);
  const normalizedActual = normalizeQueryText(actual);
  if (!normalizedExpected || !normalizedActual) return false;
  return normalizedActual.includes(normalizedExpected) || normalizedExpected.includes(normalizedActual);
}

function ToolResultsProvider({ children }: { children: React.ReactNode }) {
  const [toolResultsMap, setToolResultsMap] = useState<Map<string, any>>(new Map());
  // Session start time - set once on mount, used to filter out restored messages
  const [sessionStartTime] = useState(() => Date.now());
  const debugLogs = process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true";

  // Clear stale backend tool-results cache on page mount (survives Ctrl+F5)
  useEffect(() => {
    fetch('/api/proxy/agent/v1/tool-results/clear', { method: 'DELETE' }).catch(() => {});
  }, []);

  const setToolResultsForMessage = useCallback((messageId: string, results: any) => {
    setToolResultsMap(prev => {
      const newMap = new Map(prev);
      newMap.set(messageId, results);
      return newMap;
    });
  }, []);

  const fetchToolResultsForMessage = useCallback(async (messageId: string, messageTimestamp?: number, expectedQuery?: string | null, sessionId?: string | null) => {
    if (debugLogs) {
      console.log(`[ToolResults] fetchToolResultsForMessage called for ${messageId}, timestamp=${messageTimestamp}, sessionStart=${sessionStartTime}`);
    }

    // Skip fetching for messages that existed before this session (restored messages)
    if (messageTimestamp && messageTimestamp < sessionStartTime) {
      if (debugLogs) {
        console.log(`[ToolResults] Skipping fetch for restored message ${messageId}`);
      }
      return false;
    }

    try {
      const params = new URLSearchParams();
      if (sessionId) params.set("session_id", sessionId);
      if (typeof messageTimestamp === "number") params.set("after_ms", String(messageTimestamp - 1));
      const url = `/api/proxy/agent/v1/tool-results/latest${params.size ? `?${params.toString()}` : ""}`;
      if (debugLogs) {
        console.log(`[ToolResults] Fetching from ${url}`);
      }
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        if (debugLogs) {
          console.log(`[ToolResults] Received data:`, data.status, data.data ? `query=${data.data.query}, total=${data.data.total_available}` : 'null');
        }
        if (data.status === 'ok' && data.data) {
          if (debugLogs) {
            console.log(`[ToolResults] Storing results for ${messageId}`);
          }
          setToolResultsForMessage(messageId, data.data);
          return true;
        }
      }
    } catch (error) {
      if (debugLogs) {
        console.error('[ToolResults] Failed to fetch tool results:', error);
      }
    }
    return false;
  }, [debugLogs, setToolResultsForMessage, sessionStartTime]);

  const clearAllResults = useCallback(() => {
    setToolResultsMap(new Map());
  }, []);

  return (
    <ToolResultsContext.Provider value={{ toolResultsMap, setToolResultsForMessage, fetchToolResultsForMessage, clearAllResults, sessionStartTime }}>
      {children}
    </ToolResultsContext.Provider>
  );
}

function useToolResults() {
  return React.useContext(ToolResultsContext);
}

// Renders tool results as TroubleshootingCards with pagination
function ToolResultsRenderer({ messageId }: { messageId: string }) {
  const { toolResultsMap } = useToolResults();
  const [visibleCount, setVisibleCount] = useState(3); // Initially show 3 (same as top_k)

  const toolResult = toolResultsMap.get(messageId);

  if (!toolResult) {
    return null;
  }

  // Get pagination info
  const totalAvailable = toolResult?.total_available || 0;
  const pageSize = toolResult?.page_size || 3;

  // Extract results from this message's tool result
  const allIssues: TroubleshootingIssue[] = [];
  const seenKeys = new Set<string>();

  if (toolResult?.results && Array.isArray(toolResult.results)) {
    for (const item of toolResult.results) {
      if (isTroubleshootingResult(item)) {
        const issue = normalizeToTroubleshootingIssue(item);
        if (issue.result_type === 'specific_solution') {
          const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}`;
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            allIssues.push(issue);
          }
        }
      }
    }
  }

  if (allIssues.length === 0) {
    return null;
  }

  const visibleIssues = allIssues.slice(0, visibleCount);
  const hasMore = visibleCount < allIssues.length;

  return (
    <div className="space-y-4 my-4">
      {/* Header with count */}
      <div className="text-sm text-gray-500 mb-2">
        显示 {visibleIssues.length} / {allIssues.length} 个案例
      </div>

      {/* Cards */}
      {visibleIssues.map((issue, index) => (
        <TroubleshootingCard
          key={`${issue.case_id}-${issue.issue_number}-${index}`}
          data={issue}
        />
      ))}

      {/* Load more button */}
      {hasMore && (
        <button
          onClick={() => setVisibleCount(prev => Math.min(prev + pageSize, allIssues.length))}
          className="w-full py-2 px-4 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg border border-blue-200 transition-colors"
        >
          加载更多 ({allIssues.length - visibleCount} 个剩余)
        </button>
      )}

      {/* Show less button when expanded */}
      {visibleCount > pageSize && (
        <button
          onClick={() => setVisibleCount(pageSize)}
          className="w-full py-2 px-4 bg-gray-50 hover:bg-gray-100 text-gray-600 rounded-lg border border-gray-200 transition-colors"
        >
          收起
        </button>
      )}
    </div>
  );
}

function SanitizedAssistantMessage(props: React.ComponentProps<typeof CopilotKitAssistantMessage>) {
  const locale = useLocale();
  const { isAuthenticated } = useAuth();
  const { visibleMessages } = useCopilotChat();
  const message = (props as any)?.message;
  const raw = message?.content;
  const content = typeof raw === "string" ? raw : "";
  const copilotId = message?.id;
  const messageTimestamp = message?.timestamp || message?.createdAt;

  // Debug: Log content updates to see if streaming is progressive
  React.useEffect(() => {
    if (content) {
      console.log(`[STREAMING DEBUG] Content update - length: ${content.length}, first 50 chars: "${content.substring(0, 50)}..."`);
    }
  }, [content]);

  // Generate STABLE message ID that doesn't change during streaming
  // Use CopilotKit's ID if available, otherwise generate once on first render
  const [stableMessageId] = useState(() => {
    if (copilotId) return copilotId;
    // Generate a unique ID once - don't use content since it changes during streaming
    return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  });
  const messageId =
    copilotId ||
    (typeof messageTimestamp === "number" ? `assistant-${messageTimestamp}` : stableMessageId);

  const { fetchToolResultsForMessage, toolResultsMap, setToolResultsForMessage, sessionStartTime } = useToolResults();
  const [hasFetched, setHasFetched] = useState(false);
  // Per-component mount time: ensures each message only fetches results created
  // AFTER this component appeared (prevents Q1 results leaking into Q2 cards)
  const [mountedAt] = useState(() => Date.now());
  const afterMs = typeof messageTimestamp === "number" ? messageTimestamp : mountedAt;

  const expectedQuery = useMemo(() => {
    if (!visibleMessages || !Array.isArray(visibleMessages) || !copilotId) return null;
    const currentIndex = visibleMessages.findIndex((msg: any) => msg?.id === copilotId);
    const searchFrom = currentIndex > 0 ? currentIndex - 1 : visibleMessages.length - 1;
    for (let i = searchFrom; i >= 0; i -= 1) {
      const candidate = visibleMessages[i] as any;
      if (candidate?.role === "user" && typeof candidate?.content === "string") {
        return candidate.content;
      }
    }
    return null;
  }, [visibleMessages, copilotId]);

  const toolResultsFromContent = useMemo(() => {
    if (typeof raw !== "string" || raw.length === 0) return null;
    const match = raw.match(/\[TOOL_RESULTS\]([\s\S]*?)\[\/TOOL_RESULTS\]/);
    if (!match || !match[1]) return null;
    try {
      const parsed = JSON.parse(match[1]);
      if (Array.isArray(parsed)) {
        return parsed[0] ?? null;
      }
      return parsed ?? null;
    } catch {
      return null;
    }
  }, [raw]);

  const bbxSessionId = useMemo(() => {
    if (typeof raw !== "string" || raw.length === 0) return null;
    const match = raw.match(/\[BBX_SESSION\]([\s\S]*?)\[\/BBX_SESSION\]/);
    return match && match[1] ? match[1].trim() : null;
  }, [raw]);

  useEffect(() => {
    if (toolResultsFromContent) {
      setToolResultsForMessage(messageId, toolResultsFromContent);
    }
  }, [toolResultsFromContent, messageId, setToolResultsForMessage]);

  // Fetch tool results when a new assistant message appears
  // Pass timestamp so we can skip fetching for restored (old) messages
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
      console.log(`[SanitizedAssistantMessage] useEffect: content=${!!content}, hasFetched=${hasFetched}, messageId=${messageId}`);
    }
    // Fetch from backend even when hidden session tags are stripped.
    // The proxy route will scope tool-results to this UI session using the `bbx_session` cookie.
    if (content && !hasFetched && !toolResultsFromContent) {
      let cancelled = false;
      let timer: ReturnType<typeof setTimeout> | null = null;
      let attempt = 0;
      const maxAttempts = 6;
      const delayMs = 250;

      const runAttempt = async () => {
        if (cancelled) return;
        if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
          console.log(`[SanitizedAssistantMessage] Triggering fetch for ${messageId} (attempt ${attempt + 1})`);
        }
        const stored = await fetchToolResultsForMessage(messageId, afterMs, expectedQuery, bbxSessionId);
        if (stored || attempt >= maxAttempts - 1) {
          setHasFetched(true);
          return;
        }
        attempt += 1;
        timer = setTimeout(runAttempt, delayMs);
      };

      // 1.5s initial delay: gives the embedded [TOOL_RESULTS] path time to
      // parse from the streamed content before falling back to a network fetch.
      timer = setTimeout(runAttempt, 1500);
      return () => {
        cancelled = true;
        if (timer) clearTimeout(timer);
      };
    }
  }, [content, hasFetched, fetchToolResultsForMessage, messageId, afterMs, toolResultsFromContent, expectedQuery, bbxSessionId]);

  // Hide speech-control blocks from the visible chat bubble
  const sanitizedContent = content
    .replace(/\[TOOL_RESULTS\][\s\S]*?\[\/TOOL_RESULTS\]\n*/g, "")
    .replace(/\[SPEECH\][\s\S]*?\[\/SPEECH\]/g, "")
    .replace(/\[SPEECH\][\s\S]*?\[SPEECH\]/g, "")
    .replace(/\[BBX_SESSION\][\s\S]*?\[\/BBX_SESSION\]\n*/g, "")
    .trim();

  const sanitizedMessage = message
    ? ({ ...message, content: sanitizedContent } as any)
    : message;

  const showsPermissionPrompt =
    !isAuthenticated &&
    /(permission|not authorized|access denied|insufficient role|没有权限|权限不足|未授权)/i.test(content);

  const hasResults = toolResultsMap.has(messageId);
  if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
    console.log(`[SanitizedAssistantMessage] Render: copilotId=${copilotId}, stableMessageId=${stableMessageId}, messageId=${messageId}, hasResults=${hasResults}, mapSize=${toolResultsMap.size}`);
  }

  return (
    <>
      {hasResults && <ToolResultsRenderer messageId={messageId} />}
      {showsPermissionPrompt && <PermissionPrompt locale={locale} />}
      <CopilotKitAssistantMessage {...(props as any)} message={sanitizedMessage} />
    </>
  );
}

// Custom code block renderer that detects and renders troubleshooting cards
function TroubleshootingCodeBlock({ inline, className, children, ...props }: any) {
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';

  // Only process JSON-like code blocks (not inline code).
  if (!inline && (language === 'json' || language === 'jsonc' || language === '')) {
    const code = Array.isArray(children) ? children.join('') : String(children);
    const normalized = code.replace(/\n$/, '').trim();

    // Try to parse as JSON directly (since we already have the code block content)
    let troubleshootingIssues: TroubleshootingIssue[] = [];

    try {
      const parsed = JSON.parse(normalized);

      // Check if it's a troubleshooting search results wrapper
      if (parsed && parsed.results && Array.isArray(parsed.results)) {
        const issues = parsed.results
          .filter((r: any) => isTroubleshootingResult(r))
          .map((r: any) => normalizeToTroubleshootingIssue(r))
          .filter((r: TroubleshootingIssue) => r.result_type === 'specific_solution');

        if (issues.length > 0) {
          // Deduplicate by case_id + issue_number + problem + solution
          const seenKeys = new Set<string>();
          troubleshootingIssues = issues.filter((issue: TroubleshootingIssue) => {
            const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}-${issue.solution}`;
            if (seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
          });
        }
      }
      // Check if it's a raw array of troubleshooting results (some models output this format)
      else if (Array.isArray(parsed)) {
        const issues = parsed
          .filter((r: any) => isTroubleshootingResult(r))
          .map((r: any) => normalizeToTroubleshootingIssue(r))
          .filter((r: TroubleshootingIssue) => r.result_type === 'specific_solution');

        if (issues.length > 0) {
          const seenKeys = new Set<string>();
          troubleshootingIssues = issues.filter((issue: TroubleshootingIssue) => {
            const key = `${issue.case_id}-${issue.issue_number}-${issue.problem}-${issue.solution}`;
            if (seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
          });
        }
      }
      // Check if it's a single troubleshooting result
      else if (isTroubleshootingResult(parsed)) {
        const issue = normalizeToTroubleshootingIssue(parsed);
        if (issue.result_type === 'specific_solution') {
          troubleshootingIssues = [issue];
        }
      }
    } catch {
      // Not valid JSON or not troubleshooting data - fall through to default rendering
    }

    if (troubleshootingIssues.length > 0) {
      return (
        <div className="space-y-4 my-4">
          {troubleshootingIssues.map((issue: TroubleshootingIssue, index: number) => (
            <TroubleshootingCard
              key={`${issue.case_id}-${issue.issue_number}-${index}`}
              data={issue}
            />
          ))}
        </div>
      );
    }
  }

  // Default code block rendering
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
}
import { useChatMessages } from "@/contexts/ChatMessagesContext";

function TroubleshootingCardsOverlay() {
  const { messages } = useChatMessages();

  const allResults = useMemo(() => {
    const results: TroubleshootingIssue[] = [];

    if (!messages || !Array.isArray(messages)) {
      return results;
    }

    if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
      console.log("=== TroubleshootingCardsOverlay Debug ===");
      console.log("Messages count:", messages.length);
    }

    for (const msg of messages) {
      if (msg && typeof msg === "object" && "content" in msg) {
        const content = typeof msg.content === "string" ? msg.content : "";
        if (content) {
          const detected = detectTroubleshootingResults(content);
          if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
            console.log(`Detected ${detected.length} results from message`);
            if (detected.length > 0) {
              console.log("First result:", JSON.stringify(detected[0], null, 2));
            }
          }
          const issues = detected
            .filter((r): r is TroubleshootingIssue => r.result_type === "specific_solution")
            .map(r => r as TroubleshootingIssue);
          results.push(...issues);
        }
      }
    }
    if (process.env.NEXT_PUBLIC_TOOL_RESULTS_DEBUG === "true") {
      console.log("Total issues for cards:", results.length);
    }
    return results;
  }, [messages]);

  if (allResults.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 max-w-md max-h-96 overflow-y-auto space-y-4 z-50 pointer-events-none">
      {allResults.map((result, index) => (
        <div key={result.case_id || index} className="pointer-events-auto">
          <TroubleshootingCard data={result} />
        </div>
      ))}
    </div>
  );
}

import { CopilotChatRecorder } from "@/components/CopilotChatRecorder";
import { CopilotTTS } from "@/components/CopilotTTS";

export default function Home() {
  return (
    <AuthProvider>
      <HomeContent />
    </AuthProvider>
  );
}

function HomeContent() {
  const tCopilot = useTranslations("Copilot");
  const locale = useLocale();
  const { token } = useAuth();

  const labels = useMemo(() => ({
    title: tCopilot("title"),
    initial: tCopilot("initial"),
  }), [tCopilot]);

  const markdownTagRenderers = useMemo(() => ({
    code: TroubleshootingCodeBlock,
  }), []);

  return (
    <ChatMessagesProvider>
      <ToolResultsProvider>
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          headers={token ? { Authorization: `Bearer ${token}` } : {}}
        >
          {/* TTS component watches CopilotKit messages and speaks [SPEECH] content */}
          <CopilotTTS />
          <div className="flex flex-col lg:flex-row h-screen">

            {/* Dashboard Column - 40% on desktop, hidden on mobile */}
            <div className="hidden lg:block lg:w-[40%] overflow-y-auto bg-gradient-to-br from-blue-50 to-indigo-100">
              <MemoizedDashboardContent />
            </div>

            {/* Chat Column - 60% on desktop, full width on mobile */}
            <div className="w-full lg:w-[60%] flex flex-col border-l border-gray-200">
              <AuthBanner locale={locale} />
              <UserInfoHeader />
              <CopilotChatRecorder>
                <CopilotChat
                  labels={labels}
                  Input={VoiceInput}
                  AssistantMessage={SanitizedAssistantMessage}
                  markdownTagRenderers={markdownTagRenderers}
                  className="h-full"
                />
              </CopilotChatRecorder>
            </div>

          </div>
        </CopilotKit>
      </ToolResultsProvider>
    </ChatMessagesProvider>
  );
}

const MemoizedDashboardContent = React.memo(DashboardContent);

function DashboardContent() {
  const t = useTranslations("Home");
  const locale = useLocale();
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  const scenarios = ["erp", "crm", "itops", "oa", "mold"] as const;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <LanguageSwitcher />
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            {t("title")}
          </h1>
          <p className="text-lg text-gray-600">
            {t("subtitle")}
          </p>
        </div>

        {/* Management Portals */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            {t("portals.title")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <a
              href={`/${locale}/admin`}
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.adminPortal")}</div>
              <div className="text-sm text-gray-600">/{locale}/admin</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.agentApi")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000"}</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_ERPNEXT_URL || "http://localhost:8002"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.erp")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_ERPNEXT_URL || "http://localhost:8002"}</div>
            </a>

            <a
              href={process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-3 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
            >
              <div className="font-medium text-gray-900">{t("portals.grafana")}</div>
              <div className="text-sm text-gray-600">{process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001"}</div>
            </a>
          </div>

          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
            <a
              href={process.env.NEXT_PUBLIC_JAEGER_URL || "http://localhost:16686"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.jaeger")}
            </a>
            <a
              href={process.env.NEXT_PUBLIC_PROMETHEUS_URL || "http://localhost:9090"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.prometheus")}
            </a>
            <a
              href={process.env.NEXT_PUBLIC_QDRANT_URL || "http://localhost:6333"}
              target="_blank"
              rel="noreferrer"
              className="px-4 py-2 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 transition-colors text-sm"
            >
              {t("portals.qdrant")}
            </a>
          </div>
        </div>

        {/* Demo Scenarios */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            {t("scenarios.title")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scenarios.map((s) => (
              <button
                key={s}
                onClick={() => setDemoScenario(s)}
                className={`p-6 rounded-lg border-2 transition-all text-left ${demoScenario === s
                  ? s === "erp" ? "border-blue-500 bg-blue-50" :
                    s === "crm" ? "border-green-500 bg-green-50" :
                      s === "itops" ? "border-orange-500 bg-orange-50" :
                        s === "mold" ? "border-teal-500 bg-teal-50" :
                          "border-purple-500 bg-purple-50"
                  : `border-gray-200 hover:${s === "erp" ? "border-blue-300" :
                    s === "crm" ? "border-green-300" :
                      s === "itops" ? "border-orange-300" :
                        s === "mold" ? "border-teal-300" :
                          "border-purple-300"
                  }`
                  }`}
              >
                <div className="text-xl font-semibold mb-2">{t(`scenarios.${s}.title`)}</div>
                <p className="text-gray-600 text-sm">
                  {t(`scenarios.${s}.desc`)}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Selected Scenario Details */}
        {demoScenario && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-semibold mb-3 text-gray-800">
              {t(`scenarios.${demoScenario}.queries`)}
            </h3>
            <ul className="space-y-2 text-gray-600">
              {(t.raw(`sampleQueries.${demoScenario}`) as string[]).map((query, i) => (
                <li key={i}>• "{query}"</li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-gray-500">
              {t("tip")}
            </p>
          </div>
        )}

        {/* System Status (moved under Scenarios) */}
        <div className="mt-6">
          <ServiceStatusCard />
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>{t("footer.poweredBy")}</p>
          <p className="mt-1">
            {t("footer.specs")}
          </p>
        </div>
      </div>
    </div>
  );
}
