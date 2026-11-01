import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AnalysisPage } from './analysis-page';
import { incidentDetailFixture } from '../../core/testing/analysis-fixtures';
import { dashboardPayloadFixture } from '../../core/testing/analysis-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Sube un export .xlsx y vuelve a intentarlo.';

describe('AnalysisPage', () => {
  let fixture: ComponentFixture<AnalysisPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AnalysisPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(AnalysisPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function flushDashboard(): void {
    http.expectOne('/api/analyze').flush(dashboardPayloadFixture());
    fixture.detectChanges();
  }

  it('shows a loading state while the analysis is being computed', () => {
    const content = element().textContent ?? '';

    expect(content).toContain('Analizando el export cargado');
    expect(element().querySelector('.analysis-loading')?.getAttribute('role')).toBe('status');
    expect(element().querySelector('app-dashboard-kpis')).toBeNull();

    http.expectOne('/api/analyze').flush(dashboardPayloadFixture());
    fixture.detectChanges();
  });

  it('shows the backend message verbatim and a way back when nothing was uploaded', () => {
    http
      .expectOne('/api/analyze')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    const failure = element().querySelector('.analysis-failure') as HTMLElement;
    expect(failure.getAttribute('role')).toBe('alert');
    expect(failure.textContent).toContain(NO_SESSION_MESSAGE);
    expect(failure.textContent).toContain('Cargar');
    const backLink = failure.querySelector('a') as HTMLAnchorElement;
    expect(backLink.getAttribute('href')).toBe('/cargar');
    expect(element().querySelector('app-dashboard-kpis')).toBeNull();
  });

  it('keeps the failure card on screen while a retry is in flight', () => {
    http
      .expectOne('/api/analyze')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    const retry = element().querySelector('.analysis-failure-actions button') as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    // The whole dashboard skeleton must not replace the error card on a retry.
    expect(element().querySelector('.analysis-failure')).not.toBeNull();
    expect(element().querySelector('.analysis-loading')).toBeNull();
    const busy = element().querySelector('.analysis-failure-actions button') as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(busy.getAttribute('aria-busy')).toBe('true');
    // Both labels live in the same grid cell, so the box is as wide as the longest one.
    const label = busy.querySelector('.btn__label') as HTMLElement;
    const busyLabel = busy.querySelector('.btn__busy') as HTMLElement;
    expect(label.textContent?.trim()).toBe('Reintentar el análisis');
    expect(busyLabel.textContent?.trim()).toBe('Reintentando…');

    http
      .expectOne('/api/analyze')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    const after = element().querySelector('.analysis-failure-actions button') as HTMLButtonElement;
    expect(after.disabled).toBe(false);
    expect(after.getAttribute('aria-busy')).toBe('false');
  });

  it('renders the KPIs measured by the payload, with no invented section', () => {
    flushDashboard();

    const kpis = element().querySelector('app-dashboard-kpis') as HTMLElement;
    expect(kpis.textContent).toContain('715');
    expect(kpis.textContent).toContain('crítico');
    expect(kpis.textContent).toContain('alto');
    expect(kpis.textContent).toContain('2026-10-23 07:46:07');
    expect(kpis.textContent).toContain('2026-10-23 13:44:06');

    const findings = element().querySelector('.kpi-findings') as HTMLElement;
    expect(findings.textContent?.trim()).toBe('3');
    expect(element().querySelector('app-dashboard-charts')).not.toBeNull();
    expect(element().querySelectorAll('.incident').length).toBe(2);
  });

  it('opens with the redesign page head and the measured window as its lead', () => {
    flushDashboard();

    const head = element().querySelector('.page-head') as HTMLElement;
    expect(head.textContent).toContain('Paso 2 de 3');
    expect(head.textContent).toContain('Análisis del export');
    expect(head.textContent).toContain('5 h 58 min');
    expect(head.textContent).toContain('2 incidentes');
  });

  it('opens the incident drill-down with its distinct evidence count', () => {
    flushDashboard();

    const first = element().querySelector('.incident-open') as HTMLButtonElement;
    first.click();
    fixture.detectChanges();

    const request = http.expectOne('/api/incidents/INC-20261023-0820');
    request.flush(incidentDetailFixture());
    fixture.detectChanges();

    const detail = element().querySelector('app-incident-detail') as HTMLElement;
    expect(detail).not.toBeNull();
    expect(detail.textContent).toContain('Fuerza bruta RDP con origen externo');
    expect(detail.textContent).toContain('3 filas de evidencia distintas');
    expect(detail.textContent).toContain('EVT-00130');
  });
});
