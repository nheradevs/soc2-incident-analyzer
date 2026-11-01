import {
  ReportPayload,
  ReportSection,
  ReportVersionKey,
} from '../models/report.models';

/** The nine mandatory titles, in the order and wording the backend sends them. */
export const REPORT_TITLES = [
  '1. Resumen ejecutivo',
  '2. Hallazgos identificados',
  '3. Explicación técnica de cada hallazgo',
  '4. Evidencias encontradas en los logs',
  '5. Criticidad y justificación',
  '6. Posible impacto en la organización',
  '7. Plan de acción: investigar → contener → remediar',
  '8. Recomendaciones generales de seguridad',
  '9. Limitaciones del análisis',
];

export const REPORT_SECTION_KEYS = [
  'resumen-ejecutivo',
  'hallazgos-identificados',
  'explicacion-tecnica',
  'evidencias-logs',
  'criticidad-justificacion',
  'impacto-organizacion',
  'plan-de-accion',
  'recomendaciones-generales',
  'limitaciones-analisis',
];

/** One section of the fixture; every body is an array of paragraphs and bullets. */
function section(
  index: number,
  body: string[],
  narrative: ReportSection['narrative'] = 'plantilla',
): ReportSection {
  return {
    number: index + 1,
    key: REPORT_SECTION_KEYS[index],
    title: REPORT_TITLES[index],
    body,
    narrative,
    narrative_reason: null,
  };
}

/**
 * Realistic shape of `POST /api/report`, mirroring the measured export: nine
 * sections per version, the narrative `no_configurada` (no key configured) and
 * the guard reporting no accepted rewrites.
 */
export function reportPayloadFixture(
  overrides: Partial<ReportPayload> = {},
): ReportPayload {
  const ejecutiva: ReportSection[] = [
    section(0, [
      'Se analizaron 715 eventos del export cargado, entre las 07:46:07 y las 13:44:06 del 2026-10-23.',
      'Se identificaron 2 incidentes: 1 crítico y 1 alto.',
    ]),
    section(1, [
      '• Fuerza bruta RDP con origen externo · criticidad crítico.',
      '• Inicio de sesión sospechoso en WEB-01 · criticidad alto.',
    ]),
    section(2, [
      'El primer incidente agrupa intentos repetidos de inicio de sesión desde una IP externa.',
    ]),
    section(3, ['• EVT-00130 · 2026-10-23 08:12:04 · WEB-01']),
    section(4, ['La clasificación se apoya en la matriz de impacto y confianza.']),
    section(5, ['Un compromiso de credenciales permitiría el uso indebido de las cuentas afectadas.']),
    section(6, [
      '• Investigar: revisar los intentos fallidos y confirmar si alguna credencial quedó comprometida.',
      '• Contener: bloquear el origen externo y forzar el cambio de contraseña.',
    ]),
    section(7, ['• Aplicar autenticación multifactor en el acceso remoto.']),
    section(8, ['La ventana analizada es de 5 h 58 min de un solo día.']),
  ];
  ejecutiva[0].narrative = 'no_configurada';

  const tecnica: ReportSection[] = [
    section(0, [
      'Se analizaron 715 eventos y 46 hallazgos, agrupados en 2 incidentes entre las 07:46:07 y las 13:44:06.',
      'Distribución por criticidad: crítico 1, alto 1, medio 0, bajo 0.',
    ]),
    section(1, [
      '• INC-20261023-0820 · Fuerza bruta RDP con origen externo · criticidad crítico.',
      '• INC-20261023-0936 · Inicio de sesión sospechoso en WEB-01 · criticidad alto.',
    ]),
    section(2, [
      'La regla D1c eleva la severidad de cualquier 4625 con origen externo.',
      'Los Log_ID citados existen en el export cargado.',
    ]),
    section(3, [
      '• EVT-00126 · 2026-10-23 08:09:51 · 4625 · admin · 203.0.113.74',
      '• EVT-00130 · 2026-10-23 08:12:04 · 4625 · admin · 203.0.113.74',
    ]),
    section(4, ['Impacto alto y confianza alta: 4 eventos de una IP externa en 2 min 13 s.']),
    section(5, ['Compromiso de credenciales y uso indebido de las cuentas afectadas.']),
    section(6, [
      '• Investigar: revisar los intentos fallidos y confirmar si alguna credencial quedó comprometida.',
      '• Contener: bloquear el origen externo y forzar el cambio de contraseña de las cuentas afectadas.',
    ]),
    section(7, ['• Aplicar autenticación multifactor y una política de bloqueo progresivo.']),
    section(8, ['La zona horaria del export no está declarada.']),
  ];
  tecnica[0].narrative = 'no_configurada';

  return {
    versions: {
      ejecutiva: {
        key: 'ejecutiva',
        label: 'Versión ejecutiva',
        narrative_status: 'no_configurada',
        sections: ejecutiva,
      },
      tecnica: {
        key: 'tecnica',
        label: 'Versión técnica',
        narrative_status: 'no_configurada',
        sections: tecnica,
      },
    },
    narrative: {
      configurada: false,
      proveedor: 'https://api.nan.builders/v1',
      modelo: 'deepseek-v4-flash',
      razonamiento: 'medium',
      estado: 'no_configurada',
      motivo:
        'No hay una clave de API configurada para la redacción asistida; el informe se genera con el motor de reglas.',
      solicitudes: 0,
      secciones_aplicadas: 0,
      secciones_con_error: 0,
    },
    guard: {
      aceptadas: [],
      rechazadas: [],
      secciones_aceptadas: 0,
      secciones_rechazadas: 0,
    },
    ...overrides,
  };
}

/** Payload whose versions carry the given bodies, for body-shape tests. */
export function reportPayloadWithBodies(
  ejecutivaBody: string | string[],
  tecnicaBody: string | string[],
): ReportPayload {
  const payload = reportPayloadFixture();
  for (const key of ['ejecutiva', 'tecnica'] as ReportVersionKey[]) {
    payload.versions[key].sections = payload.versions[key].sections.map((item) => ({
      ...item,
      body: key === 'ejecutiva' ? ejecutivaBody : tecnicaBody,
    }));
  }
  return payload;
}
