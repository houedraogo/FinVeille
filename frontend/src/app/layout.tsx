import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kafundo - Trouve et securise tes financements",
  description:
    "Kafundo aide a reperer, prioriser et securiser les meilleures opportunites de financement en France et en Afrique.",
  icons: {
    icon: "/brand/kafundo-picto.png",
    apple: "/brand/kafundo-picto.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
