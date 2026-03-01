interface ApiErrorBannerProps {
  message: string;
  className?: string;
}

export function ApiErrorBanner({ message, className }: ApiErrorBannerProps) {
  return (
    <div
      className={`rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive ${className ?? ""}`}
    >
      {message}
    </div>
  );
}
