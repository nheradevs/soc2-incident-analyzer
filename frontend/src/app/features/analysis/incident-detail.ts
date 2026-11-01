import {
  Component,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { MatTableModule } from '@angular/material/table';
import { Subscription } from 'rxjs';

import { IncidentDetail as IncidentDrilldown } from '../../core/models/analysis.models';
import { ApiFailure, EventRow } from '../../core/models/ingest.models';
import { AnalysisApiService } from '../../core/services/analysis-api.service';
import { formatTimestamp } from './analysis-format';

const LOG_ID = 'Log_ID';

/**
 * RF4 drill-down of one incident: classification, every finding with the
 * justification the risk matrix wrote, and the cited log rows.
 *
 * The same row may be cited by more than one finding, so the evidence table is
 * deduplicated by `Log_ID` and the panel states how many distinct rows the
 * incident really has next to how many citations that represents.
 */
@Component({
  selector: 'app-incident-detail',
  imports: [MatTableModule],
  templateUrl: './incident-detail.html',
  styleUrl: './incident-detail.scss',
})
export class IncidentDetail implements OnChanges, OnDestroy {
  private readonly api = inject(AnalysisApiService);

  readonly incidentId = input.required<string>();
  readonly closed = output<void>();

  readonly detail = signal<IncidentDrilldown | null>(null);
  readonly loading = signal(false);
  readonly failure = signal<ApiFailure | null>(null);

  readonly formatTimestamp = formatTimestamp;

  private subscription: Subscription | null = null;
  private requestCounter = 0;

  /** Evidence rows of the whole incident, one entry per distinct `Log_ID`. */
  readonly evidenceRows = computed<EventRow[]>(() => {
    const detail = this.detail();
    if (detail === null) {
      return [];
    }
    const seen = new Set<string>();
    const rows: EventRow[] = [];
    for (const finding of detail.findings) {
      for (const row of finding.evidence_rows) {
        const key = this.rowKey(row);
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        rows.push(row);
      }
    }
    return rows;
  });

  /** How many times the findings cite a row, duplicates included. */
  readonly totalCitations = computed(() =>
    (this.detail()?.findings ?? []).reduce(
      (total, finding) => total + finding.evidence_rows.length,
      0,
    ),
  );

  /** Columns of the evidence table, with `Log_ID` always first. */
  readonly evidenceColumns = computed<string[]>(() => {
    const columns: string[] = [];
    const seen = new Set<string>();
    for (const row of this.evidenceRows()) {
      for (const column of Object.keys(row)) {
        if (!seen.has(column)) {
          seen.add(column);
          columns.push(column);
        }
      }
    }
    const index = columns.indexOf(LOG_ID);
    if (index > 0) {
      columns.splice(index, 1);
      columns.unshift(LOG_ID);
    }
    return columns;
  });

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['incidentId'] !== undefined) {
      this.load(this.incidentId());
    }
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
    this.subscription = null;
  }

  cellText(row: EventRow, column: string): string {
    const value = row[column];
    if (value === null || value === undefined) {
      return 'Sin datos';
    }
    return String(value);
  }

  close(): void {
    this.closed.emit();
  }

  private load(incidentId: string): void {
    const requestId = ++this.requestCounter;
    this.subscription?.unsubscribe();
    this.loading.set(true);
    this.failure.set(null);
    this.detail.set(null);

    this.subscription = this.api.incident(incidentId).subscribe({
      next: (detail: IncidentDrilldown) => {
        if (requestId !== this.requestCounter) {
          return;
        }
        this.detail.set(detail);
        this.loading.set(false);
      },
      error: (failure: ApiFailure) => {
        if (requestId !== this.requestCounter) {
          return;
        }
        this.failure.set(failure);
        this.loading.set(false);
      },
    });
  }

  private rowKey(row: EventRow): string {
    const logId = row[LOG_ID];
    if (typeof logId === 'string' && logId !== '') {
      return logId;
    }
    if (logId !== null && logId !== undefined) {
      return String(logId);
    }
    return JSON.stringify(row);
  }
}
