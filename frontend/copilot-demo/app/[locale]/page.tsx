"use client";

import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { VoiceInput } from "@/components/VoiceInput";
import { ServiceStatusCard } from "@/components/ServiceStatusCard";
import "@copilotkit/react-ui/styles.css";
import React, { useState, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import LanguageSwitcher from "../../components/LanguageSwitcher";

export default function Home() {
  const tCopilot = useTranslations("Copilot");

  const labels = useMemo(() => ({
    title: tCopilot("title"),
    initial: tCopilot("initial"),
  }), [tCopilot]);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <CopilotSidebar
        defaultOpen={true}
        clickOutsideToClose={false}
        labels={labels}
        Input={VoiceInput}
      >
        <MemoizedDashboardContent />
      </CopilotSidebar>
    </CopilotKit>
  );
}

const MemoizedDashboardContent = React.memo(DashboardContent);

function DashboardContent() {
  const t = useTranslations("Home");
  const [demoScenario, setDemoScenario] = useState<string | null>(null);

  const scenarios = ["erp", "crm", "itops", "oa"] as const;

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

        {/* Service Health Status */}
        <ServiceStatusCard />

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
  );
}
