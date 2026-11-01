"use client";

import { useAuthStore } from "@/domain/authStore";
import { useContextStore } from "@/domain/contextStore";
import Icon from "./Icon";

/** Every document the brain has learned from. Admins can remove them. */
export default function DocumentTable() {
  const admin = useAuthStore((s) => s.account?.admin);
  const { documents, remove } = useContextStore();

  if (!documents.length) return <p className="muted">Nothing here yet. Upload a file or sync the documentation folder.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Summary</th>
            <th>Updated</th>
            <th>Parts</th>
            {admin && <th />}
          </tr>
        </thead>
        <tbody>
          {documents.map((d) => (
            <tr key={d.id}>
              <td>
                <strong>{d.name}</strong>
                {d.url && d.url !== d.name && <div className="muted small">{d.url}</div>}
              </td>
              <td className="summary">{d.summary}</td>
              <td>{d.updated}</td>
              <td>{d.chunks}</td>
              {admin && (
                <td>
                  <button
                    className="icon-button"
                    aria-label={`Remove ${d.name}`}
                    title="Remove from the brain"
                    onClick={() => window.confirm(`Remove "${d.name}" and what was learned from it?`) && remove(d)}
                  >
                    <Icon name="trash" />
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
