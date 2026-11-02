import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { IngestPage } from './ingest-page';
import { eventsPageFixture, uploadResponseFixture } from '../../core/testing/api-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Sube un export .xlsx y vuelve a intentarlo.';

const SESSION_EMPTY_MESSAGE =
  'Todavía no has cargado ningún archivo. Sube un export .xlsx para empezar.';

const EMPTY_PANEL_COPY = 'Todavía no hay ningún archivo';

describe('IngestPage', () => {
  let fixture: ComponentFixture<IngestPage>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [IngestPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(IngestPage);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function selectFile(file: File): void {
    const input = element().querySelector('input[type="file"]') as HTMLInputElement;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }

  function sessionRequest() {
    return http.expectOne((request) => request.url === '/api/session');
  }

  function eventsRequest() {
    return http.expectOne((request) => request.url === '/api/events');
  }

  function flushEmptySession(): void {
    sessionRequest().flush(
      { detail: SESSION_EMPTY_MESSAGE },
      { status: 409, statusText: 'Conflict' },
    );
    eventsRequest().flush(
      { detail: NO_SESSION_MESSAGE },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();
  }

  function sessionSummary() {
    return uploadResponseFixture();
  }

  it('shows the honest empty state when the server holds no session', () => {
    flushEmptySession();

    const content = element().textContent ?? '';
    expect(content).toContain(EMPTY_PANEL_COPY);
    expect(content).toContain(NO_SESSION_MESSAGE);
    expect(element().querySelector('app-quality-summary')).toBeNull();
    expect(element().querySelectorAll('tbody tr').length).toBe(0);
  });

  it('hydrates the panel, the summary card and the table from a loaded session', () => {
    sessionRequest().flush(sessionSummary());
    eventsRequest().flush(eventsPageFixture());
    fixture.detectChanges();

    expect(element().querySelector('app-quality-summary')).not.toBeNull();
    const content = element().textContent ?? '';
    expect(content).toContain('SOC_L2_Logs.xlsx');
    expect(content).toContain('715 filas');
    expect(content).toContain('auth_failure');
    expect(element().querySelectorAll('tbody tr').length).toBe(2);
  });

  it('never shows the empty copy while the session check is still in flight', () => {
    const before = element().textContent ?? '';
    expect(before).not.toContain(EMPTY_PANEL_COPY);
    expect(before).not.toContain('Qué vas a ver cuando cargues el archivo');
    expect(element().querySelector('app-quality-summary')).toBeNull();
    expect(element().querySelector('[role="status"]')?.textContent).toContain(
      'Revisando si ya hay un archivo cargado',
    );

    sessionRequest().flush(sessionSummary());
    eventsRequest().flush(eventsPageFixture());
    fixture.detectChanges();

    expect(element().textContent).not.toContain(EMPTY_PANEL_COPY);
    expect(element().querySelectorAll('tbody tr').length).toBe(2);
  });

  it('shows the summary and the events table after a successful upload', () => {
    flushEmptySession();

    selectFile(new File(['content'], 'SOC_L2_Logs.xlsx'));
    http.expectOne('/api/upload').flush(uploadResponseFixture());
    fixture.detectChanges();

    const events = eventsRequest();
    expect(events.request.params.get('page')).toBe('1');
    events.flush(eventsPageFixture());
    fixture.detectChanges();

    expect(element().querySelector('app-quality-summary')).not.toBeNull();
    const content = element().textContent ?? '';
    expect(content).toContain('SOC_L2_Logs.xlsx');
    expect(content).toContain('auth_failure');
    expect(content).not.toContain(EMPTY_PANEL_COPY);
  });
});
