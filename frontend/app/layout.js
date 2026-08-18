import "./globals.css";


export const metadata = {
  title: "AI Research Assistant",
  description: "Project-scoped research literature management",
};


export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
