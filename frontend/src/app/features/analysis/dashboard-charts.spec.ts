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

  function press(hour: string): void {
    fixture.componentInstance.selectHour(hour);
    fixture.detectChanges();
  }

  function pressedHour(element: HTMLElement): string | null {
    return element.querySelector('.col[aria-pressed="true"]')?.getAttribute('data-hour') ?? null;
  }

  it('draws one card per series the payload measured', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    expect(element.querySelectorAll('.chart-card').length).toBe(4);
    const content = element.textContent ?? '';
    expect(content).toContain('Eventos por hora');
    expect(content).toContain('Tipos de hallazgo');
    expect(content).toContain('Equipos con más eventos');
    expect(content).toContain('Salida a destinos externos');
    expect(content).not.toContain('Top IPs');
  });

  it('starts with the peak bucket selected instead of the whole window', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    expect(pressedHour(element)).toBe('2026-10-23T09:00:00');
    const detail = element.querySelector('.hour-detail') as HTMLElement;
    expect(detail.textContent).toContain('09:00');
    expect(detail.textContent).toContain('270 eventos');
    expect(detail.textContent).toContain('Pico del día');
    expect(element.querySelectorAll('.col').length).toBe(3);
  });

  it('changes the selected range when another bar is activated', () => {
    const payload = dashboardPayloadFixture();
    payload.charts.events_by_hour.push({
      hour: '2026-10-23T11:00:00',
      label: '11:00',
      events: 10,
    });
    fixture.componentRef.setInput('payload', payload);
    const element = render();

    (element.querySelectorAll('.col')[3] as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(pressedHour(element)).toBe('2026-10-23T11:00:00');
    const detail = element.querySelector('.hour-detail') as HTMLElement;
    expect(detail.textContent).toContain('11:00');
    expect(detail.textContent).toContain('INC-20261023-1137');
    expect(detail.textContent).not.toContain('Pico del día');
  });

  it('keeps the reader selection when the payload refreshes with the same tramo', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();
    press('2026-10-23T07:00:00');

    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    fixture.detectChanges();

    expect(pressedHour(element)).toBe('2026-10-23T07:00:00');
  });

  it('falls back to the peak when the refreshed payload drops the selected tramo', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();
    press('2026-10-23T07:00:00');

    const refreshed = dashboardPayloadFixture();
    refreshed.charts.events_by_hour = refreshed.charts.events_by_hour.slice(1);
    fixture.componentRef.setInput('payload', refreshed);
    fixture.detectChanges();

    expect(pressedHour(element)).toBe('2026-10-23T09:00:00');
  });

  it('colours each detector bar with the documented maximum impact', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const types = element.querySelectorAll('article')[1] as HTMLElement;
    const typeBars = Array.from(types.querySelectorAll('.hbar'));
    const labels = typeBars.map((bar) => bar.querySelector('.hbar__label')?.textContent?.trim());
    expect(labels).toEqual(['D1a · Fuerza bruta dirigida', 'D7 · Exfiltración']);
    expect(typeBars[0].getAttribute('data-level')).toBe('medium');
    expect(typeBars[1].getAttribute('data-level')).toBe('high');
  });

  it('colours hosts with the severity of the incident that touches them', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const hostsCard = element.querySelectorAll('article')[2] as HTMLElement;
    const rows = Array.from(hostsCard.querySelectorAll('.hbar'));
    expect(rows[0].getAttribute('data-level')).toBe('critical');
    expect(rows[1].getAttribute('data-level')).toBe('none');
    expect(rows[1].textContent).toContain('WEB-01');
    expect(rows[1].textContent).toContain('96');
  });

  it('shows the measured byte volume and never draws an unknown one as zero', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const known = element.querySelector('.outbound-bytes') as HTMLElement;
    expect(known.textContent?.trim()).toBe('253.305.558 bytes');

    const unknown = element.querySelector('.outbound-item--unknown') as HTMLElement;
    expect(unknown).not.toBeNull();
    expect(unknown.textContent).toContain('203.0.113.88');
    expect(unknown.textContent).toContain('bytes no registrados en el export');
    expect(unknown.querySelector('.outbound-bytes')).toBeNull();
  });

  it('shows nothing fabricated when the export has no external destination', () => {
    const payload = dashboardPayloadFixture();
    payload.charts.outbound_by_destination = { items: [], total_events: 0, total_bytes: 0 };
    fixture.componentRef.setInput('payload', payload);
    const element = render();

    expect(element.textContent).toContain('No hay destinos externos en este export');
    expect(element.querySelector('.dest__row')).toBeNull();
  });
});
