import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import { Toaster } from "sonner";

import { AuthProvider } from "@/components/auth-provider";
import { Shell } from "@/components/shell";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "TextPulse AI",
  description: "Relationship intelligence platform for conversation analysis, coaching, and predictive contact profiles.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${ibmPlexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <Shell>{children}</Shell>
          <Toaster
            theme="dark"
            richColors
            position="top-right"
            toastOptions={{
              className: "border border-white/10 bg-slate-950 text-white",
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
