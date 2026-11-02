# `app.reporting`: informe determinístico + redacción asistida opcional

El **producto** es el informe determinístico: las nueve secciones obligatorias
(FSD §7.4), en sus dos versiones (`ejecutiva` y `tecnica`), generadas con reglas
a partir del análisis. Se produce siempre, sin clave y sin red.

La **redacción asistida por IA es un extra opcional**. Sólo se activa si hay una
clave configurada, y su ausencia no degrada el informe: cambia únicamente el
estado que se publica en el payload.

## Estados de la redacción asistida

| Estado | Cuándo | Efecto en el informe |
| --- | --- | --- |
| `no_configurada` | No hay `NAN_API_KEY` en el entorno. | Informe completo con redacción determinística. Se menciona una sola vez en la sección 8. |
| `deshabilitada_por_error` | Hay clave, pero la sección conserva el texto determinístico por timeout, error de red, error HTTP, respuesta inválida o rechazo del guard. | Informe completo; el motivo por sección queda en `narrative_reason` y en `guard.rechazadas`. |
| `aplicada` | El proveedor respondió y el guard aceptó la reescritura. | La sección usa el texto aceptado. |

`parcial` es la combinación de `aplicada` con `deshabilitada_por_error` cuando el
informe tiene secciones de los dos tipos. Las secciones que por diseño no pasan
por el modelo (evidencias, justificación de criticidad y limitaciones) llevan
`plantilla`.

## Activar la redacción asistida

Cualquier proveedor **OpenAI-compatible** sirve; no hay código específico de un
proveedor. La configuración vive en el entorno:

```dotenv
NAN_API_KEY=<clave>
NAN_BASE_URL=https://api.nan.builders/v1   # cambiable por cualquier gateway compatible
NAN_MODEL=deepseek-v4-flash                # modelo del proveedor
NAN_REASONING_EFFORT=low                   # none|minimal|low|medium|high|xhigh|max
```

Requisitos del cliente:

- `POST {NAN_BASE_URL}/chat/completions` con `Authorization: Bearer <clave>`.
- `stream: true` es obligatorio: sin streaming el gateway puede cortar la
  petición larga.
- Se hacen como máximo tres peticiones por versión (secciones 1, 6 y 7) y se
  limita la concurrencia a 4 peticiones simultáneas, por debajo del límite de 7
  del proveedor.

La clave nunca se registra, ni se devuelve en una respuesta, ni viaja al
frontend. Tampoco se registran el prompt ni la respuesta completa: sólo el
estado y el motivo acotado.

## Guard anti-alucinación

`guard.check` acepta una reescritura sólo si:

1. cada `Log_ID` citado pertenece a la evidencia permitida para esa sección (la
   versión ejecutiva no permite ninguno);
2. cada identificador `INC-` nombrado existe en el análisis;
3. cada criticidad afirmada coincide con la que asignó el clasificador.

En caso contrario se conserva el texto determinístico de esa sección y se
registran los motivos. El modelo nunca decide hallazgos, niveles ni conteos.

## Determinismo

`render_sections` es una función pura del brief: sin reloj, sin orden no
determinista y sin estado global. Dos ejecuciones con el mismo análisis producen
exactamente el mismo texto. La única parte variable es la prosa aceptada del
modelo.
