import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { ReportApiService } from './report-api.service';
import { ApiFailure } from '../models/ingest.models';
import { ReportDownload, ReportPayload } from '../models/report.models';
import { reportPayloadFixture } from '../testing/report-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

const SUGGESTED_FILENAME = 'informe-soc2-20261023.pdf';

describe('ReportApiService', () => {
  let service: ReportApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ReportApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the report on the relative API path and returns the payload', () => {
    let received: ReportPayload | undefined;
    service.report().subscribe((payload) => (received = payload));

    const request = http.expectOne('/api/report');
    expect(request.request.method).toBe('POST');

    const payload = reportPayloadFixture();
    request.flush(payload);
    expect(received).toEqual(payload);
  });

  it('surfaces the 409 detail verbatim when no export has been uploaded', () => {
    let failure: ApiFailure | undefined;
    service.report().subscribe({ error: (error) => (failure = error) });

    http
      .expectOne('/api/report')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });

    expect(failure?.status).toBe(409);
    expect(failure?.message).toBe(NO_SESSION_MESSAGE);
  });

  it('requests the PDF as a blob and reads the filename the backend suggests', () => {
    let received: ReportDownload | undefined;
    service.downloadReportPdf().subscribe((download) => (received = download));

    const request = http.expectOne('/api/report/pdf');
    expect(request.request.method).toBe('GET');
    expect(request.request.responseType).toBe('blob');

    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    request.flush(blob, {
      headers: { 'Content-Disposition': `attachment; filename="${SUGGESTED_FILENAME}"` },
    });

    expect(received?.blob).toBe(blob);
    expect(received?.filename).toBe(SUGGESTED_FILENAME);
  });

  it('falls back to a generic filename when the response suggests none', () => {
    let received: ReportDownload | undefined;
    service.downloadReportPdf().subscribe((download) => (received = download));

    http.expectOne('/api/report/pdf').flush(new Blob(['%PDF-1.4'], { type: 'application/pdf' }));

    expect(received?.filename).toBe('informe-soc2.pdf');
  });

  it('surfaces the 409 detail verbatim when the PDF request fails on a blob response', async () => {
    const body = new Blob([JSON.stringify({ detail: NO_SESSION_MESSAGE })], {
      type: 'application/json',
    });

    // The error body of a blob request is decoded asynchronously, so the
    // mapped failure is awaited instead of read right after `flush`.
    const failure = await new Promise<ApiFailure>((resolve, reject) => {
      service.downloadReportPdf().subscribe({
        next: () => reject(new Error('the PDF request was expected to fail')),
        error: resolve,
      });
      http.expectOne('/api/report/pdf').flush(body, { status: 409, statusText: 'Conflict' });
    });

    expect(failure.status).toBe(409);
    expect(failure.message).toBe(NO_SESSION_MESSAGE);
  });

  it('saves the PDF through an object URL that is revoked afterwards', () => {
    const anchors: HTMLAnchorElement[] = [];
    const createElement = document.createElement.bind(document);
    spyOn(document, 'createElement').and.callFake((tag: string) => {
      const element = createElement(tag);
      if (tag === 'a') {
        anchors.push(element as HTMLAnchorElement);
      }
      return element;
    });
    spyOn(HTMLAnchorElement.prototype, 'click').and.stub();
    spyOn(URL, 'createObjectURL').and.returnValue('blob:informe-soc2');
    spyOn(URL, 'revokeObjectURL').and.stub();

    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    service.saveReport({ blob, filename: SUGGESTED_FILENAME });

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    const anchor = anchors[0];
    expect(anchor.download).toBe(SUGGESTED_FILENAME);
    expect(anchor.href).toContain('blob:informe-soc2');
    expect(anchor.isConnected).toBeFalse();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:informe-soc2');
  });

  it('sends the requested version so the server can render only that one', () => {
    service.downloadReportPdf('tecnica').subscribe();

    const request = http.expectOne('/api/report/pdf?version=tecnica');
    expect(request.request.params.get('version')).toBe('tecnica');
    request.flush(new Blob(['%PDF-1.4'], { type: 'application/pdf' }));
  });
});
