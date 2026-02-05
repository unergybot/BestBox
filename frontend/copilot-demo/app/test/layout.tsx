import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "Observability Test - BestBox",
  description: "Test observability features",
};

export default function TestLayout({
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
