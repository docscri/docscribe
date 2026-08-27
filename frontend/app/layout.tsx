import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  title: 'DocScribe',
  description: 'Clinical conversations, clearly documented.',
  openGraph: { title: 'DocScribe', description: 'Clinical notes, simplified.', images: ['/og.png'] },
  twitter: { card: 'summary_large_image', title: 'DocScribe', description: 'Clinical notes, simplified.', images: ['/og.png'] },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
