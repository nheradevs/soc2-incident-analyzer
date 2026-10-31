import { Component, computed, input } from '@angular/core';

import {
  CategoryCoverage,
  DashboardPayload,
} from '../../core/models/analysis.models';

/**
 * RF4 coverage and account transparency.
 *
 * Two things are shown instead of hidden: a category with no finding is named
 * as uncovered, and the principals left out of the human ranking are listed
 * with the reason the backend gives for excluding them.
 */
@Component({
  selector: 'app-coverage-panel',
  templateUrl: './coverage-panel.html',
  styleUrl: './coverage-panel.scss',
})
export class CoveragePanel {
  readonly payload = input.required<DashboardPayload>();

  readonly categories = computed<CategoryCoverage[]>(
    () => this.payload().coverage.categories,
  );

  readonly coveredCount = computed(
    () => this.categories().filter((category) => category.findings > 0).length,
  );

  /** Uncovered codes turned into the Spanish labels of the same payload. */
  readonly uncoveredLabels = computed(() => {
    const labels = new Map(
      this.categories().map((category) => [category.category, category.label]),
    );
    return this.payload()
      .coverage.uncovered_categories.map((code) => labels.get(code) ?? code)
      .join(', ');
  });

  readonly excludedAccounts = computed(
    () => this.payload().charts.excluded_accounts,
  );
}
