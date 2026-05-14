import type { SVGProps } from "react";

const props = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} satisfies SVGProps<SVGSVGElement>;

export function PlayIcon() {
  return (
    <svg {...props}>
      <polygon points="6 4 20 12 6 20 6 4" />
    </svg>
  );
}

export function PauseIcon() {
  return (
    <svg {...props}>
      <path d="M8 5v14" />
      <path d="M16 5v14" />
    </svg>
  );
}

export function CopyIcon() {
  return (
    <svg {...props}>
      <rect width="14" height="14" x="8" y="8" rx="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

export function ShareIcon() {
  return (
    <svg {...props}>
      <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
      <path d="M12 16V4" />
      <path d="m7 9 5-5 5 5" />
    </svg>
  );
}

export function DocumentIcon() {
  return (
    <svg {...props} width="32" height="32">
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <polyline points="13 2 13 9 20 9" />
    </svg>
  );
}
