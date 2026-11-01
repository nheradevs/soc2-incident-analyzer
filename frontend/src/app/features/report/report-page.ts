import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { ApiFailure } from '../../core/models/ingest.models';
import {
  ReportDownload,
  ReportPayload,
  ReportScope,
  ReportVersion,
  ReportVersionKey,
} from '../../core/models/report.models';
import { ReportApiService } from '../../core/services/report-api.service';
import { narrativeStateLine, versionTabLabel } from './report-format';
import { ReportVersionPanel } from './report-version';

/**
 * The Informe step (FSD RF5, S5) and its PDF download (RF6, S6).
 *
 * The whole view is driven by `POST /api/report`: the screen renders the nine
 * sections of the payload, in payload order and without completing anything. A
 * 409 means nothing has been uploaded yet, so the page shows that message
 * verbatim with the way back to the load step.
 */
@Component({
  selector: 'app-report-page',
  imports: [ReportVersionPanel, RouterLink],
  templateUrl: './report-page.html',
  styleUrl: './report-page.scss',
})
export class ReportPage implements OnInit, OnDestroy {
  private readonly api = inject(ReportApiService);

  readonly payload = signal<ReportPayload | null>(null);
  readonly loading = signal(true);
  readonly failure = signal<ApiFailure | null>(null);
  /** Keeps the failure card on screen while a retry is in flight. */
  readonly retrying = signal(false);
  readonly version = signal<ReportVersionKey>('ejecutiva');
  readonly downloading = signal(false);
  readonly downloadFailure = signal<ApiFailure | null>(null);

  /** Both audience versions, in the order the FSD names them. */
  readonly versions: { key: ReportVersionKey; label: string }[] = [
    { key: 'ejecutiva', label: versionTabLabel('ejecutiva') },
    { key: 'tecnica', label: versionTabLabel('tecnica') },
  ];

  readonly activeVersion = computed<ReportVersion | null>(() => {
    const payload = this.payload();
    return payload === null ? null : payload.versions[this.version()];
  });

  /** The download action names the version that is on screen. */
  readonly downloadLabel = computed(
    () =>
      `Descargar PDF · ${
        this.version() === 'tecnica' ? 'versión técnica' : 'versión ejecutiva'
      }`,
  );

  readonly scope = computed<ReportScope | null>(() => this.payload()?.scope ?? null);

  readonly narrativeLine = computed(() => narrativeStateLine(this.payload()?.narrative.estado));

  private reportSubscription: Subscription | null = null;
  private downloadSubscription: Subscription | null = null;

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.reportSubscription?.unsubscribe();
    this.downloadSubscription?.unsubscribe();
    this.reportSubscription = null;
    this.downloadSubscription = null;
  }

  reload(): void {
    this.retrying.set(true);
    this.load(true);
  }

  selectVersion(key: string): void {
    if (key === 'ejecutiva' || key === 'tecnica') {
      this.version.set(key);
    }
  }

  /**
   * Fetch the PDF as a blob and hand it to the browser under the suggested name.
   *
   * The backend returns one PDF that carries both versions, so the action is
   * labelled with the active version but the file itself is the same one.
   */
  downloadPdf(): void {
    if (this.downloading()) {
      return;
    }
    this.downloadSubscription?.unsubscribe();
    this.downloading.set(true);
    this.downloadFailure.set(null);

    this.downloadSubscription = this.api.downloadReportPdf().subscribe({
      next: (download: ReportDownload) => {
        this.downloading.set(false);
        this.api.saveReport(download);
      },
      error: (failure: ApiFailure) => {
        this.downloadFailure.set(failure);
        this.downloading.set(false);
      },
    });
  }

  private load(keepFailureOnStart = false): void {
    this.reportSubscription?.unsubscribe();
    if (!keepFailureOnStart) {
      this.loading.set(true);
      this.failure.set(null);
      this.downloadFailure.set(null);
      this.payload.set(null);
      this.version.set('ejecutiva');
    }

    this.reportSubscription = this.api.report().subscribe({
      next: (payload: ReportPayload) => {
        this.payload.set(payload);
        this.failure.set(null);
        this.loading.set(false);
        this.retrying.set(false);
      },
      error: (failure: ApiFailure) => {
        this.failure.set(failure);
        this.payload.set(null);
        this.loading.set(false);
        this.retrying.set(false);
      },
    });
  }
}
