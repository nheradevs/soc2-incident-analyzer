import { EventsPage, EventRow, UploadResponse } from '../models/ingest.models';

/** Realistic shape of `POST /api/upload`, mirroring the measured export profile. */
export function uploadResponseFixture(overrides: Partial<UploadResponse> = {}): UploadResponse {
  const detectedColumns = [
    'Log_ID',
    'Timestamp',
    'Hostname',
    'Event_ID',
    'User',
    'Source_IP',
    'Destination',
    'Log_Source',
    'Event_Description',
    'Process_CommandLine',
    'Result',
    'Severity',
  ];
  return {
    file_name: 'SOC_L2_Logs.xlsx',
    detected_columns: detectedColumns,
    row_count: 715,
    time_range: { start: '2026-10-23T07:46:07', end: '2026-10-23T13:44:06' },
    quality: {
      row_count: 715,
      column_count: detectedColumns.length,
      detected_columns: detectedColumns,
      null_counts: { Destination: 262, Process_CommandLine: 540 },
      duplicate_hosts: [
        {
          host_norm: 'DC-01',
          spellings: ['DC-01', 'DC01'],
          spelling_counts: { 'DC-01': 40, DC01: 3 },
          row_count: 43,
        },
      ],
      event_id_types: {
        mixed: true,
        numeric_count: 690,
        named_count: 25,
        named_ids: { 'IIS-Start': 12, 'App-Login': 13 },
        raw_types: { int: 690, str: 25 },
      },
      timestamp_parse_failures: { count: 0, log_ids: [] },
    },
    ...overrides,
  };
}

export function eventRowFixture(logId: string, host: string): EventRow {
  return {
    Log_ID: logId,
    Timestamp: '2026-10-23T07:46:07',
    Hostname: host,
    Event_ID: '4625',
    event_family: 'auth_failure',
    ip_class: 'external',
    bytes_out: null,
  };
}

/** Realistic shape of `GET /api/events`, including original and derived columns. */
export function eventsPageFixture(overrides: Partial<EventsPage> = {}): EventsPage {
  return {
    items: [eventRowFixture('L-001', 'DC-01'), eventRowFixture('L-002', 'WEB-01')],
    total: 715,
    page: 1,
    page_size: 50,
    total_pages: 15,
    columns: [
      'Log_ID',
      'Timestamp',
      'Hostname',
      'Event_ID',
      'event_family',
      'ip_class',
      'bytes_out',
    ],
    ...overrides,
  };
}
