import type { ReactNode } from "react";

/**
 * Small hand-drawn icon set (24x24 grid, 2px round strokes). No icon library.
 * Icons are decorative (aria-hidden) unless the caller labels the control.
 */
export type IconName =
  | "chevronLeft"
  | "chevronRight"
  | "check"
  | "checkCircle"
  | "arrowClockwise"
  | "mic"
  | "speaker"
  | "waveform"
  | "caretUp"
  | "play"
  | "pause"
  | "info"
  | "warning"
  | "chorusMark";

const PATHS: Record<IconName, ReactNode> = {
  chevronLeft: <path d="M15 5l-7 7 7 7" />,
  chevronRight: <path d="M9 5l7 7-7 7" />,
  check: <path d="M5 12.5l4.5 4.5L19 7" />,
  checkCircle: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12.5l2.8 2.8L16.2 9.5" />
    </>
  ),
  arrowClockwise: (
    <>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path d="M19.5 4.5v4.2h-4.2" />
    </>
  ),
  mic: (
    <>
      <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
      <path d="M12 18v3" />
    </>
  ),
  speaker: (
    <>
      <path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" />
      <path d="M15.5 9a4 4 0 0 1 0 6" />
      <path d="M18.2 6.5a8 8 0 0 1 0 11" />
    </>
  ),
  waveform: <path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" />,
  caretUp: <path d="M6 15l6-6 6 6" />,
  play: <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />,
  pause: (
    <>
      <path d="M8.5 5.5v13" strokeWidth="3.4" />
      <path d="M15.5 5.5v13" strokeWidth="3.4" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5.5M12 7.6v.1" />
    </>
  ),
  warning: (
    <>
      <path d="M12 4l9 16H3z" />
      <path d="M12 10v4.5M12 17.4v.1" />
    </>
  ),
  chorusMark: <path d="M5 10v4M9 6v12M13 3.5v17M17 7v10M21 10.5v3" />,
};

interface IconProps {
  name: IconName;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function Icon({ name, size = 20, strokeWidth = 2, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}

/** Small ring spinner for in-place progress. */
export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg
      className="spinner"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" opacity="0.2" />
      <path d="M12 3a9 9 0 0 1 9 9" />
    </svg>
  );
}
