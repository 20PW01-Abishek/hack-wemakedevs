"use client";

import { useContextStore } from "@/domain/contextStore";

/** Warns about documents that newer decisions have made outdated. */
export default function AlertsBanner() {
  const alerts = useContextStore((s) => s.alerts);
  if (!alerts.length) return null;

  return (
    <details className="alerts">
      <summary>⚠️ {alerts.length} outdated document(s)</summary>
      {alerts.map((a, i) => (
        <p key={i}>
          <strong>{a.doc}</strong> (last updated {a.doc_updated}) is out of date: on {a.decided} <em>{a.decision}</em>.{" "}
          <strong>{a.concept}</strong> is now <strong>{a.current_value}</strong>. {a.people_reading_it.length} people
          affected: {a.people_reading_it.join(", ")}.
        </p>
      ))}
    </details>
  );
}
