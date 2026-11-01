import type { ReactNode, SVGProps } from "react";

function Svg({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export const Scan = () => (
  <Svg>
    <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
    <path d="M4 12h16" />
  </Svg>
);
export const Ruler = () => (
  <Svg>
    <path d="M3 17 17 3l4 4L7 21z" />
    <path d="m7 13 2 2M10 10l2 2M13 7l2 2" />
  </Svg>
);
export const Coins = () => (
  <Svg>
    <ellipse cx="9" cy="7" rx="6" ry="3" />
    <path d="M3 7v5c0 1.7 2.7 3 6 3s6-1.3 6-3V7" />
    <path d="M15 11.5c3.4.2 6 1.4 6 3 0 1.7-2.7 3-6 3-1.4 0-2.6-.2-3.6-.6" />
  </Svg>
);
export const Doc = () => (
  <Svg>
    <path d="M7 3h7l5 5v13H7z" />
    <path d="M14 3v5h5M10 13h6M10 17h6" />
  </Svg>
);
export const Shield = () => (
  <Svg>
    <path d="M12 3 4 6v6c0 4.4 3.4 8.2 8 9 4.6-.8 8-4.6 8-9V6z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);
export const Search = () => (
  <Svg>
    <circle cx="11" cy="11" r="6" />
    <path d="m20 20-4.5-4.5" />
  </Svg>
);
export const Globe = () => (
  <Svg>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
  </Svg>
);
export const Layers = () => (
  <Svg>
    <path d="m12 3 9 5-9 5-9-5z" />
    <path d="m3 13 9 5 9-5" />
  </Svg>
);
export const Sliders = () => (
  <Svg>
    <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" />
    <circle cx="16" cy="6" r="2" />
    <circle cx="10" cy="12" r="2" />
    <circle cx="18" cy="18" r="2" />
  </Svg>
);
export const History = () => (
  <Svg>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5M12 7v5l3 2" />
  </Svg>
);
export const Upload = () => (
  <Svg width="36" height="36" strokeWidth="1.5">
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
  </Svg>
);
export const ArrowDown = () => (
  <Svg width="18" height="18">
    <path d="M12 5v14M6 13l6 6 6-6" />
  </Svg>
);
export const RoomIcon = () => (
  <Svg width="40" height="40" strokeWidth="1.4">
    <path d="M3 8 12 4l9 4v9l-9 4-9-4z" />
    <path d="M3 8l9 4 9-4M12 12v9" />
  </Svg>
);
export const WallIcon = () => (
  <Svg width="40" height="40" strokeWidth="1.4">
    <rect x="3" y="4" width="18" height="16" rx="1" />
    <path d="M3 9.3h18M3 14.6h18M9 4v5.3M15 4v5.3M6 9.3v5.3M12 9.3v5.3M18 9.3v5.3M9 14.6V20M15 14.6V20" />
  </Svg>
);
export const ImagePlus = () => (
  <Svg width="26" height="26" strokeWidth="1.5">
    <rect x="3" y="5" width="14" height="14" rx="2" />
    <path d="m3 15 4-4 4 4 2-2 4 4M19 3v6M16 6h6" />
  </Svg>
);
