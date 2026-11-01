import { Component, OnChanges, OnInit, SimpleChanges, inject, input, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatPaginatorIntl, MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSortModule, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { debounceTime, distinctUntilChanged } from 'rxjs';

import {
  ApiFailure,
  EventRow,
  EventsPage,
  SortOrder,
} from '../../core/models/ingest.models';
import { SpanishPaginatorIntl } from '../../core/i18n/spanish-paginator-intl';
import { IngestApiService } from '../../core/services/ingest-api.service';

const DEFAULT_PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 300;
const LOG_ID = 'Log_ID';

/** Spanish header labels of the columns the design names, keyed by API column. */
const COLUMN_LABELS: Record<string, string> = {
  Log_ID: 'Log_ID',
  Timestamp: 'Marca de tiempo',
  Hostname: 'Equipo',
  Event_ID: 'Evento',
  User: 'Cuenta',
  Source_IP: 'Origen',
  Destination: 'Destino',
  Result: 'Resultado',
  Event_Description: 'Descripción',
  event_family: 'Familia de evento',
  ip_class: 'Clase de IP',
  bytes_out: 'Bytes de salida',
};

/** RF1 table view: server-side pagination, search and sorting over `/api/events`. */
@Component({
  selector: 'app-events-table',
  imports: [
    ReactiveFormsModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatSortModule,
    MatTableModule,
  ],
  templateUrl: './events-table.html',
  styleUrl: './events-table.scss',
  providers: [{ provide: MatPaginatorIntl, useClass: SpanishPaginatorIntl }],
})
export class EventsTable implements OnInit, OnChanges {
  private readonly api = inject(IngestApiService);

  /** Bumped by the page after a new upload so the table reloads from page 1. */
  readonly refreshKey = input(0);

  readonly searchControl = new FormControl('', { nonNullable: true });
  readonly rows = signal<EventRow[]>([]);
  readonly columns = signal<string[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(DEFAULT_PAGE_SIZE);
  readonly sortColumn = signal<string | null>(null);
  readonly sortOrder = signal<SortOrder>('asc');
  readonly loading = signal(false);
  readonly failure = signal<ApiFailure | null>(null);

  /** Drops the answer of a superseded request so a stale page cannot win. */
  private requestCounter = 0;

  constructor() {
    this.searchControl.valueChanges
      .pipe(debounceTime(SEARCH_DEBOUNCE_MS), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => this.load(1));
  }

  ngOnInit(): void {
    this.load(1);
  }

  ngOnChanges(changes: SimpleChanges): void {
    const refresh = changes['refreshKey'];
    if (refresh !== undefined && !refresh.firstChange) {
      this.load(1);
    }
  }

  onPage(event: PageEvent): void {
    this.pageSize.set(event.pageSize);
    this.load(event.pageIndex + 1);
  }

  onSort(sort: Sort): void {
    this.sortColumn.set(sort.direction === '' ? null : sort.active);
    this.sortOrder.set(sort.direction === 'desc' ? 'desc' : 'asc');
    this.load(1);
  }

  /** First row of the page, for the count line under the table. */
  firstRow(): number {
    return this.total() === 0 ? 0 : (this.page() - 1) * this.pageSize() + 1;
  }

  lastRow(): number {
    return Math.min(this.page() * this.pageSize(), this.total());
  }

  tableLabel(column: string): string {
    return COLUMN_LABELS[column] ?? column;
  }

  isVoid(row: EventRow, column: string): boolean {
    const value = row[column];
    return value === null || value === undefined || value === '';
  }

  isMono(column: string): boolean {
    return column === 'Source_IP' || column === 'Destination';
  }

  cellText(row: EventRow, column: string): string {
    const value = row[column];
    if (value === null || value === undefined) {
      return 'Sin datos';
    }
    return String(value);
  }

  private load(page: number): void {
    const requestId = ++this.requestCounter;
    this.loading.set(true);
    this.failure.set(null);

    this.api
      .getEvents({
        page,
        pageSize: this.pageSize(),
        search: this.searchControl.value,
        sort: this.sortColumn(),
        order: this.sortOrder(),
      })
      .subscribe({
        next: (response: EventsPage) => {
          if (requestId !== this.requestCounter) {
            return;
          }
          this.rows.set(response.items);
          this.columns.set(response.columns);
          this.total.set(response.total);
          this.page.set(response.page);
          this.pageSize.set(response.page_size);
          this.loading.set(false);
        },
        error: (failure: ApiFailure) => {
          if (requestId !== this.requestCounter) {
            return;
          }
          this.rows.set([]);
          this.columns.set([]);
          this.total.set(0);
          this.failure.set(failure);
          this.loading.set(false);
        },
      });
  }
}
