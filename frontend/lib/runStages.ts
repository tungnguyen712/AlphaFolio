import type { AgentRunFlow } from "@/lib/types";

// The graphs are static, so the reader-facing stages can be defined up front.
// Each stage maps to one or more backend agent steps (see backend/app/graphs).
export interface RunStage {
  key: string;
  label: string;
  description: string;
  agents: string[];
}

export const RESEARCH_STAGES: RunStage[] = [
  {
    key: "gather",
    label: "Gathering filings, prices and news",
    description: "Reading insider trades, analyst views, financial filings and recent headlines.",
    agents: ["data_retrieval", "market_intel"],
  },
  {
    key: "signals",
    label: "Reading the signals",
    description: "Weighing what the evidence says about the business and the stock.",
    agents: ["signal_analysis"],
  },
  {
    key: "counter",
    label: "Testing the opposing case",
    description: "Looking for the strongest reasons the call could be wrong.",
    agents: ["devils_advocate"],
  },
  {
    key: "report",
    label: "Writing your report",
    description: "Pulling everything into a verdict, the key signals and the main uncertainty.",
    agents: ["validation", "synthesis"],
  },
];

export const PORTFOLIO_STAGES: RunStage[] = [
  {
    key: "allocate",
    label: "Building your allocation",
    description: "Balancing your holdings against your risk profile.",
    agents: ["portfolio_construction"],
  },
];

export type StageState = "done" | "active" | "pending" | "failed";

export interface StageView {
  stage: RunStage;
  state: StageState;
}

interface StepLike {
  agent_name: string;
  completed_at: string | null;
  error: string | null;
}

export function stagesForFlow(flow: AgentRunFlow | null | undefined): RunStage[] {
  return flow === "portfolio" ? PORTFOLIO_STAGES : RESEARCH_STAGES;
}

export function computeStages(
  stages: RunStage[],
  steps: StepLike[],
  opts: { isStreaming: boolean; failed: boolean; complete: boolean },
): { views: StageView[]; completedCount: number } {
  const finished = new Set(
    steps.filter((s) => s.completed_at && !s.error).map((s) => s.agent_name),
  );
  const erroredAgents = new Set(steps.filter((s) => s.error).map((s) => s.agent_name));

  let currentAssigned = false;
  let completedCount = 0;
  const views = stages.map<StageView>((stage) => {
    const done = opts.complete || stage.agents.every((a) => finished.has(a));
    if (done) {
      completedCount += 1;
      return { stage, state: "done" };
    }
    if (currentAssigned) return { stage, state: "pending" };
    currentAssigned = true;
    if (opts.failed || stage.agents.some((a) => erroredAgents.has(a))) {
      return { stage, state: "failed" };
    }
    return { stage, state: opts.isStreaming ? "active" : "pending" };
  });
  return { views, completedCount };
}

const UPSTREAM_ERROR_PREFIXES = [
  "AuthenticationError",
  "PermissionDeniedError",
  "RateLimitError",
  "OverloadedError",
  "AnthropicError",
  "InternalServerError",
  "APIConnectionError",
  "APITimeoutError",
];

// Maps a raw backend error to a sentence a reader can act on. Never shows the
// raw text: it can contain provider names, request ids and keys' error codes.
export function friendlyRunError(error: string | null): string {
  if (error?.startsWith("LookupError")) {
    return "We couldn't find this ticker. Check the symbol and try again.";
  }
  if (error?.startsWith("ValueError") || error?.startsWith("KeyError")) {
    return "A data provider returned something unexpected. Try again shortly.";
  }
  if (error && UPSTREAM_ERROR_PREFIXES.some((p) => error.startsWith(p))) {
    return "Our analysis service is unavailable right now. Please try again in a few minutes.";
  }
  return "Something went wrong while building this report. Start a new run to try again.";
}
