import { ReactNode } from "react";
import AdminSidebar from "./AdminSidebar";

export default async function AdminLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <AdminSidebar locale={locale} />
      <main className="flex-1 ml-64 p-8">{children}</main>
    </div>
  );
}
