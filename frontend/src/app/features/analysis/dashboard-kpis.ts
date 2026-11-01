import { Component, computed, input } from '@angular/core';

import { DashboardPayload } from '../../core/models/analysis.models';
import { formatDuration, formatTimestamp } from './analysis-format';

/** RF4 KPI row: what the export contains and how severe it is, nothing else. */
@Component({
  selector: 'app-dashboard-kpis',
  templateUrl: './dashboard-kpis.html',
  styleUrl: './dashboard-kpis.scss',
})
export class DashboardKpis {
  readonly payload = input.required<DashboardPayload>();

  readonly levels = computed(() => this.payload().risk.levels);

  readonly windowStart = computed(() =>
    formatTimestamp(this.payload().coverage.time_window.start),
  );

  readonly windowEnd = computed(() => formatTimestamp(this.payload().coverage.time_window.end));

  readonly windowLabel = computed(() => {
    const window = this.payload().coverage.time_window;
    return `${formatTimestamp(window.start)} → ${formatTimestamp(window.end)} · ${formatDuration(window.duration_minutes)}`;
  });

  readonly affectedLabel = computed(() => {
    const affected = this.payload().risk.affected;
    const accounts = affected.users.length;
    const hosts = affected.hosts.length;
    const sources = affected.external_sources.length;
    return (
      `${accounts} ${accounts === 1 ? 'cuenta' : 'cuentas'} · ` +
      `${hosts} ${hosts === 1 ? 'equipo' : 'equipos'} · ` +
      `${sources} ${sources === 1 ? 'dirección externa' : 'direcciones externas'}`
    );
  });
}
