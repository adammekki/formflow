type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "link";
};

export default function Button({ variant = "primary", className = "", ...rest }: Props) {
  const styles =
    variant === "primary"
      ? "rounded-lg bg-accent px-4 py-2 font-semibold text-surface transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
      : "text-sm font-medium text-accent-soft underline underline-offset-4 transition-colors hover:text-accent";

  return <button className={`${styles} ${className}`} {...rest} />;
}
