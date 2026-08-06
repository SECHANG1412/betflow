import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "BetFlow",
  description: "Betman 배당 흐름 기반 승부예측 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
