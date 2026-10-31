/**
 * Honest rendering of a section body.
 *
 * The backend sends the body of a section either as one string or as an array
 * of strings, where the bullet entries are prefixed with `•`. The body is
 * grouped into paragraphs and bullet lists in the order it arrives; no line is
 * merged, reordered or dropped.
 */

import { ReportSectionBody } from '../../core/models/report.models';

export interface ReportParagraph {
  kind: 'paragraph';
  text: string;
}

export interface ReportList {
  kind: 'list';
  items: string[];
}

export type ReportBlock = ReportParagraph | ReportList;

const LEADING_MARKER = /^[•*-]\s+/;

/** Body lines: a string is split on line breaks, an array is taken as given. */
function bodyLines(body: ReportSectionBody): string[] {
  const lines = typeof body === 'string' ? body.split(/\r?\n/) : body;
  return lines.map((line) => line.trim()).filter((line) => line !== '');
}

function isBullet(line: string): boolean {
  return LEADING_MARKER.test(line);
}

function stripMarker(line: string): string {
  return line.replace(LEADING_MARKER, '').trim();
}

/** Paragraphs and bullet lists of one section body, in payload order. */
export function reportBlocks(body: ReportSectionBody): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  for (const line of bodyLines(body)) {
    const last = blocks[blocks.length - 1];
    if (isBullet(line)) {
      const text = stripMarker(line);
      if (last !== undefined && last.kind === 'list') {
        last.items.push(text);
      } else {
        blocks.push({ kind: 'list', items: [text] });
      }
      continue;
    }
    blocks.push({ kind: 'paragraph', text: line });
  }
  return blocks;
}
