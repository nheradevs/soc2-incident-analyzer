import { Component, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiFailure, UploadResponse } from '../../core/models/ingest.models';
import { IngestApiService } from '../../core/services/ingest-api.service';

/**
 * RF1 upload panel: drag and drop plus a file picker, with the backend message
 * verbatim. The file summary it shows after a successful load comes from the
 * parent, so the panel never composes data the upload did not return.
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

  readonly uploaded = output<UploadResponse>();
  readonly busy = signal(false);
  readonly dragging = signal(false);
  readonly failure = signal<ApiFailure | null>(null);
  readonly selectedFileName = signal<string | null>(null);

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

  private upload(file: File): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.failure.set(null);
    this.selectedFileName.set(file.name);

    this.api.upload(file).subscribe({
      next: (response: UploadResponse) => {
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
