import { Component, computed, input } from '@angular/core';
import { ChartConfiguration } from 'chart.js';

import {
  DashboardPayload,
  OutboundDestination,
} from '../../core/models/analysis.models';
import {
  formatBytes,
  formatPort,
  hasKnownBytes,
} from './analysis-format';
import { ChartCanvas } from './chart-canvas';

// Decimal megabytes, the unit the FSD uses for the measured outbound volume.
const BYTES_PER_MB = 1_000_000;

const PRIMARY = '#1565c0';
const ACCENT = '#00695c';
/** Grey for a destination whose volume the export does not measure. */
const UNKNOWN_BYTES = '#8a8a8a';

const LEVEL_COLORS: Record<string, string> = {
  critical: '#b3261e',
  high: '#b45309',
  medium: '#8a6100',
  low: '#2e7d32',
};

/** Palette used when a level key is unknown: no colour implies a rank. */
const FALLBACK_COLOR = '#5f6368';

const NO_LEGEND = { legend: { display: false } };

/**
 * RF4 charts.
 *
 * Every series is built from the payload as returned: no placeholder bucket and
 * no sample incident. There is deliberately no "top source IPs" chart (§4.8).
 * The outbound chart plots measured megabytes only; a destination whose rows
 * carry no `bytes_out` is drawn without a bar, coloured differently and labelled
 * "bytes no registrados" instead of being shown as zero traffic.
 */
@Component({
  selector: 'app-dashboard-charts',
  imports: [ChartCanvas],
  templateUrl: './dashboard-charts.html',
  styleUrl: './dashboard-charts.scss',
})
export class DashboardCharts {
  readonly payload = input.required<DashboardPayload>();

  readonly hourly = computed<ChartConfiguration>(() => {
    const buckets = this.payload().charts.events_by_hour;
    return {
      type: 'bar',
      data: {
        labels: buckets.map((bucket) => bucket.label),
        datasets: [
          {
            label: 'Eventos',
            data: buckets.map((bucket) => bucket.events),
            backgroundColor: PRIMARY,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: NO_LEGEND,
        scales: { y: { beginAtZero: true, title: { display: true, text: 'Eventos' } } },
      },
    };
  });

  readonly levels = computed<ChartConfiguration>(() => {
    const levels = this.payload().risk.levels;
    return {
      type: 'doughnut',
      data: {
        labels: levels.map((level) => `${level.level}: ${level.incidents}`),
        datasets: [
          {
            label: 'Incidentes',
            data: levels.map((level) => level.incidents),
            backgroundColor: levels.map(
              (level) => LEVEL_COLORS[level.level_key] ?? FALLBACK_COLOR,
            ),
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
      },
    };
  });

  readonly hosts = computed<ChartConfiguration>(() => {
    const hosts = this.payload().charts.top_hosts;
    return this.ranking('Eventos por host', hosts.map((item) => item.host), hosts.map((item) => item.events), PRIMARY);
  });

  readonly users = computed<ChartConfiguration>(() => {
    const users = this.payload().charts.top_users;
    return this.ranking(
      'Eventos por cuenta',
      users.map((item) => item.user),
      users.map((item) => item.events),
      ACCENT,
    );
  });

  readonly attackTypes = computed<ChartConfiguration>(() => {
    const types = this.payload().charts.attack_types;
    return this.ranking(
      'Hallazgos por tipo de ataque',
      types.map((type) => `${type.label} (${type.code})`),
      types.map((type) => type.findings),
      '#6a1b9a',
    );
  });

  readonly outbound = computed<ChartConfiguration>(() => {
    const items = this.outboundItems();
    return {
      type: 'bar',
      data: {
        labels: items.map((item) => `${item.destination}${formatPort(item.port)}`),
        datasets: [
          {
            label: 'Volumen saliente (MB)',
            data: items.map((item) =>
              hasKnownBytes(item) ? item.bytes_out / BYTES_PER_MB : null,
            ),
            backgroundColor: items.map((item) =>
              hasKnownBytes(item) ? ACCENT : UNKNOWN_BYTES,
            ),
            borderColor: items.map((item) => (hasKnownBytes(item) ? ACCENT : UNKNOWN_BYTES)),
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: NO_LEGEND,
        scales: { y: { beginAtZero: true, title: { display: true, text: 'Megabytes' } } },
      },
    };
  });

  readonly outboundItems = computed<OutboundDestination[]>(
    () => this.payload().charts.outbound_by_destination.items,
  );

  readonly outboundTotal = computed(() => this.payload().charts.outbound_by_destination);

  readonly hourlyNote = computed(() => {
    const buckets = this.payload().charts.events_by_hour;
    return buckets
      .map((bucket) => `${bucket.label}: ${bucket.events}`)
      .join(' · ');
  });

  readonly outboundDescription = computed(() => {
    const items = this.outboundItems();
    const unknown = items.filter((item) => !hasKnownBytes(item)).length;
    return (
      `Volumen saliente por destino externo: ${items.length} destinos, ` +
      `${unknown} con bytes no registrados en el export.`
    );
  });

  bytesLabel(bytes: number): string {
    return formatBytes(bytes);
  }

  portLabel(port: number | null): string {
    return formatPort(port);
  }

  hasMeasuredBytes(destination: OutboundDestination): boolean {
    return hasKnownBytes(destination);
  }

  /** Horizontal ranking: the payload order is the ranking, so it is not re-sorted. */
  private ranking(
    label: string,
    labels: string[],
    values: number[],
    color: string,
  ): ChartConfiguration {
    return {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label, data: values, backgroundColor: color, borderRadius: 4 }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: NO_LEGEND,
        scales: { x: { beginAtZero: true } },
      },
    };
  }
}
