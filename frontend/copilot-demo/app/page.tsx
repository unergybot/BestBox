"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { useState } from "react";

export default function Home() {
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <CopilotSidebar
        defaultOpen={true}
        clickOutsideToClose={false}
        labels={{
          title: "BestBox AI Assistant",
          initial: "Hello! I'm your BestBox AI assistant. I can help you with:\n\n• ERP queries (invoices, inventory, vendors)\n• System information\n• Demo scenarios\n\nTry asking: 'What's the system status?' or 'Show me unpaid invoices'",
        }}
      >
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-4xl font-bold text-gray-900 mb-2">
                BestBox Enterprise Agentic Demo
              </h1>
              <p className="text-lg text-gray-600">
                AI-Powered ERP/CRM/OA Assistant with Local LLM
              </p>
            </div>

            {/* System Info Card */}
            <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">
                System Status
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                  <div className="text-sm text-green-600 font-medium">Model</div>
                  <div className="text-lg font-bold text-gray-900">
                    Qwen2.5-14B-Instruct
                  </div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                  <div className="text-sm text-blue-600 font-medium">Backend</div>
                  <div className="text-lg font-bold text-gray-900">
                    llama.cpp (CPU)
                  </div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
                  <div className="text-sm text-purple-600 font-medium">Status</div>
                  <div className="text-lg font-bold text-green-600">
                    ✓ Operational
                  </div>
                </div>
              </div>
            </div>

            {/* Demo Scenarios */}
            <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">
                Demo Scenarios
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => setDemoScenario("erp")}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    demoScenario === "erp"
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-blue-300"
                  }`}
                >
                  <div className="text-xl font-semibold mb-2">🏢 ERP Copilot</div>
                  <p className="text-gray-600 text-sm">
                    Invoice processing, inventory checks, financial reporting
                  </p>
                </button>

                <button
                  onClick={() => setDemoScenario("crm")}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    demoScenario === "crm"
                      ? "border-green-500 bg-green-50"
                      : "border-gray-200 hover:border-green-300"
                  }`}
                >
                  <div className="text-xl font-semibold mb-2">
                    📊 CRM Assistant
                  </div>
                  <p className="text-gray-600 text-sm">
                    Lead qualification, quotation generation, opportunity tracking
                  </p>
                </button>

                <button
                  onClick={() => setDemoScenario("itops")}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    demoScenario === "itops"
                      ? "border-orange-500 bg-orange-50"
                      : "border-gray-200 hover:border-orange-300"
                  }`}
                >
                  <div className="text-xl font-semibold mb-2">
                    🔧 IT Ops Agent
                  </div>
                  <p className="text-gray-600 text-sm">
                    Ticket routing, knowledge base search, automated diagnostics
                  </p>
                </button>

                <button
                  onClick={() => setDemoScenario("oa")}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    demoScenario === "oa"
                      ? "border-purple-500 bg-purple-50"
                      : "border-gray-200 hover:border-purple-300"
                  }`}
                >
                  <div className="text-xl font-semibold mb-2">
                    📝 OA Workflow
                  </div>
                  <p className="text-gray-600 text-sm">
                    Leave approvals, meeting scheduling, document workflows
                  </p>
                </button>
              </div>
            </div>

            {/* Selected Scenario Details */}
            {demoScenario && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-xl font-semibold mb-3 text-gray-800">
                  {demoScenario === "erp" && "ERP Copilot Sample Queries"}
                  {demoScenario === "crm" && "CRM Assistant Sample Queries"}
                  {demoScenario === "itops" && "IT Ops Agent Sample Queries"}
                  {demoScenario === "oa" && "OA Workflow Sample Queries"}
                </h3>
                <ul className="space-y-2 text-gray-600">
                  {demoScenario === "erp" && (
                    <>
                      <li>• "Show me all unpaid invoices"</li>
                      <li>• "What's our current inventory status?"</li>
                      <li>• "Who are our top vendors?"</li>
                      <li>• "Give me Q4 financial summary"</li>
                    </>
                  )}
                  {demoScenario === "crm" && (
                    <>
                      <li>• "Which leads should I focus on this week?"</li>
                      <li>• "Generate a quote for Acme Corp"</li>
                      <li>• "What's the status of opportunity #245?"</li>
                    </>
                  )}
                  {demoScenario === "itops" && (
                    <>
                      <li>• "Why is server prod-db-01 slow?"</li>
                      <li>• "Show me active alerts"</li>
                      <li>• "Search knowledge base for VPN issues"</li>
                    </>
                  )}
                  {demoScenario === "oa" && (
                    <>
                      <li>• "Draft an approval email for budget request"</li>
                      <li>• "Schedule a team meeting next Tuesday"</li>
                      <li>• "Generate leave request form"</li>
                    </>
                  )}
                </ul>
                <p className="mt-4 text-sm text-gray-500">
                  💡 Use the chat on the right to interact with the AI assistant
                </p>
              </div>
            )}

            {/* Footer */}
            <div className="mt-8 text-center text-gray-500 text-sm">
              <p>Powered by Qwen2.5-14B-Instruct + llama.cpp + CopilotKit</p>
              <p className="mt-1">
                AMD Ryzen AI Max+ 395 • ROCm 7.2.0 • 128GB RAM • Ubuntu 24.04
              </p>
            </div>
          </div>
        </div>
      </CopilotSidebar>
    </CopilotKit>
  );
}
