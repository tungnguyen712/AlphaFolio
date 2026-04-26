// ---------------------------------------------------------------------------
// String-literal union enums
// ---------------------------------------------------------------------------

export type ResearchSignal = "buy" | "hold" | "sell";
export type AgentRunFlow = "research" | "portfolio";
export type AgentRunStatus = "queued" | "running" | "complete" | "failed";
export type RiskProfile = "conservative" | "moderate" | "aggressive";
export type AssetClass = "ipo" | "established" | "private";
export type PendingPositionStatus = "pending" | "accepted" | "rejected";
export type RebalanceTriggerKind =
  | "macro_event"
  | "lockup_expiry"
  | "earnings_date"
  | "drift_threshold"
  | "custom";
export type NotificationKind = "rebalance_trigger" | "run_complete" | "other";

// ---------------------------------------------------------------------------
// Shared: VerdictLayer — embedded in every recommendation surface
// ---------------------------------------------------------------------------

export interface VerdictLayer {
  verdict: string;
  top_3_signals: string[];
  key_uncertainty: string;
  confidence: number; // 0..1
}

// ---------------------------------------------------------------------------
// Research
// ---------------------------------------------------------------------------

export interface ResearchReportSummary {
  id: string;
  run_id: string | null;
  portfolio_id: string | null;
  ticker: string;
  signal: ResearchSignal;
  confidence: number;
  created_at: string;
}

export interface SourceRef {
  kind: string;
  url: string | null;
  label: string;
  retrieved_at: string | null;
}

export interface ResearchReportBody {
  ticker: string;
  signal: ResearchSignal;
  layers: VerdictLayer;
  rationale: string;
  recommended_position_pct: number | null;
  sources: SourceRef[];
}

export interface ResearchReportOut extends ResearchReportSummary {
  report: ResearchReportBody;
}

// ---------------------------------------------------------------------------
// Runs (shared)
// ---------------------------------------------------------------------------

export interface RunAccepted {
  run_id: string;
  flow: AgentRunFlow;
  status: AgentRunStatus;
}

export interface RunStepOut {
  id: string;
  agent_name: string;
  output: Record<string, unknown> | null;
  error: string | null;
  completed_at: string | null;
}

export interface RunStatusOut {
  id: string;
  flow: AgentRunFlow;
  status: AgentRunStatus;
  ticker: string | null;
  started_at: string | null;
  completed_at: string | null;
  report: ResearchReportBody | null;
  recommendation: PortfolioRecommendationBody | null;
  error: string | null;
}

// SSE event discriminated union
export type RunSseEvent =
  | { type: "status"; status: string }
  | {
      type: "step";
      agent_name: string;
      output: Record<string, unknown> | null;
      error: string | null;
      completed_at: string | null;
    }
  | { type: "done"; status: "complete" | "failed" | "timeout"; error: string | null };

// ---------------------------------------------------------------------------
// Portfolio
// ---------------------------------------------------------------------------

export interface PortfolioOut {
  id: string;
  name: string;
  cash_balance: string; // Decimal serialised as string
  risk_profile: RiskProfile;
  created_at: string;
  updated_at: string;
}

export interface HoldingOut {
  id: string;
  portfolio_id: string;
  ticker: string;
  shares: string; // Decimal serialised as string
  avg_cost: string; // Decimal serialised as string
  asset_class: AssetClass;
  created_at: string;
  updated_at: string;
}

export interface PortfolioWithHoldingsOut extends PortfolioOut {
  holdings: HoldingOut[];
}

export interface ProposedTrade {
  ticker: string;
  action: "buy" | "sell" | "trim" | "add";
  target_weight_pct: number;
  rationale: string;
  links_to_report_ticker: string | null;
}

export interface PortfolioRecommendationBody {
  portfolio_id: string;
  layers: VerdictLayer;
  proposed_trades: ProposedTrade[];
  target_allocations: Record<string, number>;
  rationale: string;
}

export interface PortfolioRecommendationOut {
  id: string;
  run_id: string | null;
  portfolio_id: string;
  recommendation: PortfolioRecommendationBody;
  created_at: string;
}

export interface PendingPositionOut {
  id: string;
  portfolio_id: string;
  ticker: string;
  target_pct: string; // Decimal serialised as string
  source_report_id: string | null;
  status: PendingPositionStatus;
  created_at: string;
  updated_at: string;
}

export interface TriggerOut {
  id: string;
  portfolio_id: string;
  kind: RebalanceTriggerKind;
  condition_json: Record<string, unknown>;
  fires_at: string | null;
  last_evaluated_at: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Market data (portfolio prices endpoint)
// ---------------------------------------------------------------------------

export interface TickerMarketData {
  prev_close: number | null;
  sector: string | null;
}

export interface PortfolioPricesOut {
  prices: Record<string, TickerMarketData>;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export interface NotificationOut {
  id: string;
  user_id: string;
  kind: NotificationKind;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}
