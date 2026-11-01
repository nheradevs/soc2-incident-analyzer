import { Component, computed, input, signal } from '@angular/core';

import {
  AttackType,
  DashboardPayload,
  HostCount,
  HourBucket,
  IncidentSummary,
  OutboundDestination,
} from '../../core/models/analysis.models';
import { formatPort, hasKnownBytes } from './analysis-format';

/**
 * Maximum impact the risk matrix assigns to each detector. It is a fixed
 * property of the rule engine, not a per-run measurement, so it is not part of
 * the payload; the mapping is the one documented for `backend/app/risk/matrix.py`.
 */
const DETECTOR_LEVELS: Record<string, string> = {
  D1a: 'medium',
  D1b: 'high',
  D1c: 'medium',
  D1d: 'critical',
  D2: 'high',
  D3: 'critical',
  D4: 'critical',
  D5: 'high',
  D6: 'high',
  D7: 'high',
};

const LEVEL_LABELS: Record<string, string> = {
  critical: 'Crítico',
  high: 'Alto',
  medium: 'Medio',
  low: 'Bajo',
  none: 'Sin incidente',
};

/** Severity order used to pick the most severe incident that touches a host. */
const LEVEL_RANK: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  none: 0,
};

const HOST_LEVEL_LABELS: Record<string, string> = {
  critical: 'Equipo con incidente crítico',
  high: 'Equipo con incidente alto',
  medium: 'Equipo con incidente medio',
  low: 'Equipo con incidente bajo',
  none: 'Sin incidente',
};

const BAR_AREA_PX = 128;
const HOUR_MS = 60 * 60 * 1000;

interface AttackTypeBar extends AttackType {
  level: string;
  width: number;
}

interface HostBar extends HostCount {
  level: string;
  width: number;
}

/** One hourly tramo, with the share and the incidents that cross it. */
interface HourDetail {
  bucket: HourBucket;
  isPeak: boolean;
  percentage: string;
  incidents: string[];
}

const PERCENT_FORMAT = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const INTEGER_FORMAT = new Intl.NumberFormat('es-ES');

/**
 * RF4 charts.
 *
 * Every series is built from the payload as returned: no placeholder bucket and
 * no sample incident. There is deliberately no "top source IPs" chart.
 *
 * The hourly chart is a selector, not a picture: each column is a button, the
 * selected tramo is real component state and the initial selection is the peak
 * bucket. A refresh of the payload keeps the selection when that tramo still
 * exists, so the reader does not lose their place.
 */
@Component({
  selector: 'app-dashboard-charts',
  templateUrl: './dashboard-charts.html',
  styleUrl: './dashboard-charts.scss',
})
export class DashboardCharts {
  readonly payload = input.required<DashboardPayload>();

  /** Tramo picked by the reader; `null` means "use the peak". */
  readonly selectedHour = signal<string | null>(null);

  readonly hourly = computed(() => this.payload().charts.events_by_hour);

  readonly peakHour = computed<HourBucket | null>(() => {
    let peak: HourBucket | null = null;
    for (const bucket of this.hourly()) {
      if (peak === null || bucket.events > peak.events) {
        peak = bucket;
      }
    }
    return peak;
  });

  readonly activeHour = computed<HourBucket | null>(() => {
    const buckets = this.hourly();
    const selected = this.selectedHour();
    const found = buckets.find((bucket) => bucket.hour === selected);
    return found ?? this.peakHour();
  });

  readonly hourDetail = computed<HourDetail | null>(() => {
    const bucket = this.activeHour();
    if (bucket === null) {
      return null;
    }
    const total = this.payload().coverage.events_analysed;
    const percentage = total > 0 ? PERCENT_FORMAT.format((bucket.events / total) * 100) : '0,0';
    return {
      bucket,
      isPeak: bucket.hour === this.peakHour()?.hour,
      percentage,
      incidents: this.incidentsFor(bucket),
    };
  });

  readonly maxHourEvents = computed(() =>
    Math.max(...this.hourly().map((bucket) => bucket.events), 1),
  );

  readonly attackTypeBars = computed<AttackTypeBar[]>(() => {
    const types = this.payload().charts.attack_types;
    const max = Math.max(...types.map((type) => type.findings), 1);
    return types.map((type) => ({
      ...type,
      level: DETECTOR_LEVELS[type.code] ?? 'none',
      width: Math.max((type.findings / max) * 100, 3),
    }));
  });

  readonly attackTypeLegend = computed(() => this.levelsOf(this.attackTypeBars()));

  readonly hostBars = computed<HostBar[]>(() => {
    const hosts = this.payload().charts.top_hosts;
    const max = Math.max(...hosts.map((host) => host.events), 1);
    return hosts.map((host) => ({
      ...host,
      level: this.hostLevel(host.host),
      width: Math.max((host.events / max) * 100, 3),
    }));
  });

  readonly hostLegend = computed(() => this.levelsOf(this.hostBars()));

  readonly outboundItems = computed<OutboundDestination[]>(
    () => this.payload().charts.outbound_by_destination.items,
  );

  readonly outboundTotal = computed(() => this.payload().charts.outbound_by_destination);

  /** Selection is a real state change; the same tramo clicked again stays selected. */
  selectHour(hour: string): void {
    this.selectedHour.set(hour);
  }

  isActiveHour(bucket: HourBucket): boolean {
    return this.activeHour()?.hour === bucket.hour;
  }

  barHeight(events: number): number {
    return Math.max(Math.round((events / this.maxHourEvents()) * BAR_AREA_PX), 2);
  }

  levelLabel(level: string): string {
    return LEVEL_LABELS[level] ?? level;
  }

  hostLevelLabel(level: string): string {
    return HOST_LEVEL_LABELS[level] ?? level;
  }

  portLabel(port: number | null): string {
    return formatPort(port);
  }

  hasMeasuredBytes(destination: OutboundDestination): boolean {
    return hasKnownBytes(destination);
  }

  formatInteger(value: number): string {
    return INTEGER_FORMAT.format(value);
  }

  /** Incident ids whose window crosses the bucket, in payload order. */
  private incidentsFor(bucket: HourBucket): string[] {
    const start = this.bucketStart(bucket);
    if (start === null) {
      return [];
    }
    const end = start.getTime() + HOUR_MS;
    return this.payload()
      .incidents.filter((incident) => this.crosses(incident, start.getTime(), end))
      .map((incident) => incident.id);
  }

  private crosses(incident: IncidentSummary, start: number, end: number): boolean {
    const first = Date.parse(incident.first_seen);
    const last = Date.parse(incident.last_seen);
    if (Number.isNaN(first) || Number.isNaN(last)) {
      return false;
    }
    return first < end && last >= start;
  }

  /** Start of the bucket: the ISO value when present, otherwise its hour label. */
  private bucketStart(bucket: HourBucket): Date | null {
    const direct = new Date(bucket.hour);
    if (!Number.isNaN(direct.getTime())) {
      return direct;
    }
    const match = /^(\d{1,2}):(\d{2})/.exec(bucket.label);
    const windowStart = Date.parse(this.payload().coverage.time_window.start ?? '');
    if (match === null || Number.isNaN(windowStart)) {
      return null;
    }
    const base = new Date(windowStart);
    base.setHours(Number(match[1]), Number(match[2]), 0, 0);
    return base;
  }

  /** Most severe incident that touches the host, or `none` when it has no incident. */
  private hostLevel(host: string): string {
    const target = this.normalizeHost(host);
    let level = 'none';
    for (const incident of this.payload().incidents) {
      const touched = incident.entities.hosts.some(
        (candidate) => this.normalizeHost(candidate) === target,
      );
      if (!touched) {
        continue;
      }
      if (LEVEL_RANK[incident.level_key] > LEVEL_RANK[level]) {
        level = incident.level_key;
      }
    }
    return level;
  }

  private normalizeHost(host: string): string {
    return host.toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  private levelsOf(bars: { level: string }[]): string[] {
    const present = new Set(bars.map((bar) => bar.level));
    return Object.keys(LEVEL_RANK).filter((level) => present.has(level));
  }
}
