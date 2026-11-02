import { Component, OnInit, inject, signal } from '@angular/core';

import { UploadResponse } from '../../core/models/ingest.models';
import { IngestApiService } from '../../core/services/ingest-api.service';
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
export class IngestPage implements OnInit {
  private readonly api = inject(IngestApiService);

  readonly summary = signal<UploadResponse | null>(null);
  readonly refreshKey = signal(0);

  /** True until the server answers whether it already holds an export. */
  readonly checkingSession = signal(true);

  ngOnInit(): void {
    this.checkSession();
  }

  onUploaded(response: UploadResponse): void {
    this.summary.set(response);
    this.refreshKey.update((value) => value + 1);
  }

  /**
   * The session belongs to the server, not to this tab, so the panel asks for it
   * instead of trusting its own memory: a reload mid-demo must not claim there
   * is no file while the table is showing the 715 rows. The check stays pending
   * until the answer arrives, so the empty copy never flashes first.
   */
  private checkSession(): void {
    this.api.getSession().subscribe({
      next: (response: UploadResponse) => {
        // A file dropped while the check was in flight already set the newer
        // summary; this answer is older and must not overwrite it.
        if (this.summary() === null) {
          this.summary.set(response);
        }
        this.checkingSession.set(false);
      },
      error: () => {
        // A 409 is the honest empty state, which is what `summary = null` shows.
        this.checkingSession.set(false);
      },
    });
  }
}
