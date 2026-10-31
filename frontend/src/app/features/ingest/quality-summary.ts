import { Component, computed, input } from '@angular/core';

import { TimeRange, UploadResponse } from '../../core/models/ingest.models';

interface CountEntry {
  key: string;
  value: number;
}

/** RF1 quality feedback: what the loaded export actually contains, nothing invented. */
@Component({
  selector: 'app-quality-summary',
  templateUrl: './quality-summary.html',
  styleUrl: './quality-summary.scss',
})
export class QualitySummary {
  readonly summary = input<UploadResponse | null>(null);

  /** Columns with at least one null: a zero-null column is noise, not a finding. */
  readonly nullCounts = computed<CountEntry[]>(() =>
    this.entries(this.summary()?.quality.null_counts ?? {}).filter((entry) => entry.value > 0),
  );

  formatTime(value: string | null): string {
    if (value === null || value === '') {
      return 'sin datos';
    }
    return value.slice(0, 19).replace('T', ' ');
  }

  timeRange(range: TimeRange): string {
    if (range.start === null && range.end === null) {
      return 'sin timestamps interpretables';
    }
    return `${this.formatTime(range.start)} → ${this.formatTime(range.end)}`;
  }

  counts(record: Record<string, number>): string {
    const entries = this.entries(record);
    if (entries.length === 0) {
      return 'ninguno';
    }
    return entries.map((entry) => `${entry.key} (${entry.value})`).join(', ');
  }

  private entries(record: Record<string, number>): CountEntry[] {
    return Object.keys(record)
      .map((key) => ({ key, value: record[key] }))
      .sort((left, right) => right.value - left.value || left.key.localeCompare(right.key));
  }
}
