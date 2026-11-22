import { type Effectiveness } from "@/lib/docs-cache";
import { cn } from "@/lib/utils";

const TONE: Record<Effectiveness["tone"], string> = {
  active: "bg-status-online text-status-online-foreground",
  future: "bg-status-offline text-status-offline-foreground",
  expired: "bg-status-down text-status-down-foreground",
};

/** Huy hiệu tình trạng hiệu lực dùng chung cho chat và trang Văn bản. Luôn có chữ, không chỉ màu. */
export function EffectivenessBadge({ eff, className }: { eff: Effectiveness; className?: string }) {
  return (
    <span
      title={eff.tooltip}
      className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", TONE[eff.tone], className)}
    >
      {eff.label}
    </span>
  );
}
