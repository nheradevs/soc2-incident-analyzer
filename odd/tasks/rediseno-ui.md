# Rediseño de la interfaz (port del paquete de diseño a Angular 20)

Port de `design/soc2-analisis/` sobre la aplicación existente. El producto ya funciona; esta feature cambia su presentación y agrega cuatro comportamientos.

## Specs

- S1: `tokens.css` se importa una sola vez en `styles.scss`. Ningún color ni tipografía fuera de los tokens.
- S2: portar `cargar.html`, `analisis.html` e `informe.html`. Las bandas de documentación de las maquetas (estados vacío, cargando, error y las vistas de 832 y 390 px) son especificación, no pantalla a portar.
- S3: los números salen de la API y de `docs/sample-data.json`; el texto del informe es representativo en la maqueta y se reemplaza por el que devuelva la API.
- S4: ninguna pantalla desborda en horizontal a 1440, 832 ni 390 px.
- S5: la búsqueda de la tabla filtra contra la API mientras se escribe.
- S6: el switch del informe muestra una sola versión y la descarga corresponde a la versión activa.
- S7: el gráfico de horas mantiene el tramo seleccionado, con el pico como estado inicial.
- S8: cabecera que se mueve y se vuelve algo transparente al hacer scroll, pie con autoría y enlaces, favicon con la N.
- S9: español neutro con tú, sin guiones largos, sin mayúscula después de dos puntos salvo nombre propio.
- S10: se conserva el comportamiento existente y la suite sigue verde.

## Tasks

- T1 [S1,S2] Versionar el paquete de diseño como referencia estable. Commit `b940c7b`.
- T2 [S1,S2,S3,S8,S9] Port de shell, tokens, favicon y las tres pantallas con sus estados. Commit `feat(ui)`.
- T3 [S4,S5,S6,S7] Verificación medida de los cuatro comportamientos y del desborde a tres anchos. Commit `test(ui)` o incluido en T2.
- T4 [S10] Revisión del parent: build, suite completa, medición propia y commit del port.

## Log

- L1 (user, verbatim): "Necesito que portes el rediseño de las tres pantallas a la app Angular 20 existente. El paquete está en design/soc2-analisis/." Acompaña cinco instrucciones: leer `decisiones.md` completo en especial §3, §5, §6, §7 y §10; tokens desde `tokens.css` importado una vez en `styles.scss` sin colores ni fuentes nuevas; las maquetas son la referencia y las bandas de documentación son especificación de estados; los números salen de `docs/sample-data.json` y del Excel real, y el texto del informe se reemplaza por el de la API; y antes de dar por terminado, ningún desborde horizontal a 1440, 832 y 390, la búsqueda filtra contra la API al escribir, el switch del informe muestra una versión y la descarga la sigue, y el gráfico de horas mantiene el tramo seleccionado con el pico como estado inicial.
- L2 (user): pregunta si conviene commitear `design/` antes de que otro agente trabaje en el repo. Decisión: sí, y se hizo en un slice separado (`b940c7b`) para que el paquete quede como referencia estable y el port no se mezcle con él.
- L3 (open point): la descarga del informe. La API devuelve un único PDF que contiene las dos versiones por diseño, así que "la descarga sigue a esa versión" se implementa como acción contextual a la pestaña activa. Agregar un parámetro de versión al backend queda fuera del alcance de un port de frontend y se decide después.
- L4 (evidence): los tres work units del rediseño commiteados y publicados: `b940c7b` y `364e616` (paquete de diseño y su ronda de ajustes), `70ef3a6` (port de las tres pantallas, 71 specs, desborde medido a 1440/832/390), `2e3e7c7` (tokens vendorizados, Chart.js fuera, seis mensajes a tú, FSD actualizado; 281 tests backend y ruff limpio).
- L5 (evidence): ensayo final sobre la interfaz rediseñada, por el proxy del dev server: 715 filas, 12 columnas, un host duplicado detectado; 715 eventos, 6 incidentes, 46 hallazgos, 4 crítico y 2 alto; serie horaria con pico en 09:00 (176 eventos); informe con 9 secciones por versión y narrativa `no_configurada`; PDF 200 con 46.476 bytes; las tres rutas responden 200.
- L6 (decision del humano): la revisión automática del rediseño queda sin hacer por decisión explícita. El candidato completo es terminal por presupuesto del proveedor (`lens_context_budget_exceeded`, 81 archivos y unas 9.000 líneas) y el candidato acotado que sí abrió linaje (`review-a20ad1d141e28b53`) no pudo correr al revisor porque el entorno no tiene modelo asignado al agente `review-reliability`. Nada quedó mutado ni quemado.
- L7 (evidence): `docs/video-script.md` reescrito con los textos reales de la interfaz rediseñada (Cargar, Análisis, Informe, pasos 1 a 3, switch de versiones, descarga contextual, pico de las 09:00) para que el guion no mande a buscar botones que ya no existen.

