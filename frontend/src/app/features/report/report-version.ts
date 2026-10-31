import { Component, input } from '@angular/core';

import { ReportSectionBody, ReportVersion } from '../../core/models/report.models';
import { ReportBlock, reportBlocks } from './report-blocks';

/**
 * One audience version of the report: the nine sections exactly as the payload
 * sends them.
 *
 * Every section title and every block of its body is rendered; the body may be
 * a single string or an array of paragraphs and `•` list items (RF5).
 */
@Component({
  selector: 'app-report-version',
  templateUrl: './report-version.html',
  styleUrl: './report-version.scss',
})
export class ReportVersionPanel {
  readonly version = input.required<ReportVersion>();

  /** Section body grouped into paragraphs and lists, in payload order. */
  blockOf(body: ReportSectionBody): ReportBlock[] {
    return reportBlocks(body);
  }
}
