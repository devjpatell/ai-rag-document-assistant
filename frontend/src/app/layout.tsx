import "../styles/globals.css";

export const metadata = {
  title: "RAG Document Q&A",
  description: "AI-powered document question answering system"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
