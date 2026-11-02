import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { IngestApiService } from './ingest-api.service';
import { ApiFailure, EventsPage, UploadResponse } from '../models/ingest.models';
import { eventsPageFixture, uploadResponseFixture } from '../testing/api-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

describe('IngestApiService', () => {
  let service: IngestApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(IngestApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function xlsxFile(): File {
    return new File(['content'], 'SOC_L2_Logs.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
  }

  it('uploads the selected file as multipart form data on the relative API path', () => {
    const file = xlsxFile();
    let received: UploadResponse | undefined;
    service.upload(file).subscribe((response) => (received = response));

    const request = http.expectOne('/api/upload');
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBeTrue();
    const body = request.request.body as FormData;
    expect(body.get('file')).toBe(file);

    const response = uploadResponseFixture();
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('surfaces the backend detail message verbatim on upload rejection', () => {
    const detail = 'Formato no admitido: solo se aceptan archivos .xlsx.';
    let failure: ApiFailure | undefined;
    service.upload(new File(['x'], 'log.csv')).subscribe({ error: (error) => (failure = error) });

    http.expectOne('/api/upload').flush({ detail }, { status: 400, statusText: 'Bad Request' });

    expect(failure?.status).toBe(400);
    expect(failure?.message).toBe(detail);
  });

  it('requests one page of events with page, size, search, sort and order', () => {
    let received: EventsPage | undefined;
    service
      .getEvents({ page: 2, pageSize: 100, search: 'DC-01', sort: 'Timestamp', order: 'desc' })
      .subscribe((page) => (received = page));

    const request = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('page')).toBe('2');
    expect(request.request.params.get('page_size')).toBe('100');
    expect(request.request.params.get('search')).toBe('DC-01');
    expect(request.request.params.get('sort')).toBe('Timestamp');
    expect(request.request.params.get('order')).toBe('desc');

    const page = eventsPageFixture();
    request.flush(page);
    expect(received).toEqual(page);
  });

  it('omits search and sort parameters when no filter or ordering is active', () => {
    service.getEvents({ page: 1, pageSize: 50 }).subscribe();

    const request = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(request.request.params.has('search')).toBeFalse();
    expect(request.request.params.has('sort')).toBeFalse();
    expect(request.request.params.get('order')).toBe('asc');
    request.flush(eventsPageFixture());
  });

  it('surfaces the 409 message verbatim when no file has been uploaded yet', () => {
    let failure: ApiFailure | undefined;
    service.getEvents({ page: 1, pageSize: 50 }).subscribe({ error: (error) => (failure = error) });

    http
      .expectOne((candidate) => candidate.url === '/api/events')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });

    expect(failure?.status).toBe(409);
    expect(failure?.message).toBe(NO_SESSION_MESSAGE);
  });

  it('reads the summary of the session the server already holds', () => {
    let received: UploadResponse | undefined;
    service.getSession().subscribe((summary) => (received = summary));

    const request = http.expectOne('/api/session');
    expect(request.request.method).toBe('GET');

    const summary = uploadResponseFixture();
    request.flush(summary);
    expect(received).toEqual(summary);
  });

  it('surfaces the 409 message verbatim when the server holds no session', () => {
    const detail = 'Todavía no has cargado ningún archivo. Sube un export .xlsx para empezar.';
    let failure: ApiFailure | undefined;
    service.getSession().subscribe({ error: (error) => (failure = error) });

    http.expectOne('/api/session').flush({ detail }, { status: 409, statusText: 'Conflict' });

    expect(failure?.status).toBe(409);
    expect(failure?.message).toBe(detail);
  });
});
