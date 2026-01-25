'use client';

import { useState } from 'react';
import { FeedbackButtons } from '@/components/FeedbackButtons';
import { ThumbsUp, ThumbsDown, Send, Activity } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function ObservabilityTestPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `test-${Date.now()}`);
  const [metrics, setMetrics] = useState<string>('');

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-user-id': 'test-user',
        },
        body: JSON.stringify({
          messages: messages.concat(userMessage).map(m => ({
            role: m.role,
            content: m.content,
          })),
          model: 'bestbox-agent',
        }),
      });

      const data = await response.json();

      const assistantMessage: Message = {
        id: data.id || `msg-${Date.now()}`,
        role: 'assistant',
        content: data.choices[0].message.content || 'No response',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Fetch updated metrics
      fetchMetrics();
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch('http://localhost:8000/metrics');
      const text = await response.text();

      // Extract relevant metrics
      const relevantMetrics = text
        .split('\n')
        .filter(line =>
          line.includes('agent_requests_total') ||
          line.includes('agent_latency_seconds') ||
          line.includes('user_feedback_total') ||
          line.includes('active_sessions')
        )
        .filter(line => !line.startsWith('#'))
        .join('\n');

      setMetrics(relevantMetrics);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">
          🧪 BestBox Observability Test Page
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          Test feedback buttons and watch metrics update in real-time
        </p>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chat Area */}
          <div className="lg:col-span-2 space-y-4">
            {/* Instructions Card */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h2 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                <Activity size={20} />
                How to Test Observability
              </h2>
              <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
                <li>Send a message using the chat below</li>
                <li>Click thumbs up 👍 or thumbs down 👎 on the response</li>
                <li>Watch the metrics panel update on the right</li>
                <li>Open Grafana to see metrics: <a href="http://localhost:3001" target="_blank" className="underline">localhost:3001</a></li>
                <li>Check Jaeger traces: <a href="http://localhost:16686" target="_blank" className="underline">localhost:16686</a></li>
              </ol>
            </div>

            {/* Session Info */}
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm text-gray-600">
                <strong>Session ID:</strong> <code className="bg-gray-100 px-2 py-1 rounded">{sessionId}</code>
              </div>
              <div className="text-sm text-gray-600 mt-2">
                <strong>User ID:</strong> <code className="bg-gray-100 px-2 py-1 rounded">test-user</code>
              </div>
            </div>

            {/* Messages */}
            <div className="bg-white rounded-lg shadow min-h-[400px] max-h-[500px] overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center text-gray-400 py-12">
                  No messages yet. Send a message to start testing!
                </div>
              )}

              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-900'
                    }`}
                  >
                    <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                    <div className="text-xs opacity-70 mt-1">
                      {message.timestamp.toLocaleTimeString()}
                    </div>

                    {/* Feedback Buttons for Assistant Messages */}
                    {message.role === 'assistant' && (
                      <div className="mt-3 pt-3 border-t border-gray-300">
                        <FeedbackButtons
                          messageId={message.id}
                          sessionId={sessionId}
                          onFeedbackSubmitted={(rating) => {
                            console.log(`Feedback submitted: ${rating}`);
                            fetchMetrics(); // Refresh metrics after feedback
                          }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-200 text-gray-900 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-700"></div>
                      <span className="text-sm">Agent is thinking...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Type a message to test observability..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <Send size={18} />
                  Send
                </button>
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => setInput('What is BestBox?')}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Quick: What is BestBox?
                </button>
                <button
                  onClick={() => setInput('Show me ERP features')}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Quick: ERP features
                </button>
                <button
                  onClick={() => setInput('Help with IT operations')}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Quick: IT ops help
                </button>
              </div>
            </div>
          </div>

          {/* Metrics Panel */}
          <div className="space-y-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-gray-900">Live Metrics</h2>
                <button
                  onClick={fetchMetrics}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Refresh
                </button>
              </div>

              {metrics ? (
                <pre className="text-xs bg-gray-50 p-3 rounded border border-gray-200 overflow-x-auto whitespace-pre-wrap font-mono">
                  {metrics || 'No metrics yet. Send a message!'}
                </pre>
              ) : (
                <div className="text-sm text-gray-400 text-center py-8">
                  Click Refresh to load metrics
                </div>
              )}
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Quick Links</h3>
              <div className="space-y-2 text-sm">
                <a
                  href="http://localhost:3001"
                  target="_blank"
                  className="block text-blue-600 hover:underline"
                >
                  📊 Grafana (admin/bestbox)
                </a>
                <a
                  href="http://localhost:9090"
                  target="_blank"
                  className="block text-blue-600 hover:underline"
                >
                  📈 Prometheus
                </a>
                <a
                  href="http://localhost:16686"
                  target="_blank"
                  className="block text-blue-600 hover:underline"
                >
                  🔍 Jaeger Tracing
                </a>
                <a
                  href="http://localhost:8000/metrics"
                  target="_blank"
                  className="block text-blue-600 hover:underline"
                >
                  🔢 Raw Metrics
                </a>
              </div>
            </div>

            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <h3 className="font-semibold text-green-900 mb-2">Test Checklist</h3>
              <div className="space-y-1 text-sm text-green-800">
                <div>✅ Send message</div>
                <div>✅ Click thumbs up/down</div>
                <div>✅ See metrics update</div>
                <div>✅ Check Grafana</div>
                <div>✅ View Jaeger trace</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
