import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { IngestPage } from './ingest-page';
import { eventsPageFixture, uploadResponseFixture } from '../../core/testing/api-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

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

  it('states honestly that nothing has been loaded yet, without fake data', () => {
    http
      .expectOne((request) => request.url === '/api/events')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    const content = element().textContent ?? '';
    expect(content).toContain('Todavía no hay ningún archivo');
    expect(content).toContain(NO_SESSION_MESSAGE);
    expect(element().querySelector('app-quality-summary')).toBeNull();
    expect(element().querySelectorAll('tbody tr').length).toBe(0);
  });

  it('shows the summary and the events table after a successful upload', () => {
    http
      .expectOne((request) => request.url === '/api/events')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    selectFile(new File(['content'], 'SOC_L2_Logs.xlsx'));
    http.expectOne('/api/upload').flush(uploadResponseFixture());
    fixture.detectChanges();

    const events = http.expectOne((request) => request.url === '/api/events');
    expect(events.request.params.get('page')).toBe('1');
    events.flush(eventsPageFixture());
    fixture.detectChanges();

    expect(element().querySelector('app-quality-summary')).not.toBeNull();
    const content = element().textContent ?? '';
    expect(content).toContain('SOC_L2_Logs.xlsx');
    expect(content).toContain('auth_failure');
    expect(content).not.toContain('Todavía no hay ningún archivo');
  });
});
