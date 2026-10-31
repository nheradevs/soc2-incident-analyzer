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

  readonly windowLabel = computed(() => {
    const window = this.payload().coverage.time_window;
    const range = `${formatTimestamp(window.start)} → ${formatTimestamp(window.end)}`;
    return `${range} · ${formatDuration(window.duration_minutes)}`;
  });

  readonly affectedLabel = computed(() => {
    const affected = this.payload().risk.affected;
    return (
      `${affected.users.length} usuarios · ${affected.hosts.length} hosts · ` +
      `${affected.external_sources.length} orígenes externos`
    );
  });
}
