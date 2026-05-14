import type { SVGProps } from "react";
import type { RunMode, StageMeta } from "./types";

type IconProps = SVGProps<SVGSVGElement>;

const iconProps = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} satisfies IconProps;

function RadarIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}

function BankIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="m3 10 9-7 9 7" />
      <path d="M5 10v10" />
      <path d="M19 10v10" />
      <path d="M9 10v10" />
      <path d="M15 10v10" />
      <path d="M3 20h18" />
    </svg>
  );
}

function UpIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function DownIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </svg>
  );
}

function ScaleIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
      <path d="M7 21h10" />
      <path d="M12 3v18" />
      <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
    </svg>
  );
}

function ShieldIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    </svg>
  );
}

function BriefcaseIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M10 6V5a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v1" />
      <rect width="20" height="14" x="2" y="6" rx="2" />
      <path d="M2 12h20" />
      <path d="M12 12v2" />
    </svg>
  );
}

function ClipboardIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <rect width="8" height="4" x="8" y="2" rx="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <path d="M8 12h8" />
      <path d="M8 16h5" />
    </svg>
  );
}

export const STAGE_META: Record<string, StageMeta> = {
  question_planning: { id: "question_planning", agent: "问题理解", title: "意图与信号规划", color: "#38BDF8", icon: <RadarIcon /> },
  information_analysis: { id: "information_analysis", agent: "信息分析", title: "市场数据汇总", color: "#41C7E8", icon: <RadarIcon /> },
  a_share_context: { id: "a_share_context", agent: "A 股上下文", title: "股票池与板块", color: "#4AB8B0", icon: <BankIcon /> },
  bull_debate: { id: "bull_debate", agent: "多头", title: "看涨逻辑", color: "#78B86B", icon: <UpIcon /> },
  bear_debate: { id: "bear_debate", agent: "空头", title: "看跌反驳", color: "#D66A5A", icon: <DownIcon /> },
  judge_decision: { id: "judge_decision", agent: "裁判", title: "综合裁决", color: "#9E8CFF", icon: <ScaleIcon /> },
  risk_review: { id: "risk_review", agent: "风控", title: "风险复核", color: "#D69B45", icon: <ShieldIcon /> },
  portfolio_manager: { id: "portfolio_manager", agent: "总经理", title: "最终决策", color: "#B58CFF", icon: <BriefcaseIcon /> },
  save_trade_plan: { id: "save_trade_plan", agent: "交易计划", title: "计划落盘", color: "#62BFA2", icon: <ClipboardIcon /> },
};

export const COMMON_STAGE_ORDER = ["question_planning", "information_analysis"];

export const A_SHARE_STAGE_ORDER = [
  "question_planning",
  "information_analysis",
  "bull_debate",
  "bear_debate",
  "judge_decision",
  "risk_review",
  "portfolio_manager",
  "save_trade_plan",
];

export function currentStageOrder(runMode: RunMode): string[] {
  return runMode === "common" ? [...COMMON_STAGE_ORDER] : [...A_SHARE_STAGE_ORDER];
}

export function normalizeStageOrder(stageIds: string[], fallbackMode: RunMode): string[] {
  const known = stageIds.filter((id) => STAGE_META[id]);
  return known.length ? known : currentStageOrder(fallbackMode);
}
