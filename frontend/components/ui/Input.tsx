import { cn } from "@/lib/cn";

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Input({ label, className, id, ...rest }: Props) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-xs font-medium text-[var(--fg)]">
          {label}
        </label>
      )}
      <input
        id={id}
        className={cn(
          "px-3 py-2 rounded-md border border-[var(--border)] bg-[var(--bg)]",
          "text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]",
          "focus:outline-none focus:ring-2 focus:ring-[var(--brand)] focus:border-transparent",
          className
        )}
        {...rest}
      />
    </div>
  );
}
