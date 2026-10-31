import { Component, input, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { IncidentSummary } from '../../core/models/analysis.models';
import { formatTimestamp } from './analysis-format';

/**
 * RF4 incident list.
 *
 * The order is the payload's order (most severe first, then chronological);
 * sorting again here would be a second source of truth for severity.
 */
@Component({
  selector: 'app-incident-list',
  imports: [MatIconModule],
  templateUrl: './incident-list.html',
  styleUrl: './incident-list.scss',
})
export class IncidentList {
  readonly incidents = input.required<IncidentSummary[]>();
  readonly selectedId = input<string | null>(null);
  readonly selected = output<string>();

  readonly formatTimestamp = formatTimestamp;
}
