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
      <div className="flex items-center gap-3 text-gray-500">
        <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        {message && <span className="text-sm">{message}</span>}
      </div>
      {slow && (
        <p className="text-xs text-gray-400 ml-8">
          Databricks warehouse may be warming up — this can take up to 2 minutes on first
          load. You can also start it manually in the Databricks console.
        </p>
      )}
    </div>
  );
}
