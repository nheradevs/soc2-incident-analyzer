import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import { DashboardPayload, IncidentDetail } from '../models/analysis.models';
import { ApiFailure } from '../models/ingest.models';
import { toApiFailure } from './ingest-api.service';

/** Relative base path: the dev server proxies `/api` to the backend. */
const API_BASE = '/api';

/** Reuse the shared failure mapping so every endpoint reports `detail` verbatim. */
function failWithDetail(error: unknown): Observable<never> {
  return throwError((): ApiFailure => toApiFailure(error));
}

/** RF4 endpoints: the dashboard payload and the drill-down of one incident. */
@Injectable({ providedIn: 'root' })
export class AnalysisApiService {
  private readonly http = inject(HttpClient);

  /**
   * Analyse the export already uploaded to the session.
   *
   * The endpoint takes no body and answers 409 with a Spanish `detail` when
   * nothing has been uploaded, which the dashboard renders as its empty state.
   */
  analyze(): Observable<DashboardPayload> {
    return this.http
      .post<DashboardPayload>(`${API_BASE}/analyze`, null)
      .pipe(catchError(failWithDetail));
  }

  /** Risk classification, findings and evidence rows of one incident. */
  incident(id: string): Observable<IncidentDetail> {
    return this.http
      .get<IncidentDetail>(`${API_BASE}/incidents/${encodeURIComponent(id)}`)
      .pipe(catchError(failWithDetail));
  }
}
