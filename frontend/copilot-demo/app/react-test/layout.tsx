import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "ReAct Test - BestBox",
  description: "Test the ReAct reasoning endpoint",
};

export default function ReactTestLayout({
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
