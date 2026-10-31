/**
 * Presentation helpers shared by the dashboard panels.
 *
 * They format values the payload already contains; none of them derives a
 * number the backend did not measure. Spanish notation, English identifiers.
 */

import { OutboundDestination } from '../../core/models/analysis.models';

// Decimal megabytes, the unit the FSD uses for the measured 253 305 558 bytes.
const BYTES_PER_MB = 1_000_000;

/** Timestamp exactly as the export shows it: second precision, no `T`. */
export function formatTimestamp(value: string | null): string {
  if (value === null || value === '') {
    return 'sin datos';
  }
  return value.slice(0, 19).replace('T', ' ');
}

/** Duration of the export window in hours and minutes. */
export function formatDuration(minutes: number): string {
  if (minutes <= 0) {
    return 'sin duración medible';
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours === 0) {
    return `${remainder} min`;
  }
  if (remainder === 0) {
    return `${hours} h`;
  }
  return `${hours} h ${remainder} min`;
}

/** Bytes as megabytes in Spanish notation, e.g. `241,6 MB`. */
export function formatBytes(bytes: number): string {
  const megabytes = new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(bytes / BYTES_PER_MB);
  return `${megabytes} MB`;
}

/** Port of a destination, or an explicit note when the export has none. */
export function formatPort(port: number | null): string {
  return port === null ? ' (sin puerto)' : `:${port}`;
}

/**
 * Whether the export measured the volume sent to a destination.
 *
 * `events_with_bytes === 0` means no cited row carried `bytes_out`; the total
 * is then unknown and must never be presented as zero traffic.
 */
export function hasKnownBytes(destination: OutboundDestination): boolean {
  return destination.events_with_bytes > 0;
}
