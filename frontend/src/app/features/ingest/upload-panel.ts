import { Component, ElementRef, inject, output, signal, viewChild } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiFailure, UploadResponse } from '../../core/models/ingest.models';
import { IngestApiService } from '../../core/services/ingest-api.service';

/** RF1 upload panel: drag & drop plus a file picker, with the backend message verbatim. */
@Component({
  selector: 'app-upload-panel',
  imports: [MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './upload-panel.html',
  styleUrl: './upload-panel.scss',
})
export class UploadPanel {
  private readonly api = inject(IngestApiService);

  private readonly fileInput = viewChild.required<ElementRef<HTMLInputElement>>('fileInput');

  readonly uploaded = output<UploadResponse>();
  readonly busy = signal(false);
  readonly dragging = signal(false);
  readonly error = signal<string | null>(null);
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

  private upload(file: File): void {
    if (this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.selectedFileName.set(file.name);

    this.api.upload(file).subscribe({
      next: (response: UploadResponse) => {
        this.finishUpload();
        this.uploaded.emit(response);
      },
      error: (failure: ApiFailure) => {
        this.error.set(failure.message);
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
