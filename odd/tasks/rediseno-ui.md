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
