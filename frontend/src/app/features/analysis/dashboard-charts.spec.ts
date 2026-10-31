import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DashboardCharts } from './dashboard-charts';
import { dashboardPayloadFixture } from '../../core/testing/analysis-fixtures';

describe('DashboardCharts', () => {
  let fixture: ComponentFixture<DashboardCharts>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [DashboardCharts] }).compileComponents();
    fixture = TestBed.createComponent(DashboardCharts);
  });

  function render(): HTMLElement {
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('draws one chart per series the payload measured', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    expect(element.querySelectorAll('app-chart-canvas').length).toBe(6);
    const content = element.textContent ?? '';
    expect(content).toContain('Eventos por hora');
    expect(content).toContain('Distribución por criticidad');
    expect(content).toContain('Top hosts');
    expect(content).toContain('Cuentas humanas más activas');
    expect(content).toContain('Tipos de ataque detectados');
    expect(content).toContain('Volumen saliente por destino externo');
    expect(content).not.toContain('Top IPs');
  });

  it('renders the values of every ranking exactly as the payload returned them', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const content = element.textContent ?? '';
    expect(content).toContain('DC01');
    expect(content).toContain('121');
    expect(content).toContain('admin');
    expect(content).toContain('Fuerza bruta dirigida');
    expect(content).toContain('07:00');
    expect(content).toContain('180');
  });

  it('shows the byte volume of the destinations the export measured', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const known = element.querySelector('.outbound-bytes') as HTMLElement;
    expect(known.textContent?.trim()).toBe('253,3 MB');
  });

  it('labels a destination with an unknown byte count distinctly and draws no zero megabyte bar', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const unknown = element.querySelector('.outbound-item--unknown') as HTMLElement;
    expect(unknown).not.toBeNull();
    expect(unknown.textContent).toContain('203.0.113.88');
    expect(unknown.textContent).toContain('bytes no registrados en el export');
    expect(unknown.querySelector('.outbound-bytes')).toBeNull();

    const datasets = fixture.componentInstance.outbound().data.datasets;
    expect(datasets[0].data).toEqual([253305558 / 1_000_000, null]);
  });

  it('shows nothing fabricated when the export has no external destination', () => {
    const payload = dashboardPayloadFixture();
    payload.charts.outbound_by_destination = { items: [], total_events: 0, total_bytes: 0 };
    fixture.componentRef.setInput('payload', payload);
    const element = render();

    expect(element.textContent).toContain('No hay destinos externos en este export');
    expect(element.querySelector('.outbound-item')).toBeNull();
  });
});
