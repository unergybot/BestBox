import type { Metadata } from "next";
import "../globals.css";
import AdminSidebar from "./AdminSidebar";

export const metadata: Metadata = {
  title: "Admin - BestBox",
  description: "Session review, document management, and admin panel",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <div className="flex min-h-screen bg-gray-50">
          <AdminSidebar />
          <main className="flex-1 ml-64">{children}</main>
        </div>
      </body>
    </html>
  );
}
