import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "The Sentinel — OSS Risk Agent",
  description: "Tactical monitoring for open-source dependency health",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden" style={{ background: "#0B0E14", color: "#F0F6FC" }}>
        <Sidebar />
        <main className="flex-1 overflow-y-auto scrollbar-dark">{children}</main>
      </body>
    </html>
  );
}
