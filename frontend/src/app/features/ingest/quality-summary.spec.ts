import { ComponentFixture, TestBed } from '@angular/core/testing';

import { QualitySummary } from './quality-summary';
import { uploadResponseFixture } from '../../core/testing/api-fixtures';

describe('QualitySummary', () => {
  let fixture: ComponentFixture<QualitySummary>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [QualitySummary] }).compileComponents();
    fixture = TestBed.createComponent(QualitySummary);
  });

  function text(): string {
    fixture.detectChanges();
    return (fixture.nativeElement as HTMLElement).textContent ?? '';
  }

  it('reports rows, columns and the time range of the loaded export', () => {
    fixture.componentRef.setInput('summary', uploadResponseFixture());
    const content = text();

    expect(content).toContain('SOC_L2_Logs.xlsx');
    expect(content).toContain('715');
    expect(content).toContain('12');
    expect(content).toContain('2026-10-23 07:46:07');
    expect(content).toContain('2026-10-23 13:44:06');
  });

  it('shows the duplicate host spellings as explicit evidence', () => {
    fixture.componentRef.setInput('summary', uploadResponseFixture());
    text();

    const evidence = fixture.nativeElement.querySelector('.quality-duplicate-host') as HTMLElement;
    expect(evidence).not.toBeNull();
    expect(evidence.textContent).toContain('DC-01');
    expect(evidence.textContent).toContain('DC-01 (40)');
    expect(evidence.textContent).toContain('DC01 (3)');
    expect(evidence.textContent).toContain('43');
  });

  it('shows the mixed Event_ID evidence and the columns with null values', () => {
    fixture.componentRef.setInput('summary', uploadResponseFixture());
    text();

    const eventIds = fixture.nativeElement.querySelector('.quality-event-id') as HTMLElement;
    expect(eventIds.textContent).toContain('690');
    expect(eventIds.textContent).toContain('25');
    expect(eventIds.textContent).toContain('IIS-Start (12)');
    expect(eventIds.textContent).toContain('int (690)');

    const nulls = fixture.nativeElement.querySelector('.quality-null-counts') as HTMLElement;
    expect(nulls.textContent).toContain('Destination: 262');
    expect(nulls.textContent).toContain('Process_CommandLine: 540');
  });

  it('states honestly that no timestamp failed to parse when the count is zero', () => {
    fixture.componentRef.setInput('summary', uploadResponseFixture());
    text();

    const failures = fixture.nativeElement.querySelector(
      '.quality-timestamp-failures',
    ) as HTMLElement;
    expect(failures.textContent).toContain('0');
    expect(failures.textContent).toContain('no interpretables');
  });

  it('renders nothing when no export has been loaded', () => {
    fixture.componentRef.setInput('summary', null);
    expect(text().trim()).toBe('');
  });
});
