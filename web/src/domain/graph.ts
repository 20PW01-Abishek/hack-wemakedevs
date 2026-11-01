import type { PathGraph } from "./types";

const COLORS: Record<string, string> = {
  Person: "#f0abfc",
  Concept: "#93c5fd",
  Decision: "#86efac",
  Doc: "#7dd3fc",
};

function wrap(text: string, width: number): string {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(" ")) {
    if (line && line.length + word.length + 1 > width) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  return [...lines, line].join("\n");
}

/** Convert an answer path into Graphviz DOT source, laid out left to right. */
export function toDot(graph: PathGraph): string {
  const q = JSON.stringify;
  const nodes = graph.nodes.map(
    (n) => `${q(n.id)} [label=${q(`${wrap(n.id, 28)}\n(${n.label})`)}, fillcolor="${COLORS[n.label] ?? "#e5e7eb"}"];`,
  );
  const edges = graph.edges.map((e) => `${q(e.from)} -> ${q(e.to)} [label=${q(e.type)}];`);
  return [
    'digraph { rankdir=LR; bgcolor="transparent";',
    'node [shape=box, style="filled,rounded", fontname=Helvetica, fontsize=10, fontcolor="#111827", color="#6b7280"];',
    'edge [fontname=Helvetica, fontsize=8, color="#9ca3af", fontcolor="#9ca3af"];',
    ...nodes,
    ...edges,
    "}",
  ].join("\n");
}
