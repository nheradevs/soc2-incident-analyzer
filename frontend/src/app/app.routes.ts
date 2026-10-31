import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'cargar' },
  {
    path: 'cargar',
    loadComponent: () =>
      import('./features/ingest/ingest-page').then((module) => module.IngestPage),
  },
  { path: '**', redirectTo: 'cargar' },
];
