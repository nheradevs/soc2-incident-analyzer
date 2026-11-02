/** Typed contract of the two RF1 endpoints. Identifiers stay English, values Spanish. */

export type SortOrder = 'asc' | 'desc';

/** One cell of a normalized event row; the API serializes NaN/NaT as `null`. */
export type EventValue = string | number | boolean | null;

/** A row keyed by the column names the API returns (original plus derived). */
export type EventRow = Record<string, EventValue>;

export interface TimeRange {
  start: string | null;
  end: string | null;
}

/** Raw spellings that normalize to one host, e.g. `DC-01` / `DC01`. */
export interface DuplicateHost {
  host_norm: string;
  spellings: string[];
  spelling_counts: Record<string, number>;
  row_count: number;
}

/** Mixed numeric/named `Event_ID` evidence (FSD §4.1). */
export interface EventIdTypes {
  mixed: boolean;
  numeric_count: number;
  named_count: number;
  named_ids: Record<string, number>;
  raw_types: Record<string, number>;
}

export interface TimestampParseFailures {
  count: number;
  log_ids: string[];
}

export interface QualityReport {
  row_count: number;
  column_count: number;
  detected_columns: string[];
  null_counts: Record<string, number>;
  duplicate_hosts: DuplicateHost[];
  event_id_types: EventIdTypes;
  timestamp_parse_failures: TimestampParseFailures;
}

/**
 * `POST /api/upload` success body. `GET /api/session` returns this same shape
 * when the server already holds a file, so one type rebuilds the load panel
 * whether the export arrived in this tab or in an earlier session.
 */
export interface UploadResponse {
  file_name: string;
  detected_columns: string[];
  row_count: number;
  time_range: TimeRange;
  quality: QualityReport;
}

/** Query of `GET /api/events`; the backend clamps `pageSize` to 200. */
export interface EventsQuery {
  page: number;
  pageSize: number;
  search?: string;
  sort?: string | null;
  order?: SortOrder;
}

/** `GET /api/events` success body. */
export interface EventsPage {
  items: EventRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  columns: string[];
}

/** Normalized HTTP failure: `message` is the backend `detail`, verbatim. */
export interface ApiFailure {
  status: number;
  message: string;
}

/**
 * Whether retrying the same request can change the outcome.
 *
 * A network failure, a rate limit or a server error might succeed on a second
 * attempt. A rejected file or a missing session will fail identically, so
 * offering "retry" there would be a button that cannot do anything.
 */
export function isRetryableFailure(failure: ApiFailure): boolean {
  return failure.status === 0 || failure.status === 429 || failure.status >= 500;
}
