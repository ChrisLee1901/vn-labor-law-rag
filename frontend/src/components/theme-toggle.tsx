"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button variant="ghost" size="icon" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
      {/* Biểu tượng và nhãn đổi bằng CSS (class .dark do script đặt trước khi vẽ) nên không lệch giữa server và client. */}
      <SunIcon className="hidden dark:block" />
      <MoonIcon className="dark:hidden" />
      <span className="sr-only dark:hidden">Chuyển sang giao diện tối</span>
      <span className="sr-only hidden dark:inline">Chuyển sang giao diện sáng</span>
    </Button>
  );
}
