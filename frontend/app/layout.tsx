import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CloudDesk Support",
  description: "AI-powered customer support resolution platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
