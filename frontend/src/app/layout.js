import './globals.css';

export const metadata = {
  title: 'NKBP Footprint Change Checker',
  description: 'GIS analytics system for detecting building footprint changes',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}