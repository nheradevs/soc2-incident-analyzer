import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { By } from '@angular/platform-browser';
import { MatSort } from '@angular/material/sort';

import { EventsTable } from './events-table';
import { eventsPageFixture } from '../../core/testing/api-fixtures';

const NO_SESSION_MESSAGE =
  'Todavía no se ha cargado ningún archivo. Suba un export .xlsx y vuelva a intentarlo.';

describe('EventsTable', () => {
  let fixture: ComponentFixture<EventsTable>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EventsTable],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(EventsTable);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function element(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function bodyRows(): NodeListOf<HTMLElement> {
    return element().querySelectorAll('tbody tr');
  }

  function flushPage(): void {
    http.expectOne((request) => request.url === '/api/events').flush(eventsPageFixture());
    fixture.detectChanges();
  }

  it('asks for the first page and shows the backend 409 message honestly when nothing is loaded', () => {
    http
      .expectOne((request) => request.url === '/api/events')
      .flush({ detail: NO_SESSION_MESSAGE }, { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();

    expect(element().textContent).toContain(NO_SESSION_MESSAGE);
    expect(bodyRows().length).toBe(0);
    expect(element().querySelector('table')).toBeNull();
  });

  it('renders the original and derived columns returned by the API', () => {
    flushPage();

    const headers = Array.from(element().querySelectorAll('th')).map((header) =>
      header.textContent?.trim(),
    );
    expect(headers).toEqual([
      'Log_ID',
      'Marca de tiempo',
      'Equipo',
      'Evento',
      'Familia de evento',
      'Clase de IP',
      'Bytes de salida',
    ]);
    expect(bodyRows().length).toBe(2);
    expect(bodyRows()[0].textContent).toContain('L-001');
    expect(bodyRows()[0].textContent).toContain('auth_failure');
  });

  it('loads the next page when the paginator changes page', () => {
    flushPage();

    const paginator = fixture.debugElement.query(By.css('mat-paginator'));
    expect(paginator).not.toBeNull();
    paginator.componentInstance.page.emit({ pageIndex: 1, pageSize: 50, length: 715 });

    const request = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(request.request.params.get('page')).toBe('2');
    request.flush(eventsPageFixture({ page: 2, items: [] }));
    fixture.detectChanges();
  });

  it('maps a header sort to the sort and order parameters', () => {
    flushPage();

    const sort = fixture.debugElement.query(By.directive(MatSort)).injector.get(MatSort);
    sort.sort({ id: 'Hostname', start: 'asc', disableClear: false });

    const request = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(request.request.params.get('sort')).toBe('Hostname');
    expect(request.request.params.get('order')).toBe('asc');
    expect(request.request.params.get('page')).toBe('1');
    request.flush(eventsPageFixture());
    fixture.detectChanges();

    sort.sort({ id: 'Hostname', start: 'asc', disableClear: false });
    const descending = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(descending.request.params.get('sort')).toBe('Hostname');
    expect(descending.request.params.get('order')).toBe('desc');
    descending.flush(eventsPageFixture());
    fixture.detectChanges();

    sort.sort({ id: 'Hostname', start: 'asc', disableClear: false });
    const cleared = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(cleared.request.params.has('sort')).toBeFalse();
    expect(cleared.request.params.get('page')).toBe('1');
    cleared.flush(eventsPageFixture());
    fixture.detectChanges();
  });

  it('debounces search and restarts from the first page', fakeAsync(() => {
    flushPage();

    const input = element().querySelector('input[aria-label="Buscar en todos los eventos"]');
    expect(input).not.toBeNull();
    (input as HTMLInputElement).value = 'DC-01';
    input?.dispatchEvent(new Event('input'));

    tick(299);
    http.expectNone((candidate) => candidate.url === '/api/events');

    tick(1);
    const request = http.expectOne((candidate) => candidate.url === '/api/events');
    expect(request.request.params.get('search')).toBe('DC-01');
    expect(request.request.params.get('page')).toBe('1');
    request.flush(eventsPageFixture({ items: [] }));
    fixture.detectChanges();

    expect(element().textContent).toContain('No hay eventos que coincidan');
  }));
});
