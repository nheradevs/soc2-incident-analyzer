import { ComponentFixture, TestBed } from '@angular/core/testing';

import { IncidentList } from './incident-list';
import { dashboardPayloadFixture } from '../../core/testing/analysis-fixtures';
import { IncidentSummary } from '../../core/models/analysis.models';

describe('IncidentList', () => {
  let fixture: ComponentFixture<IncidentList>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [IncidentList] }).compileComponents();
    fixture = TestBed.createComponent(IncidentList);
  });

  function render(incidents: IncidentSummary[]): HTMLElement {
    fixture.componentRef.setInput('incidents', incidents);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('keeps the severity order the payload returned instead of re-sorting it', () => {
    const incidents = dashboardPayloadFixture().incidents;
    const element = render(incidents);

    const ids = Array.from(element.querySelectorAll('.incident')).map((node) =>
      node.getAttribute('data-incident-id'),
    );
    expect(ids).toEqual(incidents.map((incident) => incident.id));
    expect(element.textContent).toContain('crítico');
    expect(element.textContent).toContain('alto');
  });

  it('marks the incidents that still require manual validation', () => {
    const element = render(dashboardPayloadFixture().incidents);

    const badges = element.querySelectorAll('.incident-validation');
    expect(badges.length).toBe(1);
    expect(badges[0].textContent).toContain('Requiere validación');
  });

  it('emits the identifier of the incident the analyst opens', () => {
    const incidents = dashboardPayloadFixture().incidents;
    const element = render(incidents);

    let selected: string | undefined;
    fixture.componentInstance.selected.subscribe((id) => (selected = id));

    (element.querySelector('.incident-open') as HTMLButtonElement).click();

    expect(selected).toBe(incidents[0].id);
  });

  it('states honestly that no incident was detected', () => {
    const element = render([]);

    expect(element.textContent).toContain('No se detectaron incidentes en este export');
    expect(element.querySelectorAll('.incident').length).toBe(0);
  });
});
