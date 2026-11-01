import type { Metadata } from "next";
import "@/presentation/styles.css";

export const metadata: Metadata = {
  title: "Lattice",
  description: "Ask why things changed, who decided, and who is affected.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
