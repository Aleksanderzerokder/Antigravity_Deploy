import './globals.css'

export const metadata = {
  title: 'Antigravity Analytics | Seller Dashboard',
  description: 'Premium Analytics for E-commerce Sellers',
}

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>
        <div className="min-h-screen relative">
          {/* Subtle Background Glows */}
          <div className="fixed top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-purple-900/10 blur-[120px] pointer-events-none" />
          <div className="fixed bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-900/10 blur-[120px] pointer-events-none" />
          
          <main className="relative z-10">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
