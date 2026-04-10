import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinVeille — Veille Financement Public",
  description: "Plateforme de veille sur les dispositifs de financement public France & Afrique",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
