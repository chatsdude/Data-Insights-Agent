"use client";

import { useEffect, useState } from "react";

type SummaryStreamProps = {
  text: string;
  stream?: boolean;
  onStreamComplete?: () => void;
};

export function SummaryStream({
  text,
  stream = false,
  onStreamComplete,
}: SummaryStreamProps) {
  const [visibleLength, setVisibleLength] = useState(text.length);

  useEffect(() => {
    if (!stream) {
      setVisibleLength(text.length);
      return;
    }

    setVisibleLength(0);
    if (!text) return;

    let currentLength = 0;
    const interval = setInterval(() => {
      const remaining = text.length - currentLength;
      const step = Math.min(3, Math.max(1, Math.ceil(remaining / 22)));
      currentLength = Math.min(text.length, currentLength + step);
      setVisibleLength(currentLength);

      if (currentLength >= text.length) {
        clearInterval(interval);
        onStreamComplete?.();
      }
    }, 20);

    return () => clearInterval(interval);
  }, [text, stream, onStreamComplete]);

  if (!text) return null;

  const streamedText = text.slice(0, visibleLength);
  const isStreaming = visibleLength < text.length;

  return (
    <section className="summary-card" aria-live="polite">
      <div className="summary-head">
        <span className="summary-badge">Insights Summary</span>
      </div>
      <pre className="summary-body">
        {streamedText}
        {isStreaming && <span className="summary-cursor" aria-hidden="true" />}
      </pre>
    </section>
  );
}
