import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { UploadPanel } from './upload-panel';
import { UploadResponse } from '../../core/models/ingest.models';
import { uploadResponseFixture } from '../../core/testing/api-fixtures';

function selectFile(input: HTMLInputElement, file: File): void {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event('change'));
}

describe('UploadPanel', () => {
  let fixture: ComponentFixture<UploadPanel>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UploadPanel],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(UploadPanel);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function fileInput(): HTMLInputElement {
    const input = fixture.nativeElement.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).withContext('file input').not.toBeNull();
    return input;
  }

  it('exposes an accessible label and restricts the picker to .xlsx files', () => {
    const input = fileInput();
    expect(input.getAttribute('accept')).toBe('.xlsx');

    const labelledBy = input.getAttribute('aria-labelledby');
    expect(labelledBy).withContext('aria-labelledby').not.toBeNull();
    const label = fixture.nativeElement.querySelector(`#${labelledBy}`) as HTMLElement;
    expect(label).withContext('label element').not.toBeNull();
    expect(label.textContent).toContain('Elegir archivo .xlsx');

    const button = fixture.nativeElement.querySelector('button') as HTMLButtonElement;
    expect(button.getAttribute('type')).toBe('button');
  });

  it('uploads a dropped file and emits the parsed response', () => {
    let emitted: UploadResponse | undefined;
    fixture.componentInstance.uploaded.subscribe((response) => (emitted = response));

    const file = new File(['content'], 'SOC_L2_Logs.xlsx');
    const dropZone = fixture.nativeElement.querySelector('.drop-zone') as HTMLElement;
    const event = new Event('drop') as Event & { dataTransfer: DataTransfer };
    const transfer = new DataTransfer();
    transfer.items.add(file);
    event.dataTransfer = transfer;
    dropZone.dispatchEvent(event);

    const request = http.expectOne('/api/upload');
    const body = request.request.body as FormData;
    expect(body.get('file')).toBe(file);

    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Validando');

    const response = uploadResponseFixture();
    request.flush(response);
    fixture.detectChanges();

    expect(emitted).toEqual(response);
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('Validando');
  });

  it('renders the backend rejection message verbatim and emits nothing', () => {
    let emitted = false;
    fixture.componentInstance.uploaded.subscribe(() => (emitted = true));
    const detail = 'El archivo está vacío. Seleccione un export .xlsx válido.';

    selectFile(fileInput(), new File([''], 'empty.xlsx'));
    http
      .expectOne('/api/upload')
      .flush({ detail }, { status: 400, statusText: 'Bad Request' });
    fixture.detectChanges();

    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert?.textContent).toContain(detail);
    expect(alert?.textContent).toContain('Detalle: 400');
    expect(emitted).toBeFalse();
    expect(fileInput().value).toBe('');
  });
});
