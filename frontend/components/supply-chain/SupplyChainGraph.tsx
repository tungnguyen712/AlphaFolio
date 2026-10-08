"use client";

import "@xyflow/react/dist/style.css";
import { useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import { useTheme } from "next-themes";
import type { SupplyChainReport, RelationshipKind } from "@/lib/types";

// Only show these four — parent/subsidiary live in the Cards view
const SHOWN_KINDS: RelationshipKind[] = ["supplier", "customer", "manufacturer", "competitor"];

// Theme tokens (see globals.css), so the graph follows light/dark mode.
const tone = (v: string) => ({
  bg: `rgb(var(--${v}) / 0.12)`,
  text: "rgb(var(--ink))",
  border: `rgb(var(--${v}))`,
});
const REL_COLOR: Record<string, { bg: string; text: string; border: string }> = {
  supplier:     tone("muted"),
  customer:     tone("action"),
  manufacturer: tone("buy"),
  competitor:   tone("sell"),
};

const GROUP_LABEL: Record<string, string> = {
  supplier:     "Suppliers",
  customer:     "Customers",
  manufacturer: "Manufacturers",
  competitor:   "Competitors",
};

// ── Custom node: dotted group boundary ────────────────────────────────────────
function KindGroupNode({ data }: NodeProps) {
  const { label, color, tint } = data as { label: string; color: string; tint: string };
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        border: `1.5px dashed ${color}`,
        borderRadius: 12,
        background: tint,
        position: "relative",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: -11,
          left: 14,
          background: "rgb(var(--paper))",
          padding: "0 6px",
          fontSize: 13,
          fontWeight: 600,
          color,
          pointerEvents: "none",
        }}
      >
        {label}
      </span>
    </div>
  );
}

const nodeTypes = { kindGroup: KindGroupNode };

// ── Layout constants ──────────────────────────────────────────────────────────
const NODE_W = 130;
const NODE_H = 44;
const HGAP = 14;         // horizontal gap between nodes in grid
const VGAP = 12;         // vertical gap between nodes in grid
const GROUP_PAD = 24;    // padding inside dotted boundary
const GROUP_LABEL_H = 18; // space reserved for the floating label
const MAX_COLS = 4;
// Minimum distance from center (0,0) to the nearest edge of any group.
const MIN_CENTER_DIST = 88;

// Fixed angles: suppliers top, customers right, manufacturers left
const SECTOR_ANGLES: Record<string, number> = {
  supplier:     -Math.PI / 2,         // top
  customer:      Math.PI / 6,         // bottom-right
  manufacturer: (5 * Math.PI) / 6,    // bottom-left
  competitor:    Math.PI / 2,         // bottom
};

const CENTER_STYLE: React.CSSProperties = {
  background: "rgb(var(--surface))",
  color: "rgb(var(--ink))",
  border: "2px solid rgb(var(--ink))",
  borderRadius: 12,
  padding: "10px 16px",
  fontSize: 13,
  fontWeight: 700,
  minWidth: 120,
  textAlign: "center",
};

/** Compute grid dimensions for `count` nodes. */
function gridDims(count: number) {
  const cols = Math.min(Math.ceil(Math.sqrt(count)), MAX_COLS);
  const rows = Math.ceil(count / cols);
  const innerW = cols * NODE_W + (cols - 1) * HGAP;
  const innerH = rows * NODE_H + (rows - 1) * VGAP;
  const groupW = innerW + 2 * GROUP_PAD;
  const groupH = innerH + 2 * GROUP_PAD + GROUP_LABEL_H;
  return { cols, innerW, groupW, groupH };
}

// ── Graph builder ─────────────────────────────────────────────────────────────
function buildGraph(report: SupplyChainReport): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  nodes.push({
    id: "center",
    position: { x: 0, y: 0 },
    data: { label: report.company_name },
    style: CENTER_STYLE,
    draggable: false,
  });

  // Bucket — skip parent & subsidiary entirely
  const grouped: Record<string, typeof report.relationships> = {
    supplier: [],
    customer: [],
    manufacturer: [],
    competitor: [],
  };
  for (const rel of report.relationships ?? []) {
    if (grouped[rel.relationship]) grouped[rel.relationship].push(rel);
  }

  const activeKinds = SHOWN_KINDS.filter((k) => (grouped[k]?.length ?? 0) > 0);

  activeKinds.forEach((kind) => {
    const rels = grouped[kind];
    const { bg, text, border } = REL_COLOR[kind];
    const { cols, innerW, groupW, groupH } = gridDims(rels.length);

    const angle = SECTOR_ANGLES[kind] ?? 0;
    const ux = Math.cos(angle);
    const uy = Math.sin(angle);

    // Place group so its near edge, not its far diagonal corner, drives spacing.
    const halfAlongRay = Math.abs(ux) * groupW / 2 + Math.abs(uy) * groupH / 2;
    const dist = MIN_CENTER_DIST + halfAlongRay;
    const groupX = ux * dist - groupW / 2;
    const groupY = uy * dist - groupH / 2;

    const groupId = `group-${kind}`;
    nodes.push({
      id: groupId,
      type: "kindGroup",
      position: { x: groupX, y: groupY },
      data: { label: GROUP_LABEL[kind], color: border, tint: bg },
      width: groupW,
      height: groupH,
      style: { width: groupW, height: groupH },
      draggable: true,
    });

    // Grid-layout child nodes inside the group — guaranteed no overlaps
    const gridStartX = (groupW - innerW) / 2;   // horizontally centered
    const gridStartY = GROUP_PAD + GROUP_LABEL_H;

    rels.forEach((rel, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const nodeId = `${kind}-${i}`;

      nodes.push({
        id: nodeId,
        parentId: groupId,
        position: {
          x: gridStartX + col * (NODE_W + HGAP),
          y: gridStartY + row * (NODE_H + VGAP),
        },
        data: { label: rel.name },
        style: {
          background: bg,
          color: text,
          border: `1px solid ${border}`,
          borderRadius: 8,
          padding: "5px 10px",
          fontSize: 11,
          width: NODE_W,
          textAlign: "center",
          fontWeight: 500,
        },
        draggable: false,
      });

      edges.push({
        id: `e-${nodeId}`,
        source: "center",
        target: nodeId,
        style: { stroke: border, strokeWidth: 1, opacity: 0.35 },
        animated: false,
      });
    });
  });

  return { nodes, edges };
}

// ── Component ─────────────────────────────────────────────────────────────────
interface Props {
  report: SupplyChainReport;
}

export function SupplyChainGraph({ report }: Props) {
  const { resolvedTheme } = useTheme();
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(report),
    [report],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

  // Re-seed if report changes within the same mount (e.g. ticker swap)
  useEffect(() => {
    setNodes(initNodes);
    setEdges(initEdges);
  }, [initNodes, initEdges, setNodes, setEdges]);

  return (
    <div
      className="w-full overflow-hidden rounded-lg border border-rule"
      style={{ height: "min(78vh, 860px)", minHeight: 680 }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        panOnDrag
        panOnScroll={false}
        zoomOnScroll
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        colorMode={resolvedTheme === "dark" ? "dark" : "light"}
      >
        <Background color="rgb(var(--rule))" gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
