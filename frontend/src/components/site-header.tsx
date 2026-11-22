"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { StatusBadge } from "@/components/status-badge";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Hỏi đáp" },
  { href: "/van-ban", label: "Văn bản" },
  { href: "/gioi-thieu", label: "Giới thiệu" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <header className="border-b bg-background/95">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 sm:px-6">
        <Link href="/" className="text-[0.9375rem] font-semibold tracking-tight">
          Trợ lý Pháp luật Lao động
        </Link>
        <div className="order-3 flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 md:order-2 md:w-auto md:flex-1">
          <nav aria-label="Chính" className="-ml-2 flex items-center md:ml-0">
            {NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "whitespace-nowrap rounded-md px-2 py-2 text-sm font-medium text-muted-foreground hover:text-foreground md:px-3",
                  "aria-[current=page]:text-foreground aria-[current=page]:underline aria-[current=page]:decoration-cite-border aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-8",
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <StatusBadge />
        </div>
        <div className="order-2 ml-auto md:order-3 md:ml-0">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
