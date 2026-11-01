import { Component, HostListener, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

/**
 * Application shell: sticky header with the three screen links and the page
 * footer with the author. The header turns slightly translucent once the page
 * scrolls, which is colour only, never a blur.
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  readonly stuck = signal(false);

  @HostListener('window:scroll')
  onWindowScroll(): void {
    this.stuck.set(window.scrollY > 8);
  }
}
