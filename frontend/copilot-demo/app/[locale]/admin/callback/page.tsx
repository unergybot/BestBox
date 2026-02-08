"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function OIDCCallbackPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const t = useTranslations("AdminNew.common");
  const searchParams = useSearchParams();
  const router = useRouter();
  const [locale, setLocale] = useState("en");

  useEffect(() => {
    params.then((p) => setLocale(p.locale));
  }, [params]);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      router.push(`/${locale}/admin/login`);
      return;
    }

    fetch(`${API_BASE}/admin/auth/oidc/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, locale }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem("admin_jwt_token", data.access_token);
          localStorage.setItem("admin_user", JSON.stringify(data.user));
          if (data.user?.role) localStorage.setItem("admin_role", data.user.role);
          router.push(`/${locale}/admin`);
        } else {
          throw new Error("No access token received");
        }
      })
      .catch((err) => {
        console.error("OIDC callback error:", err);
        router.push(`/${locale}/admin/login`);
      });
  }, [searchParams, router, locale]);

  return (
    <div className="flex items-center justify-center min-h-screen -ml-64">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
        <p className="mt-4 text-gray-600">{t("loading")}</p>
      </div>
    </div>
  );
}
