import { Component, input, output } from '@angular/core';

import { IncidentSummary } from '../../core/models/analysis.models';

/**
 * RF4 incident list.
 *
 * The order is the payload's order (most severe first, then chronological);
 * sorting again here would be a second source of truth for severity.
 */
@Component({
  selector: 'app-incident-list',
  templateUrl: './incident-list.html',
  styleUrl: './incident-list.scss',
})
export class IncidentList {
  readonly incidents = input.required<IncidentSummary[]>();
  readonly selectedId = input<string | null>(null);
  readonly selected = output<string>();

  /** Hour and minute of an incident timestamp, e.g. `08:20`. */
  clock(value: string | null): string {
    if (value === null || value.length < 16) {
      return 'sin hora';
    }
    return value.slice(11, 16);
  }
}
