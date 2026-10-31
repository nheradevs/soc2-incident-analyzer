/**
 * Typed contract of the RF5/RF6 report endpoints (`POST /api/report`,
 * `GET /api/report/pdf`). Identifiers stay English, values Spanish.
 *
 * The report is composed by the backend from the analysis already in the
 * session: the screen renders what the payload contains and never composes or
 * completes a section on its own.
 */

import { CategoryCoverage, RiskLevelCount } from './analysis.models';

/** Version keys of the payload; both versions carry the same nine sections. */
export type ReportVersionKey = 'ejecutiva' | 'tecnica';

/**
 * Body of one section: the backend sends either a single string (one block of
 * prose) or an array of strings (paragraphs and `•`-prefixed list items).
 */
export type ReportSectionBody = string | string[];

/**
 * Explicit states of the optional assisted writing. None of them means the
 * report is incomplete: the nine sections are always rendered.
 */
export type NarrativeState =
  | 'aplicada'
  | 'parcial'
  | 'no_configurada'
  | 'deshabilitada_por_error'
  | 'plantilla';

/** One of the nine mandatory sections (FSD RF5), in payload order. */
export interface ReportSection {
  number: number;
  key: string;
  /** Already numbered by the backend, e.g. `3. Explicación técnica de cada hallazgo`. */
  title: string;
  body: ReportSectionBody;
  /** Per-section state: a section never rewritten by design stays `plantilla`. */
  narrative: NarrativeState;
  narrative_reason: string | null;
}

/** One audience version of the report. */
export interface ReportVersion {
  key: ReportVersionKey;
  label: string;
  narrative_status: NarrativeState;
  sections: ReportSection[];
}

/** Non-secret description of the optional provider plus the overall state. */
export interface ReportNarrative {
  configurada: boolean;
  proveedor: string;
  modelo: string;
  razonamiento: string;
  estado: NarrativeState;
  motivo: string | null;
  solicitudes: number;
  secciones_aplicadas: number;
  secciones_con_error: number;
}

/** Outcome of the anti-hallucination guard over the rewritten sections. */
export interface ReportGuard {
  aceptadas: { version: string; section: string }[];
  rechazadas: { version: string; section: string; reasons: string[] }[];
  secciones_aceptadas: number;
  secciones_rechazadas: number;
}

/**
 * Scope the report was composed from. Optional in the contract because the
 * screen renders the sections, not this block; typed for completeness.
 */
export interface ReportScope {
  events_analysed: number;
  incidents: number;
  findings: number;
  first_seen: string;
  last_seen: string;
  date: string;
  start: string;
  end: string;
  duration_minutes: number;
  levels: RiskLevelCount[];
  categories: CategoryCoverage[];
  categories_covered: string[];
  categories_covered_labels: string[];
  categories_uncovered_labels: string[];
  users: string[];
  hosts: string[];
  external_sources: string[];
  service_name_accounts: string[];
  incident_ids: string[];
}

/** `POST /api/report` success body. */
export interface ReportPayload {
  versions: Record<ReportVersionKey, ReportVersion>;
  narrative: ReportNarrative;
  scope?: ReportScope;
  guard?: ReportGuard;
}

/** A PDF already fetched from the backend, with the name it suggests. */
export interface ReportDownload {
  blob: Blob;
  filename: string;
}
