/**
 * Typed contract of the RF4 analysis endpoints (`POST /api/analyze`,
 * `GET /api/incidents/{id}`). Identifiers stay English, values Spanish.
 *
 * The payload is computed by the backend from the loaded export; nothing here
 * is optional because the dashboard must not render a section the backend did
 * not measure.
 */

import { EventRow } from './ingest.models';

/** Window of the analysed export, measured from its own timestamps. */
export interface AnalysisTimeWindow {
  start: string | null;
  end: string | null;
  duration_minutes: number;
  hours: number;
}

/** Detection coverage of one of the six categories (FSD S2), always present. */
export interface CategoryCoverage {
  category: string;
  label: string;
  findings: number;
  incidents: number;
}

export interface CoverageSummary {
  events_analysed: number;
  events_without_timestamp: number;
  incidents: number;
  findings: number;
  time_window: AnalysisTimeWindow;
  categories: CategoryCoverage[];
  covered_categories: string[];
  uncovered_categories: string[];
}

/** Counts of one risk level; `level_key` is the stable English key. */
export interface RiskLevelCount {
  level: string;
  level_key: string;
  incidents: number;
  findings: number;
}

/** Entities touched by the incidents; source IPs only when external. */
export interface AffectedEntities {
  users: string[];
  hosts: string[];
  external_sources: string[];
}

export interface RiskSummary {
  levels: RiskLevelCount[];
  incidents_total: number;
  findings_total: number;
  affected: AffectedEntities;
}

export interface HourBucket {
  hour: string;
  label: string;
  events: number;
}

export interface HostCount {
  host: string;
  events: number;
}

export interface UserCount {
  user: string;
  events: number;
}

/** Principal left out of the human ranking, and why (FSD §4.5). */
export interface ExcludedAccount {
  principal: string;
  kind: string;
  reason: string;
  events: number;
}

export interface AttackType {
  code: string;
  label: string;
  findings: number;
  events: number;
}

/**
 * External destination and the volume sent to it. `events_with_bytes` counts
 * the rows that actually carry `bytes_out`: when it is 0 the byte total is
 * unknown, not zero.
 */
export interface OutboundDestination {
  destination: string;
  port: number | null;
  events: number;
  events_with_bytes: number;
  bytes_out: number;
}

export interface OutboundVolume {
  items: OutboundDestination[];
  total_events: number;
  total_bytes: number;
}

/** Chart series of the dashboard. There is deliberately no "top source IPs". */
export interface DashboardCharts {
  events_by_hour: HourBucket[];
  top_hosts: HostCount[];
  top_users: UserCount[];
  excluded_accounts: ExcludedAccount[];
  attack_types: AttackType[];
  outbound_by_destination: OutboundVolume;
}

/** Normalized entities of an incident or finding. */
export interface IncidentEntities {
  users: string[];
  hosts: string[];
  source_ips: string[];
  shares: string[];
}

/** One row of the severity-ordered incident list on the dashboard. */
export interface IncidentSummary {
  id: string;
  title: string;
  level: string;
  level_key: string;
  categories: string[];
  categories_labels: string[];
  first_seen: string;
  last_seen: string;
  event_count: number;
  entities: IncidentEntities;
  requires_validation: boolean;
}

/** `POST /api/analyze` success body: exactly four top-level sections. */
export interface DashboardPayload {
  coverage: CoverageSummary;
  risk: RiskSummary;
  charts: DashboardCharts;
  incidents: IncidentSummary[];
}

/** Matrix factors plus the rule-written justification of one unit (RF3). */
export interface RiskRating {
  level: string;
  level_key: string;
  impact: string;
  confidence: string;
  event_count: number;
  requires_validation: boolean;
  justification: string;
}

/** One detection rule firing, joined with the rows it cites. */
export interface IncidentFinding {
  id: string;
  code: string;
  category: string;
  title: string;
  entities: IncidentEntities;
  event_count: number;
  first_seen: string;
  last_seen: string;
  evidence: string[];
  severity_hint: string;
  requires_validation: boolean;
  rationale: string;
  measured_bytes: number | null;
  risk: RiskRating;
  /** Cited rows; the same row may be cited by more than one finding. */
  evidence_rows: EventRow[];
}

/** `GET /api/incidents/{id}` success body: the drill-down of one incident. */
export interface IncidentDetail extends IncidentSummary {
  evidence: string[];
  severity_hint: string;
  narrative: string;
  risk: RiskRating;
  findings: IncidentFinding[];
  evidence_log_ids: string[];
  /** `Log_ID`s cited by a finding that do not exist in the export. */
  evidence_missing: string[];
}
