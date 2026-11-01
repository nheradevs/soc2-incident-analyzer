import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import {
  ApiFailure,
  EventsPage,
  EventsQuery,
  UploadResponse,
} from '../models/ingest.models';

/** Relative base path: the dev server proxies `/api` to the backend. */
const API_BASE = '/api';

const NETWORK_MESSAGE =
  'No se pudo contactar con el servidor. Verifica que el backend esté en ejecución.';

/** Read the Spanish `detail` string FastAPI sends on rejection. */
function readDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return null;
  }
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string' && detail.trim() !== '') {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) =>
        typeof entry === 'object' && entry !== null && 'msg' in entry
          ? String((entry as { msg: unknown }).msg)
          : null,
      )
      .filter((message): message is string => message !== null);
    if (messages.length > 0) {
      return messages.join(' ');
    }
  }
  return null;
}

/** Convert any thrown value into the `ApiFailure` the UI renders. */
export function toApiFailure(error: unknown): ApiFailure {
  if (error instanceof HttpErrorResponse) {
    const detail = readDetail(error.error);
    if (detail !== null) {
      return { status: error.status, message: detail };
    }
    if (error.status === 0) {
      return { status: 0, message: NETWORK_MESSAGE };
    }
    return { status: error.status, message: error.message };
  }
  return { status: 0, message: NETWORK_MESSAGE };
}

function failWithDetail(error: unknown): Observable<never> {
  return throwError(() => toApiFailure(error));
}

@Injectable({ providedIn: 'root' })
export class IngestApiService {
  private readonly http = inject(HttpClient);

  /** Upload one `.xlsx` export; the backend validates format and size. */
  upload(file: File): Observable<UploadResponse> {
    const body = new FormData();
    body.append('file', file);
    return this.http
      .post<UploadResponse>(`${API_BASE}/upload`, body)
      .pipe(catchError(failWithDetail));
  }

  /** Fetch one page of normalized events with optional search and ordering. */
  getEvents(query: EventsQuery): Observable<EventsPage> {
    let params = new HttpParams()
      .set('page', query.page)
      .set('page_size', query.pageSize)
      .set('order', query.order ?? 'asc');

    const search = query.search?.trim();
    if (search) {
      params = params.set('search', search);
    }
    if (query.sort) {
      params = params.set('sort', query.sort);
    }

    return this.http
      .get<EventsPage>(`${API_BASE}/events`, { params })
      .pipe(catchError(failWithDetail));
  }
}
