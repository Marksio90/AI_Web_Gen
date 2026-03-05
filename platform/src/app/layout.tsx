import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"] });

export const metadata: Metadata = {
  title: {
    default: "AI Web Generator — Strony dla polskich firm",
    template: "%s | AI Web Generator",
  },
  description:
    "Automatycznie generujemy profesjonalne strony internetowe dla polskich mikroprzedsiębiorstw. Od 29 PLN miesięcznie.",
  keywords: ["strona internetowa", "małe firmy", "AI", "websitebuilder", "Polska"],
  openGraph: {
    type: "website",
    locale: "pl_PL",
    siteName: "AI Web Generator",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
