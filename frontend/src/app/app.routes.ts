import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'cargar' },
  {
    path: 'cargar',
    loadComponent: () =>
      import('./features/ingest/ingest-page').then((module) => module.IngestPage),
  },
  {
    path: 'analisis',
    loadComponent: () =>
      import('./features/analysis/analysis-page').then((module) => module.AnalysisPage),
  },
  {
    path: 'informe',
    loadComponent: () =>
      import('./features/report/report-page').then((module) => module.ReportPage),
  },
  { path: '**', redirectTo: 'cargar' },
];
