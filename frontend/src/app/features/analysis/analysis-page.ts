import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Subscription } from 'rxjs';

import { DashboardPayload } from '../../core/models/analysis.models';
import { ApiFailure } from '../../core/models/ingest.models';
import { AnalysisApiService } from '../../core/services/analysis-api.service';
import { CoveragePanel } from './coverage-panel';
import { DashboardCharts } from './dashboard-charts';
import { DashboardKpis } from './dashboard-kpis';
import { IncidentDetail } from './incident-detail';
import { IncidentList } from './incident-list';

/**
 * The Analizar step (FSD RF4): KPIs, charts, incident list and drill-down.
 *
 * The whole view is driven by `POST /api/analyze`. When nothing has been
 * uploaded the backend answers 409 with a Spanish message; the page shows that
 * message verbatim and offers the way back to the load step instead of
 * inventing an empty dashboard.
 */
@Component({
  selector: 'app-analysis-page',
  imports: [
    MatButtonModule,
    MatProgressSpinnerModule,
    CoveragePanel,
    DashboardCharts,
    DashboardKpis,
    IncidentDetail,
    IncidentList,
    RouterLink,
  ],
  templateUrl: './analysis-page.html',
  styleUrl: './analysis-page.scss',
})
export class AnalysisPage implements OnInit, OnDestroy {
  private readonly api = inject(AnalysisApiService);

  readonly payload = signal<DashboardPayload | null>(null);
  readonly loading = signal(true);
  readonly failure = signal<ApiFailure | null>(null);
  readonly selectedId = signal<string | null>(null);

  private subscription: Subscription | null = null;

  ngOnInit(): void {
    this.load();
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
    this.subscription = null;
  }

  reload(): void {
    this.load();
  }

  select(incidentId: string): void {
    this.selectedId.set(incidentId);
  }

  closeDetail(): void {
    this.selectedId.set(null);
  }

  private load(): void {
    this.subscription?.unsubscribe();
    this.loading.set(true);
    this.failure.set(null);
    this.payload.set(null);
    this.selectedId.set(null);

    this.subscription = this.api.analyze().subscribe({
      next: (payload: DashboardPayload) => {
        this.payload.set(payload);
        this.loading.set(false);
      },
      error: (failure: ApiFailure) => {
        this.failure.set(failure);
        this.loading.set(false);
      },
    });
  }
}
