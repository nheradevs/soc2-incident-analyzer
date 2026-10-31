import {
  DashboardPayload,
  IncidentDetail,
  IncidentFinding,
  RiskRating,
} from '../models/analysis.models';
import { EventRow } from '../models/ingest.models';

/**
 * Realistic shape of `POST /api/analyze`, mirroring the measured real export:
 * two incidents (one crítico, one alto), the six categories always present with
 * the uncovered ones named, and one external destination whose byte count the
 * export does not carry.
 */
export function dashboardPayloadFixture(
  overrides: Partial<DashboardPayload> = {},
): DashboardPayload {
  return {
    coverage: {
      events_analysed: 715,
      events_without_timestamp: 0,
      incidents: 2,
      findings: 3,
      time_window: {
        start: '2026-10-23T07:46:07',
        end: '2026-10-23T13:44:06',
        duration_minutes: 358,
        hours: 7,
      },
      categories: [
        { category: 'brute-force', label: 'fuerza bruta', findings: 2, incidents: 1 },
        {
          category: 'suspicious-logon',
          label: 'inicio de sesión sospechoso',
          findings: 1,
          incidents: 1,
        },
        {
          category: 'privilege-escalation',
          label: 'escalamiento de privilegios',
          findings: 0,
          incidents: 0,
        },
        { category: 'command-execution', label: 'ejecución de comandos', findings: 0, incidents: 0 },
        { category: 'lateral-movement', label: 'movimiento lateral', findings: 0, incidents: 0 },
        { category: 'other-anomaly', label: 'otra anomalía', findings: 0, incidents: 0 },
      ],
      covered_categories: ['brute-force', 'suspicious-logon'],
      uncovered_categories: [
        'privilege-escalation',
        'command-execution',
        'lateral-movement',
        'other-anomaly',
      ],
    },
    risk: {
      levels: [
        { level: 'crítico', level_key: 'critical', incidents: 1, findings: 2 },
        { level: 'alto', level_key: 'high', incidents: 1, findings: 1 },
        { level: 'medio', level_key: 'medium', incidents: 0, findings: 0 },
        { level: 'bajo', level_key: 'low', incidents: 0, findings: 0 },
      ],
      incidents_total: 2,
      findings_total: 3,
      affected: {
        users: ['admin', 'jlopez'],
        hosts: ['DC01', 'WEB-01'],
        external_sources: ['203.0.113.74'],
      },
    },
    charts: {
      events_by_hour: [
        { hour: '2026-10-23T07:00:00', label: '07:00', events: 180 },
        { hour: '2026-10-23T08:00:00', label: '08:00', events: 265 },
        { hour: '2026-10-23T09:00:00', label: '09:00', events: 270 },
      ],
      top_hosts: [
        { host: 'DC01', events: 121 },
        { host: 'WEB-01', events: 96 },
      ],
      top_users: [
        { user: 'admin', events: 34 },
        { user: 'jlopez', events: 21 },
      ],
      excluded_accounts: [
        { principal: '-', kind: 'anonymous', reason: 'principal anónimo', events: 21 },
        {
          principal: 'IIS APPPOOL\\DefaultAppPool',
          kind: 'machine',
          reason: 'cuenta de servicio o de máquina',
          events: 1,
        },
      ],
      attack_types: [
        { code: 'D1a', label: 'Fuerza bruta dirigida', findings: 2, events: 8 },
        { code: 'D7', label: 'Exfiltración', findings: 1, events: 22 },
      ],
      outbound_by_destination: {
        items: [
          {
            destination: '198.51.100.88',
            port: 443,
            events: 22,
            events_with_bytes: 22,
            bytes_out: 253305558,
          },
          {
            destination: '203.0.113.88',
            port: 80,
            events: 1,
            events_with_bytes: 0,
            bytes_out: 0,
          },
        ],
        total_events: 23,
        total_bytes: 253305558,
      },
    },
    incidents: [
      {
        id: 'INC-20261023-0820',
        title: 'Fuerza bruta RDP con origen externo',
        level: 'crítico',
        level_key: 'critical',
        categories: ['brute-force'],
        categories_labels: ['fuerza bruta'],
        first_seen: '2026-10-23T08:20:12',
        last_seen: '2026-10-23T08:34:40',
        event_count: 8,
        entities: {
          users: ['admin'],
          hosts: ['DC01'],
          source_ips: ['203.0.113.74'],
          shares: [],
        },
        requires_validation: false,
      },
      {
        id: 'INC-20261023-1137',
        title: 'Lectura secuencial masiva de archivos',
        level: 'alto',
        level_key: 'high',
        categories: ['other-anomaly'],
        categories_labels: ['otra anomalía'],
        first_seen: '2026-10-23T11:37:02',
        last_seen: '2026-10-23T11:41:18',
        event_count: 23,
        entities: {
          users: ['svc_backup'],
          hosts: ['FS-01'],
          source_ips: ['10.10.1.14'],
          shares: ['\\\\FS-01\\backups'],
        },
        requires_validation: true,
      },
    ],
    ...overrides,
  };
}

export function riskRatingFixture(overrides: Partial<RiskRating> = {}): RiskRating {
  return {
    level: 'crítico',
    level_key: 'critical',
    impact: 'crítico',
    confidence: 'alta',
    event_count: 4,
    requires_validation: false,
    justification:
      'Criticidad crítico: impacto crítico con confianza alta sobre 4 eventos de evidencia; ' +
      'el origen es una IP externa y la cuenta afectada es privilegiada.',
    ...overrides,
  };
}

export function evidenceRowFixture(logId: string, overrides: EventRow = {}): EventRow {
  return {
    Log_ID: logId,
    Timestamp: '2026-10-23T08:27:11',
    Hostname: 'DC01',
    Event_ID: 4625,
    User: 'CORP\\admin',
    Source_IP: '203.0.113.74',
    Log_Source: 'Security',
    Event_Description: 'An account failed to log on',
    ...overrides,
  };
}

export function incidentFindingFixture(
  overrides: Partial<IncidentFinding> = {},
): IncidentFinding {
  return {
    id: 'D1a:rdp@203.0.113.74@2026-10-23T08:20:12',
    code: 'D1a',
    category: 'brute-force',
    title: 'Fuerza bruta dirigida contra «admin»',
    entities: {
      users: ['admin'],
      hosts: ['DC01'],
      source_ips: ['203.0.113.74'],
      shares: [],
    },
    event_count: 4,
    first_seen: '2026-10-23T08:20:12',
    last_seen: '2026-10-23T08:36:40',
    evidence: ['EVT-00126', 'EVT-00130'],
    severity_hint: 'high',
    requires_validation: false,
    rationale:
      'Cuatro fallos de autenticación desde una IP externa contra la misma cuenta en 16 minutos.',
    measured_bytes: null,
    risk: riskRatingFixture(),
    evidence_rows: [
      evidenceRowFixture('EVT-00126'),
      evidenceRowFixture('EVT-00130', { Timestamp: '2026-10-23T08:36:40' }),
    ],
    ...overrides,
  };
}

/**
 * Realistic shape of `GET /api/incidents/{id}`. The second finding cites
 * `EVT-00130`, which the first finding already cites: the panel must show three
 * distinct rows, not four.
 */
export function incidentDetailFixture(
  overrides: Partial<IncidentDetail> = {},
): IncidentDetail {
  return {
    id: 'INC-20261023-0820',
    title: 'Fuerza bruta RDP con origen externo',
    level: 'crítico',
    level_key: 'critical',
    categories: ['brute-force'],
    categories_labels: ['fuerza bruta'],
    first_seen: '2026-10-23T08:20:12',
    last_seen: '2026-10-23T08:34:40',
    event_count: 8,
    entities: {
      users: ['admin'],
      hosts: ['DC01'],
      source_ips: ['203.0.113.74'],
      shares: [],
    },
    requires_validation: false,
    evidence: ['EVT-00126', 'EVT-00130', 'EVT-00127'],
    severity_hint: 'critical',
    narrative:
      'Cuatro fallos de autenticación desde una IP externa seguidos de un inicio de sesión correcto.',
    risk: riskRatingFixture(),
    findings: [
      incidentFindingFixture(),
      incidentFindingFixture({
        id: 'D1d:logon@admin@2026-10-23T08:34:40',
        code: 'D1d',
        category: 'suspicious-logon',
        title: 'Inicio de sesión posterior al ataque',
        event_count: 2,
        evidence: ['EVT-00130', 'EVT-00127'],
        severity_hint: 'medium',
        rationale: 'Inicio de sesión correcto de «admin» desde la misma IP externa.',
        risk: riskRatingFixture({
          level: 'alto',
          level_key: 'high',
          impact: 'alto',
          confidence: 'media',
          event_count: 2,
          justification:
            'Criticidad alto: el inicio de sesión llega desde la IP externa del ataque previo, ' +
            'sobre una cuenta privilegiada.',
        }),
        evidence_rows: [
          evidenceRowFixture('EVT-00130', { Timestamp: '2026-10-23T08:36:40' }),
          evidenceRowFixture('EVT-00127', { Event_ID: 4624, Timestamp: '2026-10-23T08:34:40' }),
        ],
      }),
    ],
    evidence_log_ids: ['EVT-00126', 'EVT-00130', 'EVT-00127'],
    evidence_missing: [],
    ...overrides,
  };
}
