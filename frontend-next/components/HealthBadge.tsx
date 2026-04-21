interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
}

function glowStyle(score: number): React.CSSProperties {
  if (score >= 7.0) return {
    background: "rgba(0,230,118,0.1)",
    color: "#00E676",
    boxShadow: "0 0 8px rgba(0,230,118,0.2)",
    border: "1px solid rgba(0,230,118,0.25)",
  };
  if (score >= 5.0) return {
    background: "rgba(251,191,36,0.1)",
    color: "#FBBF24",
    boxShadow: "0 0 8px rgba(251,191,36,0.15)",
    border: "1px solid rgba(251,191,36,0.25)",
  };
  return {
    background: "rgba(255,76,76,0.1)",
    color: "#FF4C4C",
    boxShadow: "0 0 8px rgba(255,76,76,0.25)",
    border: "1px solid rgba(255,76,76,0.3)",
  };
}

function sizeClass(size: "sm" | "md" | "lg"): string {
  if (size === "sm") return "text-xs px-1.5 py-0.5";
  if (size === "lg") return "text-base px-3 py-1.5 font-bold";
  return "text-sm px-2 py-1 font-medium";
}

export default function HealthBadge({ score, size = "md" }: Props) {
  return (
    <span
      className={`inline-block rounded font-mono ${sizeClass(size)}`}
      style={glowStyle(score)}
    >
      {score.toFixed(1)}
    </span>
  );
}
