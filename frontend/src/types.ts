export type Language = "en" | "ur" | "ar";
export type Finish = "basic" | "standard" | "premium";
export type ConfidenceLabel = "high" | "medium" | "low";

export const FINISHING_WORK = ["wall", "floor", "ceiling", "door", "window", "fixture"] as const;
export const REPAIR_WORK = ["crack", "damp", "peeling"] as const;
export const ALL_WORK = [...FINISHING_WORK, ...REPAIR_WORK];
export type WorkItem = (typeof ALL_WORK)[number];

export type SpaceMode = "room" | "wall";
export type PhotoRole = "floor" | "ceiling" | "wall";
/** Work that can be seen in a single wall photo; floor, ceiling and fixtures need a room. */
export const WALL_WORK: WorkItem[] = ["wall", "door", "window", "crack", "damp", "peeling"];
/** Replacing doors, windows or lights is a choice, not a default: most jobs are refinishing and repairs. */
export const REPLACEMENTS: WorkItem[] = ["door", "window", "fixture"];
export const withoutReplacements = (items: readonly WorkItem[]) => items.filter((w) => !REPLACEMENTS.includes(w));

/** Typical room sizes (m) the backend assumes when the customer has no measurements. */
export const ROOM_TYPES = {
  bedroom: [3.5, 4],
  master_bedroom: [4.5, 5],
  living: [5, 6],
  kitchen: [3, 3.5],
  bathroom: [2, 2.5],
} as const;
export type RoomType = keyof typeof ROOM_TYPES;

export interface RolePhoto {
  file: File;
  role: PhotoRole;
}

export interface Scale {
  method: "user_reference" | "assumed_door" | "none";
  metres_per_pixel: number | null;
  reference: string | null;
}

export interface Evidence {
  source: string;
  detector_score: number;
  image_share: number;
  boxes: number[][];
  photo: number | null;
  area_basis?: "scale" | "dimensions" | null;
  estimated?: boolean;
  rule: string;
}

export interface ReportElement {
  type: string;
  count: number;
  area_m2: number | null;
  confidence: number;
  confidence_label: ConfidenceLabel;
  evidence: Evidence | null;
  edited?: boolean;
}

export interface ReportDefect {
  kind: string;
  location: string;
  severity: "low" | "medium" | "high";
  confidence: number;
  confidence_label: ConfidenceLabel;
  why: string;
  evidence: Evidence | null;
}

export interface CostLine {
  item: string;
  quantity: number;
  unit: string;
  low: number;
  high: number;
  estimated?: boolean;
  labour_share?: number | null;
  edited?: boolean;
}

export interface Report {
  scene: string;
  scale: Scale;
  elements: ReportElement[];
  defects: ReportDefect[];
  cost_estimate: {
    currency: string;
    finish: Finish;
    scope: string[];
    low: number | null;
    high: number | null;
    estimated?: boolean;
    sample_rates?: boolean;
    vendor?: Vendor | null;
    labour_low?: number | null;
    labour_high?: number | null;
    materials_low?: number | null;
    materials_high?: number | null;
    lines: CostLine[];
    assumptions: string[];
  };
  summary: string;
  language: Language;
  disclaimer: string;
}

export interface Layer {
  type: string;
  color: string;
  png_base64: string;
}

/** The user's corrections: counts and areas per element type, and boxes tapped away per photo. */
export interface Edits {
  counts?: Record<string, number>;
  areas?: Record<string, number>;
  removed?: Record<string, Record<string, number[][]>>;
}

/** "pending": the instant code report is shown while the Muse model writes the full one. */
export type ReasoningState = "none" | "pending" | "done" | "failed";

export interface AnalysisResult {
  id: string;
  mode: "live" | "mock";
  reasoning?: ReasoningState;
  edits?: Edits;
  perceiver: string;
  filename: string;
  role?: PhotoRole | null;
  report: Report;
  image_png_base64: string;
  layers: Layer[];
  warnings: string[];
}

export interface RoomResult {
  id: string;
  mode: "live" | "mock";
  reasoning?: ReasoningState;
  edits?: Edits;
  photos: AnalysisResult[];
  report: Report;
  warnings: string[];
}

export type Result = AnalysisResult | RoomResult;

export const isRoom = (r: Result): r is RoomResult => "photos" in r;

export interface HistoryEntry {
  id: string;
  kind: "photo" | "room";
  created_at: string;
  title: string;
  summary: string;
  currency: string;
  low: number | null;
  high: number | null;
}

export interface PriceItem {
  label: string;
  unit: "m2" | "each";
  low: number;
  high: number;
  labour_share?: number | null;
}

export interface PriceListInfo {
  id: string;
  name: string;
  currencies: string[];
  active: boolean;
  logo?: string | null;
}

/** Whether the report writer can answer right now. */
export type WriterStatus = "ready" | "loading" | "offline" | "api" | "off";

/** Who a price table belongs to; shown on every report and PDF priced with it. */
export interface Vendor {
  name: string;
  tagline?: string;
  logo?: string | null;
  phone?: string;
  email?: string;
  website?: string;
  address?: string;
  city?: string;
  valid_until?: string;
  terms?: string;
}

export interface PriceTable {
  default_currency: string;
  note: string;
  sample?: boolean;
  vendor?: Vendor | null;
  list_id?: string | null;
  finish_multipliers: Record<Finish, number>;
  tables: Record<string, Record<string, PriceItem>>;
}
