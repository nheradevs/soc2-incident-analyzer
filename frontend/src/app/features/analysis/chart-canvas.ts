import {
  AfterViewInit,
  Component,
  ElementRef,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  input,
  viewChild,
} from '@angular/core';
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  ChartConfiguration,
  DoughnutController,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';

// Only the controllers and scales the dashboard uses are registered: this code
// ships in the lazy analysis chunk and Chart.js is tree-shakeable.
Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  DoughnutController,
  ArcElement,
  Tooltip,
  Legend,
);

/**
 * Canvas host for one Chart.js chart (FSD RF4).
 *
 * The chart is created from the configuration the caller builds out of the
 * payload, so no series exists that the backend did not return. The canvas is
 * also described through `description` because a canvas is opaque to a screen
 * reader.
 */
@Component({
  selector: 'app-chart-canvas',
  templateUrl: './chart-canvas.html',
  styleUrl: './chart-canvas.scss',
})
export class ChartCanvas implements AfterViewInit, OnChanges, OnDestroy {
  readonly config = input.required<ChartConfiguration>();
  readonly description = input('');

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private chart: Chart | null = null;

  ngAfterViewInit(): void {
    this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    const config = changes['config'];
    if (config !== undefined && !config.firstChange) {
      this.render();
    }
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
    this.chart = null;
  }

  private render(): void {
    this.chart?.destroy();
    this.chart = new Chart(this.canvas().nativeElement, this.config());
  }
}
