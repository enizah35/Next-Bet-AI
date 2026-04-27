import React from "react";

interface IconProps extends React.SVGProps<SVGSVGElement> {
  size?: number;
  sw?: number;
}

const Icon = ({ size = 18, sw = 1.6, children, ...rest }: IconProps & { children?: React.ReactNode }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size} height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
    {...rest}
  >
    {children}
  </svg>
);

export const I = {
  Home: (p: IconProps) => <Icon {...p}><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></Icon>,
  Spark: (p: IconProps) => <Icon {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></Icon>,
  Flame: (p: IconProps) => <Icon {...p}><path d="M12 3s4 4 4 9a4 4 0 01-8 0c0-2 1-3 1-3s-1 4 1 4c0-3 2-5 2-10z"/></Icon>,
  Chart: (p: IconProps) => <Icon {...p}><path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></Icon>,
  Bolt: (p: IconProps) => <Icon {...p}><path d="M13 3L4 14h7l-1 7 9-11h-7l1-7z"/></Icon>,
  User: (p: IconProps) => <Icon {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></Icon>,
  Card: (p: IconProps) => <Icon {...p}><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></Icon>,
  Sun: (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></Icon>,
  Moon: (p: IconProps) => <Icon {...p}><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></Icon>,
  Close: (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6L6 18"/></Icon>,
  Chevron: (p: IconProps) => <Icon {...p}><path d="M9 6l6 6-6 6"/></Icon>,
  ChevronDown: (p: IconProps) => <Icon {...p}><path d="M6 9l6 6 6-6"/></Icon>,
  Check: (p: IconProps) => <Icon {...p}><path d="M5 12l5 5L20 7"/></Icon>,
  Plus: (p: IconProps) => <Icon {...p}><path d="M12 5v14M5 12h14"/></Icon>,
  Info: (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/></Icon>,
  Lock: (p: IconProps) => <Icon {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></Icon>,
  Arrow: (p: IconProps) => <Icon {...p}><path d="M5 12h14M13 6l6 6-6 6"/></Icon>,
  Shield: (p: IconProps) => <Icon {...p}><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/></Icon>,
  Target: (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/></Icon>,
  Grid: (p: IconProps) => <Icon {...p}><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></Icon>,
  List: (p: IconProps) => <Icon {...p}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></Icon>,
  Logout: (p: IconProps) => <Icon {...p}><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></Icon>,
  Alert: (p: IconProps) => <Icon {...p}><path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17h.01"/></Icon>,
  Cal: (p: IconProps) => <Icon {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></Icon>,
  Trend: (p: IconProps) => <Icon {...p}><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/></Icon>,
};

/* Legacy compat shim */
export const Icons = {
  zap: (p: { size?: number }) => <I.Bolt size={p.size} />,
  trendingUp: (p: { size?: number }) => <I.Trend size={p.size} />,
  calendar: (p: { size?: number }) => <I.Cal size={p.size} />,
  alertCircle: (p: { size?: number }) => <I.Alert size={p.size} />,
  check: (p: { size?: number }) => <I.Check size={p.size} />,
  checkCircle: (p: { size?: number }) => <I.Check size={p.size} />,
  cpu: (p: { size?: number }) => <I.Spark size={p.size} />,
  crosshair: (p: { size?: number }) => <I.Target size={p.size} />,
  x: (p: { size?: number }) => <I.Close size={p.size} />,
};
