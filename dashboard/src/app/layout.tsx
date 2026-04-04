import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import "./globals.css"
import { Providers } from "@/components/providers"
import { Sidebar } from "@/components/sidebar"
import { MobileNav } from "@/components/mobile-nav"
import { TooltipProvider } from "@/components/ui/tooltip"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Отклик — Employer Acquisition Engine",
  description: "Платформа автоматизации привлечения работодателей",
  icons: {
    icon: "/favicon.ico",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="ru"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full bg-zinc-950">
        <Providers>
          <TooltipProvider>
            <div className="flex min-h-screen">
              {/* Desktop Sidebar */}
              <div className="hidden lg:block">
                <Sidebar />
              </div>

              {/* Mobile Navigation */}
              <MobileNav />

              {/* Main Content */}
              <main className="flex-1 lg:ml-64">
                {children}
              </main>
            </div>
          </TooltipProvider>
        </Providers>
      </body>
    </html>
  )
}
