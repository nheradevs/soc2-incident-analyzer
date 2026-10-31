import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, from, map, mergeMap, throwError } from 'rxjs';

import { ApiFailure } from '../models/ingest.models';
import { ReportDownload, ReportPayload } from '../models/report.models';
import { toApiFailure } from './ingest-api.service';

/** Relative base path: the dev server proxies `/api` to the backend. */
const API_BASE = '/api';

const PDF_PATH = `${API_BASE}/report/pdf`;

/** Used only when the response carries no usable `Content-Disposition`. */
const FALLBACK_FILENAME = 'informe-soc2.pdf';

/**
 * Filename the backend suggests in `Content-Disposition`, e.g.
 * `attachment; filename="informe-soc2-20261023.pdf"`.
 */
export function suggestedFilename(header: string | null): string {
  if (header === null) {
    return FALLBACK_FILENAME;
  }
  const match = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  const candidate = match?.[1]?.trim() ?? '';
  if (candidate === '') {
    return FALLBACK_FILENAME;
  }
  try {
    return decodeURIComponent(candidate);
  } catch {
    return candidate;
  }
}

/**
 * Read the Spanish `detail` of a failed blob request.
 *
 * With `responseType: 'blob'` Angular hands the error body over as a `Blob`
 * rather than a parsed object, so the JSON has to be read before it can reach
 * the shared `toApiFailure` mapping. Without this the UI would lose the
 * backend message and show a generic HTTP failure instead.
 */
async function readBlobFailure(blob: Blob, error: HttpErrorResponse): Promise<ApiFailure> {
  try {
    const parsed: unknown = JSON.parse(await blob.text());
    return toApiFailure(
      new HttpErrorResponse({
        status: error.status,
        statusText: error.statusText,
        url: error.url ?? undefined,
        error: parsed,
      }),
    );
  } catch {
    return { status: error.status, message: error.message };
  }
}

function failWithDetail(error: unknown): Observable<never> {
  if (error instanceof HttpErrorResponse && error.error instanceof Blob) {
    return from(readBlobFailure(error.error, error)).pipe(
      mergeMap((failure) => throwError(() => failure)),
    );
  }
  return throwError(() => toApiFailure(error));
}

/** RF5/RF6 endpoints: the composed report and its server-side PDF. */
@Injectable({ providedIn: 'root' })
export class ReportApiService {
  private readonly http = inject(HttpClient);

  /**
   * Both versions of the report of the export already in the session.
   *
   * Answers 409 with a Spanish `detail` when nothing has been uploaded, which
   * the report screen renders as its empty state.
   */
  report(): Observable<ReportPayload> {
    return this.http
      .post<ReportPayload>(`${API_BASE}/report`, null)
      .pipe(catchError(failWithDetail));
  }

  /** The report as a PDF, requested as a blob with the filename the server suggests. */
  downloadReportPdf(): Observable<ReportDownload> {
    return this.http
      .get(PDF_PATH, { observe: 'response', responseType: 'blob' })
      .pipe(
        map((response) => ({
          blob: response.body ?? new Blob([], { type: 'application/pdf' }),
          filename: suggestedFilename(response.headers.get('Content-Disposition')),
        })),
        catchError(failWithDetail),
      );
  }

  /**
   * Save an already fetched PDF through an object URL.
   *
   * The URL is revoked once the browser has been handed the download, so the
   * blob is not kept alive; nothing is opened in a new tab.
   */
  saveReport(download: ReportDownload): void {
    const url = URL.createObjectURL(download.blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = download.filename;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    try {
      anchor.click();
    } finally {
      anchor.remove();
      URL.revokeObjectURL(url);
    }
  }
}
