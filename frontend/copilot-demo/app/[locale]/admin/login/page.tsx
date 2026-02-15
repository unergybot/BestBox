"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminLoginRedirect({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const router = useRouter();

  useEffect(() => {
    params.then(({ locale }) => {
      router.replace(`/${locale}/login?returnUrl=${encodeURIComponent(`/${locale}/admin`)}`);
    });
  }, [params, router]);

  return null;
}
