"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import { useState } from "react";
import { useTranslations } from "next-intl";
import LanguageSwitcher from "../../components/LanguageSwitcher";

export default function Home() {
  const t = useTranslations("Home");
  const tCopilot = useTranslations("Copilot");
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  // Helper function removed as we stick to t.raw for arrays


  const scenarios = ["erp", "crm", "itops", "oa"] as const;

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <CopilotSidebar
        defaultOpen={true}
        clickOutsideToClose={false}
        labels={{
          title: tCopilot("title"),
          initial: tCopilot("initial"),
        }}
      >
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

            {/* System Info Card */}
            <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">
                {t("systemStatus.title")}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                  <div className="text-sm text-green-600 font-medium">{t("systemStatus.model")}</div>
                  <div className="text-lg font-bold text-gray-900">
                    Qwen2.5-14B-Instruct
                  </div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                  <div className="text-sm text-blue-600 font-medium">{t("systemStatus.backend")}</div>
                  <div className="text-lg font-bold text-gray-900">
                    llama.cpp (CPU)
                  </div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
                  <div className="text-sm text-purple-600 font-medium">{t("systemStatus.status")}</div>
                  <div className="text-lg font-bold text-green-600">
                    ✓ {t("systemStatus.operational")}
                  </div>
                </div>
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
                            "border-purple-500 bg-purple-50"
                      : `border-gray-200 hover:${s === "erp" ? "border-blue-300" :
                        s === "crm" ? "border-green-300" :
                          s === "itops" ? "border-orange-300" :
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
                  {/* We'll use a hardcoded range for simplicity since we know the max queries is small. 
                      Arrays in next-intl are tricky without special config. 
                      Alternative: t.raw('sampleQueries.' + demoScenario) as string[] */}
                  {(t.raw(`sampleQueries.${demoScenario}`) as string[]).map((query, i) => (
                    <li key={i}>• "{query}"</li>
                  ))}
                </ul>
                <p className="mt-4 text-sm text-gray-500">
                  {t("tip")}
                </p>
              </div>
            )}

            {/* Footer */}
            <div className="mt-8 text-center text-gray-500 text-sm">
              <p>{t("footer.poweredBy")}</p>
              <p className="mt-1">
                {t("footer.specs")}
              </p>
            </div>
          </div>
        </div>
      </CopilotSidebar>
    </CopilotKit>
  );
}
