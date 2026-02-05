import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Admin - BestBox",
  description: "Session review and admin panel",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
