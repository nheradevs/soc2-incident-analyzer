import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { IncidentDetail } from './incident-detail';
import { incidentDetailFixture } from '../../core/testing/analysis-fixtures';

describe('IncidentDetail', () => {
  let fixture: ComponentFixture<IncidentDetail>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [IncidentDetail],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(IncidentDetail);
    http = TestBed.inject(HttpTestingController);
    fixture.componentRef.setInput('incidentId', 'INC-20261023-0820');
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function flushDetail(overrides = {}): void {
    http.expectOne('/api/incidents/INC-20261023-0820').flush(incidentDetailFixture(overrides));
    fixture.detectChanges();
  }

  it('requests the drill-down of the selected incident and shows its classification', () => {
    flushDetail();

    const content = element().textContent ?? '';
    expect(content).toContain('Fuerza bruta RDP con origen externo');
    expect(content).toContain('crítico');
    expect(content).toContain('alta');
    expect(content).toContain('INC-20261023-0820');
    const level = element().querySelector('.detail-level') as HTMLElement;
    expect(level.getAttribute('data-level')).toBe('critical');
  });

  it('shows every finding with the justification the risk matrix wrote', () => {
    flushDetail();

    const findings = element().querySelectorAll('.finding');
    expect(findings.length).toBe(2);
    expect(element().textContent).toContain('Fuerza bruta dirigida contra «admin»');
    expect(element().textContent).toContain(
      'Inicio de sesión posterior al ataque',
    );
    expect(element().querySelectorAll('.finding-justification').length).toBe(2);
    expect(element().textContent).toContain('el origen es una IP externa');
    expect(element().textContent).toContain('la IP externa del ataque previo');
  });

  it('deduplicates evidence rows shared by two findings and states the distinct count', () => {
    flushDetail();

    const count = element().querySelector('.evidence-count') as HTMLElement;
    expect(count.textContent).toContain('3 filas de evidencia distintas');
    expect(count.textContent).toContain('4 citas');

    const rows = element().querySelectorAll('.evidence-table tbody tr');
    expect(rows.length).toBe(3);
    const logIds = Array.from(element().querySelectorAll('.evidence-log-id')).map(
      (cell) => (cell.textContent ?? '').trim(),
    );
    expect(logIds).toEqual(['EVT-00126', 'EVT-00130', 'EVT-00127']);
  });

  it('warns when a cited evidence row does not exist in the export', () => {
    flushDetail({ evidence_missing: ['EVT-99999'] });

    const warning = element().querySelector('.evidence-missing') as HTMLElement;
    expect(warning).not.toBeNull();
    expect(warning.getAttribute('role')).toBe('alert');
    expect(warning.textContent).toContain('EVT-99999');
    expect(warning.textContent).toContain('no existen en el export');
  });

  it('shows the backend message verbatim when the drill-down cannot be loaded', () => {
    const detail = 'No existe un incidente con el identificador «INC-20261023-0820».';
    http
      .expectOne('/api/incidents/INC-20261023-0820')
      .flush({ detail }, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();

    const failure = element().querySelector('.detail-failure') as HTMLElement;
    expect(failure.getAttribute('role')).toBe('alert');
    expect(failure.textContent).toContain(detail);
  });
});
