import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import '../index.css';
import '../styles/research.css';
import '../styles/landing.css';
import '../styles/product.css';

export const metadata: Metadata = {
  title: 'Nexus | Agentic Research Engine',
  description: 'Explore research sources, trace evidence, and build grounded answers with Nexus.',
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;1,14..32,300;1,14..32,400&display=swap"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
