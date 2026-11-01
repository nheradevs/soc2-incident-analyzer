import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { throwError } from 'rxjs';

import { ReportPage } from './report-page';
import { ReportApiService } from '../../core/services/report-api.service';
import {
  REPORT_TITLES,
  reportPayloadFixture,
  reportPayloadWithBodies,
} from '../../core/testing/report-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

describe('ReportPage', () => {
  let fixture: ComponentFixture<ReportPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReportPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(ReportPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function flushReport(
    payload = reportPayloadFixture(),
  ): void {
    http.expectOne('/api/report').flush(payload);
    fixture.detectChanges();
  }

  function openTechnicalVersion(): void {
    const toggles = element().querySelectorAll('.report-tabs button');
    (toggles[1] as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  it('shows a loading state while the report is being composed', () => {
    expect(element().textContent).toContain('Generando el informe');
    expect(element().querySelector('.report-loading')?.getAttribute('role')).toBe('status');
    expect(element().querySelectorAll('.report-section').length).toBe(0);

    flushReport();
  });

  it('shows the 409 message verbatim with the way back to Cargar when nothing was uploaded', () => {
    http
      .expectOne('/api/report')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    const failure = element().querySelector('.report-failure') as HTMLElement;
    expect(failure.getAttribute('role')).toBe('alert');
    expect(failure.textContent).toContain(NO_SESSION_MESSAGE);
    expect(element().querySelectorAll('.report-section').length).toBe(0);
    expect(element().querySelector('.report-narrative')).toBeNull();

    const targets = Array.from(failure.querySelectorAll('a')).map((link) =>
      link.getAttribute('href'),
    );
    expect(targets).toContain('/cargar');
    expect(targets).toContain('/analisis');
  });

  it('renders the nine executive sections with the titles of the payload', () => {
    flushReport();

    const sections = element().querySelectorAll('.report-section');
    expect(sections.length).toBe(9);
    const titles = Array.from(sections).map((section) =>
      (section.querySelector('.report-section-title')?.textContent ?? '').trim(),
    );
    expect(titles).toEqual(REPORT_TITLES);
  });

  it('switches to the technical version with its own nine sections', () => {
    flushReport();
    openTechnicalVersion();

    const sections = element().querySelectorAll('.report-section');
    expect(sections.length).toBe(9);
    const titles = Array.from(sections).map((section) =>
      (section.querySelector('.report-section-title')?.textContent ?? '').trim(),
    );
    expect(titles).toEqual(REPORT_TITLES);
    const text = element().textContent ?? '';
    expect(text).toContain('INC-20261023-0820');
    expect(text).toContain('EVT-00126');
  });

  it('renders a body given as a string as one paragraph', () => {
    flushReport(reportPayloadWithBodies('Párrafo único del resumen ejecutivo.', 'Texto técnico.'));

    const first = element().querySelector('.report-section') as HTMLElement;
    const paragraphs = first.querySelectorAll('p.report-paragraph');
    expect(paragraphs.length).toBe(1);
    expect(paragraphs[0].textContent?.trim()).toBe('Párrafo único del resumen ejecutivo.');
    expect(first.querySelector('ul.report-list')).toBeNull();
  });

  it('renders a body given as an array as paragraphs and list items without truncating', () => {
    const body = [
      'Primer párrafo del resumen.',
      '• Primer elemento de la lista.',
      '• Segundo elemento de la lista.',
      'Último párrafo del resumen.',
    ];
    flushReport(reportPayloadWithBodies(body, body));

    const first = element().querySelector('.report-section') as HTMLElement;
    const paragraphs = Array.from(first.querySelectorAll('p.report-paragraph')).map((node) =>
      (node.textContent ?? '').trim(),
    );
    expect(paragraphs).toEqual(['Primer párrafo del resumen.', 'Último párrafo del resumen.']);

    const items = Array.from(first.querySelectorAll('ul.report-list li')).map((node) =>
      (node.textContent ?? '').trim(),
    );
    expect(items).toEqual(['Primer elemento de la lista.', 'Segundo elemento de la lista.']);
  });

  it('states the narrative state in one neutral line that never calls the report incomplete', () => {
    flushReport();

    const narrative = element().querySelector('.report-narrative') as HTMLElement;
    expect(narrative.textContent?.trim()).toBe(
      'Redacción asistida: no configurada en esta instalación.',
    );
    const text = element().textContent ?? '';
    expect(text).not.toContain('sin narrativa IA');
    expect(text).not.toContain('incompleto');
  });

  it('requests the PDF as a blob and saves it under the suggested filename', () => {
    flushReport();
    const api = TestBed.inject(ReportApiService);
    const save = spyOn(api, 'saveReport').and.stub();

    (element().querySelector('.report-download-button') as HTMLButtonElement).click();
    fixture.detectChanges();

    expect(element().querySelector('.report-download-busy')).not.toBeNull();

    const request = http.expectOne('/api/report/pdf');
    expect(request.request.responseType).toBe('blob');

    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    request.flush(blob, {
      headers: { 'Content-Disposition': 'attachment; filename="informe-soc2-20261023.pdf"' },
    });
    fixture.detectChanges();

    expect(save).toHaveBeenCalledWith({ blob, filename: 'informe-soc2-20261023.pdf' });
    expect(element().querySelector('.report-download-busy')).toBeNull();
    expect(element().querySelector('.report-download-failure')).toBeNull();
  });

  it('surfaces the download failure verbatim and keeps the report on screen', () => {
    flushReport();

    // The failure rendering is driven by the service error, which decodes the
    // blob body of the PDF request; the decoding itself is covered in
    // ReportApiService's spec.
    const detail =
      'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';
    const api = TestBed.inject(ReportApiService);
    spyOn(api, 'downloadReportPdf').and.returnValue(
      throwError(() => ({ status: 409, message: detail })),
    );

    (element().querySelector('.report-download-button') as HTMLButtonElement).click();
    fixture.detectChanges();

    const failure = element().querySelector('.report-download-failure') as HTMLElement;
    expect(failure.getAttribute('role')).toBe('alert');
    expect(failure.textContent).toContain(detail);
    expect(element().querySelectorAll('.report-section').length).toBe(9);
    expect(
      (element().querySelector('.report-download-button') as HTMLButtonElement).disabled,
    ).toBeFalse();
  });

  it('keeps one version on screen and moves the download action with the switch', () => {
    flushReport();

    expect(element().querySelectorAll('app-report-version').length).toBe(1);
    expect(element().querySelector('.report-download-button')?.textContent).toContain(
      'versión ejecutiva',
    );

    openTechnicalVersion();

    expect(element().querySelectorAll('app-report-version').length).toBe(1);
    expect(element().querySelector('.report-download-button')?.textContent).toContain(
      'versión técnica',
    );
    expect(element().querySelector('.report-download-button')?.textContent).not.toContain(
      'ejecutiva',
    );
  });
});
