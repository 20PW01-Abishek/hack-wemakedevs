"use client";

import { useEffect, useRef } from "react";
import { toDot } from "@/domain/graph";
import type { PathGraph as PathGraphData } from "@/domain/types";

/** Draws the graph path behind an answer with Graphviz. */
export default function PathGraph({ graph }: { graph: PathGraphData }) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    import("@viz-js/viz").then(async ({ instance }) => {
      const viz = await instance();
      if (!cancelled && box.current) box.current.replaceChildren(viz.renderSVGElement(toDot(graph)));
    });
    return () => {
      cancelled = true;
    };
  }, [graph]);

  return <div className="path-graph" ref={box} />;
}
