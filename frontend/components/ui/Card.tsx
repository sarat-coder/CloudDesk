import { cn } from "@/lib/cn";

interface Props {
  children: React.ReactNode;
  className?: string;
  title?: string;
}

export function Card({ children, className, title }: Props) {
  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)]",
        className
      )}
    >
      {title && (
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h3 className="text-sm font-medium text-[var(--fg)]">{title}</h3>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
