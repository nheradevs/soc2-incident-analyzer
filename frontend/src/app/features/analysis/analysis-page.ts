import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { DashboardPayload } from '../../core/models/analysis.models';
import { ApiFailure } from '../../core/models/ingest.models';
import { AnalysisApiService } from '../../core/services/analysis-api.service';
import { formatDuration, formatTimestamp } from './analysis-format';
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

  /** Labels of the KPI skeletons, so the loading state is Spanish too. */
  readonly skeletonLevels = [
    { key: 'critical', label: 'Crítico' },
    { key: 'high', label: 'Alto' },
    { key: 'medium', label: 'Medio' },
    { key: 'low', label: 'Bajo' },
  ];

  /** Window and volume of the analysis, built only from what the payload measured. */
  readonly lead = computed(() => {
    const data = this.payload();
    if (data === null) {
      return '';
    }
    const duration = formatDuration(data.coverage.time_window.duration_minutes);
    const incidents = data.coverage.incidents;
    return (
      `${duration} de actividad agrupada en ${incidents} ` +
      `${incidents === 1 ? 'incidente' : 'incidentes'}. La lista está ordenada por severidad: ` +
      'el primero es el que hay que explicar antes.'
    );
  });

  /** Facts of the window and the incidents that still need manual validation. */
  readonly windowLine = computed(() => {
    const data = this.payload();
    if (data === null) {
      return '';
    }
    const window = data.coverage.time_window;
    return (
      `La ventana cubre ${formatDuration(window.duration_minutes)}, entre ` +
      `${formatTimestamp(window.start)} y ${formatTimestamp(window.end)}.`
    );
  });

  readonly validationIncidents = computed(() =>
    (this.payload()?.incidents ?? [])
      .filter((incident) => incident.requires_validation)
      .map((incident) => incident.id),
  );

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
