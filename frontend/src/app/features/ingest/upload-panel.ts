import { Component, ElementRef, computed, inject, input, output, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiFailure, UploadResponse, isRetryableFailure } from '../../core/models/ingest.models';
import { IngestApiService } from '../../core/services/ingest-api.service';

/**
 * RF1 upload panel: drag and drop plus a file picker, with the backend message
 * verbatim. The file summary it shows comes from the parent, so the panel never
 * composes data no endpoint returned: a summary restored from `/api/session`
 * and one returned by an upload render through the same path.
 */
@Component({
  selector: 'app-upload-panel',
  imports: [RouterLink],
  templateUrl: './upload-panel.html',
  styleUrl: './upload-panel.scss',
})
export class UploadPanel {
  private readonly api = inject(IngestApiService);

  private readonly fileInput = viewChild.required<ElementRef<HTMLInputElement>>('fileInput');

  readonly summary = input<UploadResponse | null>(null);

  /** True while the page is asking the server whether it already holds a file. */
  readonly checking = input(false);

  readonly uploaded = output<UploadResponse>();
  readonly busy = signal(false);
  readonly dragging = signal(false);
  readonly failure = signal<ApiFailure | null>(null);
  readonly selectedFileName = signal<string | null>(null);

  /** The last file the user handed over, so a retry re-sends that same file. */
  private lastFile: File | null = null;

  /** One-word state of the card header; never claims a file the panel has not seen. */
  readonly cardNote = computed(() => {
    if (this.busy()) {
      return 'Leyendo el archivo';
    }
    return this.checking() ? 'Revisando' : '.xlsx';
  });

  /** What the loading state says it is doing, so the wait is never anonymous. */
  readonly statusText = computed(() =>
    this.busy()
      ? `Validando ${this.selectedFileName() ?? ''}`.trim()
      : 'Revisando si ya hay un archivo cargado',
  );

  /** A retry only makes sense when the failure could have a different outcome. */
  readonly canRetry = computed(() => {
    const failure = this.failure();
    return failure !== null && isRetryableFailure(failure);
  });

  onFileInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.item(0) ?? null;
    if (file !== null) {
      this.upload(file);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDragLeave(): void {
    this.dragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files.item(0) ?? null;
    if (file !== null) {
      this.upload(file);
    }
  }

  chooseFile(): void {
    this.fileInput().nativeElement.click();
  }

  /** Re-sends the exact file that failed, without making the user pick it again. */
  retryUpload(): void {
    const file = this.lastFile;
    if (file !== null) {
      // Keep the failure on screen: clearing it would unmount the very button
      // that has to show the retry is running.
      this.upload(file, true);
    }
  }

  /** Compact window of the loaded export, e.g. `23/10/2026 07:46 a 13:44`. */
  fileWindow(response: UploadResponse): string {
    const start = response.time_range.start;
    const end = response.time_range.end;
    if (start === null || end === null) {
      return 'sin ventana medible';
    }
    const [date, startTime] = start.split('T');
    const [, endTime] = end.split('T');
    const parts = date.split('-');
    if (parts.length !== 3 || startTime === undefined || endTime === undefined) {
      return `${start} a ${end}`;
    }
    return `${parts[2]}/${parts[1]}/${parts[0]} ${startTime.slice(0, 5)} a ${endTime.slice(0, 5)}`;
  }

  private upload(file: File, keepFailureOnStart = false): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    if (!keepFailureOnStart) {
      this.failure.set(null);
    }
    this.lastFile = file;
    this.selectedFileName.set(file.name);

    this.api.upload(file).subscribe({
      next: (response: UploadResponse) => {
        this.failure.set(null);
        this.finishUpload();
        this.uploaded.emit(response);
      },
      error: (failure: ApiFailure) => {
        this.failure.set(failure);
        this.finishUpload();
      },
    });
  }

  private finishUpload(): void {
    this.busy.set(false);
    // Clearing the picker lets the user re-select the same file, e.g. after a fix.
    this.fileInput().nativeElement.value = '';
  }
}
