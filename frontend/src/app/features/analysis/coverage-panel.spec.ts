import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CoveragePanel } from './coverage-panel';
import { dashboardPayloadFixture } from '../../core/testing/analysis-fixtures';

describe('CoveragePanel', () => {
  let fixture: ComponentFixture<CoveragePanel>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [CoveragePanel] }).compileComponents();
    fixture = TestBed.createComponent(CoveragePanel);
  });

  function render(): HTMLElement {
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('names the categories the export did not cover instead of hiding them', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    expect(element.querySelectorAll('.category-row').length).toBe(6);
    const uncovered = element.querySelectorAll('.category-uncovered');
    expect(uncovered.length).toBe(4);
    const text = Array.from(uncovered)
      .map((node) => (node.textContent ?? '').trim())
      .join(' | ');
    expect(text).toContain('sin hallazgos en este export');
    expect(element.textContent).toContain('2 de 6 categorías con hallazgos');
    expect(element.textContent).toContain('movimiento lateral');
  });

  it('shows the counts of the covered categories from the payload', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const covered = element.querySelector('.category-row[data-covered="true"]') as HTMLElement;
    expect(covered.textContent).toContain('fuerza bruta');
    expect(covered.textContent).toContain('2 hallazgos');
    expect(covered.textContent).toContain('1 incidentes');
    expect(covered.querySelector('.category-uncovered')).toBeNull();
  });

  it('lists the excluded accounts with the reason the backend gives', () => {
    fixture.componentRef.setInput('payload', dashboardPayloadFixture());
    const element = render();

    const excluded = element.querySelectorAll('.excluded-account');
    expect(excluded.length).toBe(2);
    const text = element.textContent ?? '';
    expect(text).toContain('principal anónimo');
    expect(text).toContain('cuenta de servicio o de máquina');
    expect(text).toContain('21 eventos');
    expect(text).toContain('no se cuentan como personas');
  });
});
