"use client";

import { useEffect, useState } from "react";

interface Props {
  message?: string;
}

export default function LoadingSpinner({ message }: Props) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3" style={{ color: "#8B9BB4" }}>
        <div
          className="w-5 h-5 rounded-full animate-spin-ring"
          style={{
            border: "2px solid rgba(139,92,246,0.2)",
            borderTopColor: "#8B5CF6",
          }}
        />
        {message && <span className="text-sm">{message}</span>}
      </div>
      {slow && (
        <p className="text-xs ml-8" style={{ color: "#4B5563" }}>
          Databricks warehouse may be warming up — this can take up to 2 minutes on first
          load.
        </p>
      )}
    </div>
  );
}
