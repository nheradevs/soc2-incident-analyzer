import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { routes } from './app.routes';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('renders the product name in the header and the routed content outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('header')?.textContent).toContain('Análisis SOC 2');
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('links the three screens from the header and credits the author in the footer', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;

    const targets = Array.from(compiled.querySelectorAll('.nav a')).map((link) =>
      link.getAttribute('href'),
    );
    expect(targets).toEqual(['/cargar', '/analisis', '/informe']);

    const footer = compiled.querySelector('footer') as HTMLElement;
    expect(footer.textContent).toContain('Karen Gil');
    expect(footer.textContent).toContain('Analista SOC 2');
    const profiles = Array.from(footer.querySelectorAll('a')).map((link) =>
      link.getAttribute('href'),
    );
    expect(profiles).toEqual([
      'https://github.com/nheradevs',
      'https://www.linkedin.com/in/karen-gil-g',
    ]);

    const external = Array.from(footer.querySelectorAll('a'));
    for (const link of external) {
      expect(link.getAttribute('target')).toBe('_blank');
      expect(link.getAttribute('rel')).toContain('noopener');
      expect(link.getAttribute('rel')).toContain('noreferrer');
    }
  });

  it('routes the root path to the Cargar step', () => {
    expect(routes[0]).toEqual(jasmine.objectContaining({ path: '', redirectTo: 'cargar' }));
    const cargar = routes.find((route) => route.path === 'cargar');
    expect(cargar?.loadComponent).withContext('lazy Cargar step').toBeDefined();
  });
});
