interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
}

function colorClass(score: number): string {
  if (score >= 7.0) return "bg-green-100 text-green-800";
  if (score >= 5.0) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

function sizeClass(size: "sm" | "md" | "lg"): string {
  if (size === "sm") return "text-xs px-1.5 py-0.5";
  if (size === "lg") return "text-base px-3 py-1.5 font-bold";
  return "text-sm px-2 py-1 font-medium";
}

export default function HealthBadge({ score, size = "md" }: Props) {
  return (
    <span
      className={`inline-block rounded font-mono ${colorClass(score)} ${sizeClass(size)}`}
    >
      {score.toFixed(1)}
    </span>
  );
}
