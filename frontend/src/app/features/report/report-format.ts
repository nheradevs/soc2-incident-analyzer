/**
 * Presentation helpers of the Informe step.
 *
 * They only translate states the payload already carries into Spanish; none of
 * them decides whether the report is complete, because the nine sections are
 * always rendered by the backend.
 */

import { NarrativeState, ReportVersionKey } from '../../core/models/report.models';

const TAB_LABELS: Record<ReportVersionKey, string> = {
  ejecutiva: 'Versión ejecutiva',
  tecnica: 'Versión técnica',
};

/** Spanish label of the toggle that selects one audience version. */
export function versionTabLabel(key: ReportVersionKey): string {
  return TAB_LABELS[key];
}

/**
 * Neutral wording of the assisted-writing state. Every line is a statement of
 * configuration, never of missing content: the deterministic report is the
 * product and the state is reported once.
 */
const NARRATIVE_LINES: Record<NarrativeState, string> = {
  aplicada: 'Redacción asistida: aplicada en las secciones que la admiten.',
  parcial:
    'Redacción asistida: aplicada en una parte de las secciones; el resto conserva la redacción del motor de reglas.',
  no_configurada: 'Redacción asistida: no configurada en esta instalación.',
  deshabilitada_por_error:
    'Redacción asistida: se conservó la redacción del motor de reglas.',
  plantilla: 'Redacción asistida: redacción generada por el motor de reglas.',
};

const UNKNOWN_STATE_LINE = 'Redacción asistida: el servidor no informó el estado.';

/** One Spanish line for the narrative state the payload reports. */
export function narrativeStateLine(state: string | undefined): string {
  if (state !== undefined && Object.prototype.hasOwnProperty.call(NARRATIVE_LINES, state)) {
    return NARRATIVE_LINES[state as NarrativeState];
  }
  return UNKNOWN_STATE_LINE;
}
