import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AnalysisApiService } from './analysis-api.service';
import { ApiFailure } from '../models/ingest.models';
import { DashboardPayload, IncidentDetail } from '../models/analysis.models';
import { dashboardPayloadFixture, incidentDetailFixture } from '../testing/analysis-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

describe('AnalysisApiService', () => {
  let service: AnalysisApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalysisApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('requests the analysis on the relative API path and returns the payload', () => {
    let received: DashboardPayload | undefined;
    service.analyze().subscribe((payload) => (received = payload));

    const request = http.expectOne('/api/analyze');
    expect(request.request.method).toBe('POST');

    const payload = dashboardPayloadFixture();
    request.flush(payload);
    expect(received).toEqual(payload);
  });

  it('surfaces the 409 detail verbatim when no export has been uploaded', () => {
    let failure: ApiFailure | undefined;
    service.analyze().subscribe({ error: (error) => (failure = error) });

    http
      .expectOne('/api/analyze')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });

    expect(failure?.status).toBe(409);
    expect(failure?.message).toBe(NO_SESSION_MESSAGE);
  });

  it('requests one incident drill-down with its identifier in the path', () => {
    let received: IncidentDetail | undefined;
    service.incident('INC-20261023-0820').subscribe((detail) => (received = detail));

    const request = http.expectOne('/api/incidents/INC-20261023-0820');
    expect(request.request.method).toBe('GET');

    const detail = incidentDetailFixture();
    request.flush(detail);
    expect(received).toEqual(detail);
  });

  it('encodes the incident identifier instead of pasting it raw into the path', () => {
    service.incident('INC 0820/../secreto').subscribe();

    const request = http.expectOne('/api/incidents/INC%200820%2F..%2Fsecreto');
    expect(request.request.url).toBe('/api/incidents/INC%200820%2F..%2Fsecreto');
    request.flush(incidentDetailFixture());
  });

  it('surfaces the 404 detail verbatim for an unknown incident', () => {
    const detail = 'No existe un incidente con el identificador «INC-9999-0000».';
    let failure: ApiFailure | undefined;
    service.incident('INC-9999-0000').subscribe({ error: (error) => (failure = error) });

    http
      .expectOne('/api/incidents/INC-9999-0000')
      .flush({ detail }, { status: 404, statusText: 'Not Found' });

    expect(failure?.status).toBe(404);
    expect(failure?.message).toBe(detail);
  });
});
