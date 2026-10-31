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

  it('renders the project name in the header and the routed content outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('header')?.textContent).toContain('SOC L2');
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('routes the root path to the Cargar step', () => {
    expect(routes[0]).toEqual(jasmine.objectContaining({ path: '', redirectTo: 'cargar' }));
    const cargar = routes.find((route) => route.path === 'cargar');
    expect(cargar?.loadComponent).withContext('lazy Cargar step').toBeDefined();
  });
});
