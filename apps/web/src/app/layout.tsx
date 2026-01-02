import "./globals.css";
import type { Metadata } from "next";
import { Manrope, Roboto_Mono, Space_Grotesk } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import Navigation from "@/components/navigation/Navigation";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-body" });
const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });
const mono = Roboto_Mono({ subsets: ["latin"], variable: "--font-code" });

export const metadata: Metadata = {
  title: "MatchedBetting - Professional Matched Betting Platform",
  description: "Master matched betting with our comprehensive tools, calculators, and academy. Start earning risk-free profits today.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={[manrope.variable, spaceGrotesk.variable, mono.variable].join(" ")}>
      <body>
        <ClerkProvider
          signInUrl="/sign-in"
          signUpUrl="/sign-up"
          afterSignInUrl="/dashboard"
          afterSignUpUrl="/dashboard"
        >
          <Navigation />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
