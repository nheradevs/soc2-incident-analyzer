import { Component, signal } from '@angular/core';

import { UploadResponse } from '../../core/models/ingest.models';
import { EventsTable } from './events-table';
import { QualitySummary } from './quality-summary';
import { UploadPanel } from './upload-panel';

/** The Cargar step: load one export, report its quality and browse its events. */
@Component({
  selector: 'app-ingest-page',
  imports: [UploadPanel, QualitySummary, EventsTable],
  templateUrl: './ingest-page.html',
  styleUrl: './ingest-page.scss',
})
export class IngestPage {
  readonly summary = signal<UploadResponse | null>(null);
  readonly refreshKey = signal(0);

  onUploaded(response: UploadResponse): void {
    this.summary.set(response);
    this.refreshKey.update((value) => value + 1);
  }
}
