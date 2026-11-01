# Decisiones de diseño: analizador SOC Nivel 2

Documento de traspaso. Explica qué se eligió, por qué, y qué se descartó para poder portar las maquetas sin adivinar nada.

## 1. Qué hay en esta carpeta

| Archivo | Qué es |
| --- | --- |
| `tokens.css` | Los tokens portables: colores, escala tipográfica, espaciados, radios, sombras y puntos de quiebre. |
| `cargar.html` | Maqueta de la pantalla de carga, con sus cuatro estados y las vistas de tableta y móvil. |
| `analisis.html` | Maqueta del dashboard, con sus cuatro estados y las vistas de tableta y móvil. |
| `informe.html` | Maqueta del informe, con sus cuatro estados y las vistas de tableta y móvil. |
| `favicon.svg` | La letra N blanca sobre fondo negro, para reemplazar `frontend/public/favicon.ico`. |
| `design.json` | Manifiesto del canvas: título, brief y tabla de artboards. |

Cada maqueta es un archivo suelto que se abre con doble clic. Arriba está la pantalla real con datos y debajo dos bandas de documentación: los estados y las vistas de tableta y móvil. Las bandas no forman parte del producto, son parte del entregable.

Dos convenciones del entregable:

- Cada maqueta lleva el bloque de tokens inline porque tiene que poder abrirse sin servidor. `tokens.css` tiene exactamente los mismos valores para que el port importe un solo archivo.
- Las vistas de tableta y móvil no son copias: el script clona el marcado real de la pantalla y lo mete en un marco de 832 px o de 390 px. Lo que se ve en esas vistas es el mismo HTML que se va a portar, no un dibujo aparte.

## 2. Tipografía

**Poppins en títulos. Inter en todo lo demás.**

Por qué Inter y no otra:

- **Coincidencia de caja.** Poppins tiene una altura de x alta y formas geométricas; Inter también, así que los títulos y el cuerpo se apoyan en la misma línea de lectura sin que uno domine al otro. Una fuente de caja baja al lado de Poppins se ve más chica de lo que es y obliga a subir el cuerpo a 17 o 18 px.
- **Está dibujada para pantalla.** Inter resuelve bien los tamaños chicos sobre fondo oscuro, que es el 90 % del texto de este producto: tabla de eventos, evidencia, metadatos de incidente.
- **Cifras tabulares.** `font-variant-numeric: tabular-nums` da columnas de números alineadas. En esta interfaz hay marcas de tiempo, conteos de eventos, IDs de fila y bytes; sin cifras tabulares la tabla se lee mal y parece sucia.
- **Contraste de voz.** Poppins aporta la personalidad en títulos cortos; Inter es neutra y deja que el contenido mande. La jerarquía se ve por forma y tamaño, no por decoración.
- **Disponibilidad.** Ambas están en Google Fonts, con los cuatro pesos que se usan (Poppins 500 y 600, Inter 400, 500 y 600).

Descartadas, con motivo: **Source Sans 3** (más humanista, se lleva peor con la geometría de Poppins), **IBM Plex Sans** (tiene carácter propio y compite con Poppins por la atención), **Work Sans** (demasiado geométrica, los títulos pierden contraste contra el cuerpo), **Lato y Open Sans** (caja baja y cifras menos parejas en tablas).

Escala: base 16 px, razón 1,25, con clima fluido arriba. Cuerpo de lectura `clamp(1rem, 0.96rem + 0.2vw, 1.0625rem)` y nunca por debajo de 16 px en móvil. Títulos: h1 de 34 a 52 px, h2 de 24 a 30, h3 de 24, h4 de 20. Medida de línea del informe limitada a 74 caracteres y de los párrafos de interfaz a 58 o 62.

## 3. Paleta

Los cinco colores del brief más un tono claro de la misma familia, que es el que se usa como texto principal. No se agregó ningún color ajeno.

| Token | Valor | Uso | Contraste medido |
| --- | --- | --- | --- |
| `--color-bg` | `#0E161B` | Fondo de página | |
| `--color-surface` | `#162022` | Sección, banda de apoyo, campo de formulario | |
| `--color-card` | `#232E30` | Tarjeta, tabla, panel de gráfico | |
| `--color-line` | `#314048` | Bordes de control, separadores internos, carril de barras | |
| `--color-muted` | `#56666F` | Iconografía, trazos, texto grande | 3.07 sobre el fondo |
| `--color-text` | `#E4EBED` | Texto principal | 15.14 sobre `bg`, 11.57 sobre `card` |

Dos consecuencias que conviene entender antes de portar:

1. **`#56666F` no sirve para texto chico.** Sobre la tarjeta mide 2.34:1 y el mínimo AA para texto corrido es 4.5:1. Se reserva para iconos, líneas de gráfico y texto grande, que es exactamente lo que el brief le asigna. El texto secundario legible usa un escalón más claro de la misma familia, `--color-text-soft` `#A9B6BB` (8.78 sobre `bg`, 6.71 sobre `card`). No es un color nuevo: es el mismo neutro un paso más arriba, y es la única forma de tener texto secundario en esta paleta sin romper contraste.
2. **La profundidad la hace el valor de superficie, no el borde.** Fondo, sección y tarjeta son tres escalones del mismo neutro. Por eso no hay líneas en los bordes de la página ni del contenedor: no hacen falta para separar planos.

Semánticos de criticidad, cuatro, con la lógica más sobria posible:

| Nivel | Token | Sobre `card` |
| --- | --- | --- |
| crítico | `--color-critical` `#E08370` | 5.08:1 |
| alto | `--color-high` `#CFA05A` | 5.87:1 |
| medio | `--color-medium` `#8FADB9` | 5.88:1 |
| bajo | `--color-low` `#A9A89F` | 5.84:1 |

Todos pasan AA como texto y 3:1 como relleno de gráfico. La criticidad se muestra con un punto de color más la palabra, nunca con la palabra coloreada sola: así el color es una ayuda y no el único portador de la información para quien no distingue matices.

El tono de «bajo» cambió después de la primera entrega: era `#8FA0A7`, seis puntos de valor por debajo del azul acero de «medio», y en un gráfico o en un punto los dos niveles se leían igual. Ahora es un neutro cálido `#A9A89F`, que se separa del azul acero por temperatura y no por saturación, y mantiene la regla de no introducir un verde. Los cuatro niveles quedan en cuatro familias: rojo, ámbar, azul acero y neutro cálido.

**No hay verde.** El éxito de una carga se comunica por la ausencia de error, no por un color festivo. Menos colores, menos ruido, y el único cromatico que aparece cuando algo importa es el de criticidad y el de error, que comparten tono.

## 4. Jerarquía

Un solo `h1` por pantalla, después `h2` para bloques y `h3` para lo que va dentro. Sin saltos. En el informe, `h1` es el título de la pantalla, `h2` es la versión y `h3` es cada una de las nueve secciones, con su número incluido porque el backend ya las entrega numeradas.

Tres reglas que ordenan el resto:

- **Nada de etiquetas en mayúsculas arriba de los títulos.** El contexto del paso se dice en una línea normal: «Paso 2 de 3», con una raya corta de 20 px como marca, sin versalitas ni espaciado de letras.
- **El peso hace el trabajo del tamaño.** h3 y h4 están a 24 y 20 px: la diferencia la da el peso y el color, no saltar a 32 px y romper la escala.
- **Encabezados de tabla en caja normal**, 14 px, en `--color-text-soft`. No son etiquetas decorativas, son texto que se lee.

## 5. Estructura

**Cabecera.** Sticky, con fondo opaco en reposo. Al pasar los 8 px de scroll se le agrega la clase `is-stuck` y el fondo pasa a `rgba(14, 22, 27, 0.86)` con una sombra profunda y de poca opacidad. Esa transparencia es color, no desenfoque: no hay `backdrop-filter` en ningún lado. Debajo, un filete de 1 px en el borde inferior del ítem activo de navegación, no en el borde de la página.

**Pie.** Autoría a la izquierda (Karen Gil, Analista SOC 2) y los dos enlaces a la derecha, con el icono en `--color-muted`. El mismo pie se repite en el PDF como línea de texto: «Karen Gil, Analista SOC 2», que es el cambio que el brief pide sobre la línea actual de la consultora.

**Ancho.** 1240 px de contenido con gutter fluido de 20 a 48 px. El informe usa una columna de lectura de 74 caracteres y una columna lateral de 336 px para la descarga.

**Adaptación.** Las reglas se escribieron con container queries sobre el contenedor de página, no con media queries. Motivo: la misma regla sirve para la ventana real y para las vistas embebidas del entregable, así que lo que se revisa es lo que se porta. Al pasar a Angular, si hiciera falta compatibilidad con navegadores sin container queries, cada `@container (max-width: 62rem)` se convierte en `@media (max-width: 62rem)` sin cambiar ningún valor.

Una salvedad sobre las vistas embebidas: la escala tipográfica fluida y el gutter usan `vw`, que se mide contra la ventana real. Abierto un marco de 390 px en un escritorio, los títulos de adentro se ven al tamaño de escritorio; el reflujo de columnas, que es lo que hay que validar, es idéntico. En un teléfono real la escala baja sola, porque ahí la ventana mide lo que mide el marco.

Un detalle del layout que no es obvio: los anchos de los controles se resolvieron con el contenedor flex y no con `vw`. Un campo de búsqueda calibrado con `vw` se desborda cuando la columna es más angosta que la ventana, y ese fue el único desborde horizontal que apareció en la revisión de los 390 px.

| Punto | Qué cambia |
| --- | --- |
| 1280 px o más | Dos columnas en carga y en el dashboard, lateral fijo en el informe. |
| 992 px (62rem) | El dashboard pasa a una columna: primero la lista de incidentes, después el detalle. Carga a una columna. El lateral del informe sube arriba del texto, porque la descarga no puede quedar al final de veinte párrafos. |
| 832 px | Indicadores de riesgo en dos columnas. Los gráficos a una columna. |
| 768 px (48rem) | El nombre del producto al lado del logotipo se oculta y queda solo la marca. Los tres enlaces de navegación siguen visibles en una fila compacta: entran junto al logotipo, así que no hay botón de menú que no lleve a ningún lado. |
| 480 px (30rem) | Todo a una sola columna, indicadores apilados, entidades y definiciones a una columna. La tabla de eventos conserva el desplazamiento horizontal. |

La tabla nunca se convierte en tarjetas: en un análisis de seguridad la fila comparada contra la fila de arriba es la que informa, y apilarla destruye esa lectura. Se mantiene el desplazamiento horizontal, con los identificadores fijos a la izquierda y la barra de desplazamiento dibujada: si la barra no se ve, nadie adivina que hay más columnas. En el teléfono el paginador envuelve en dos líneas antes que salirse de la tarjeta.

## 6. Orden del dashboard

El brief dejaba abierto el orden. La decisión: riesgo primero, incidentes segundo, evidencia tercera, contexto cuarto.

1. **Indicadores de criticidad** en una fila de cuatro. Es la primera pregunta que se hace un analista: qué tan grave es esto. La fila lleva una línea de contexto con eventos, hallazgos, incidentes y ventana.
2. **Lista de incidentes por severidad** a la izquierda y **detalle del incidente seleccionado** a la derecha, en la misma pantalla. El detalle es el que lleva más ancho, porque es el que se lee.
3. **Contexto** en cuatro gráficos debajo: eventos por hora, tipos de hallazgo, equipos y salida externa. Es información de apoyo para explicar, no para decidir.
4. **Alcance y límites** al final, incluidas las exclusiones declaradas y lo que el informe va a decir sobre limitaciones.

La alternativa del brief (indicadores a un lado, gráficos al otro, resto debajo) pone el volumen por delante del incidente. Un analista Nivel 2 no arranca por el volumen: arranca por lo que pasó.

Los gráficos son barras y listas de barras, sin ejes dobles ni series inventadas. Sin rejilla: cada barra lleva su valor al lado y la etiqueta debajo.

En «Tipos de hallazgo» y «Equipos con más eventos» la barra codifica dos cosas: el largo es la cantidad y el color es la criticidad, tomada de la paleta semántica que ya usa el resto de la pantalla. Cada uno de esos dos gráficos lleva su leyenda, porque el color solo no explica qué significa.

- **Tipos de hallazgo:** el color es el impacto máximo que la matriz de riesgo (`backend/app/risk/matrix.py`) asigna a ese detector. D1d, D3 y D4 pueden fijar un crítico; D1b, D2, D5, D6 y D7 un alto; D1a y D1c un medio. No se inventó un nivel por barra: sale de la tabla de impacto que ya existe en el motor.
- **Equipos con más eventos:** el color es la criticidad del incidente más grave que toca al equipo, y en gris quedan los equipos que aparecen en el export pero en ningún incidente. Es la diferencia entre «muchos eventos» y «equipo comprometido», que es justo lo que el volumen solo no dice.

«Eventos por hora» es un selector, no una lámina: cada barra es un botón y debajo del gráfico hay un bloque que dice qué pasó en el tramo elegido (cuántos eventos, qué porcentaje del día y qué incidentes lo cruzan). Arranca con el pico ya seleccionado, a las 09:00, y con la etiqueta «Pico del día» a la vista: sin ese estado inicial nadie adivina que las barras se tocan. El blanco del tono principal marca el tramo elegido, no la criticidad, porque acá no hay criticidad: hay volumen.

Ese bloque también resuelve un problema de composición. Las tarjetas de gráfico no se estiran a la altura de la más alta de la fila: con `align-self: start` cada una mide lo que mide su contenido. Antes, la de «Eventos por hora» se estiraba hasta igualar a «Tipos de hallazgo» y quedaba un hueco de doscientos píxeles debajo de las barras.

## 7. Datos

Todo número de las maquetas sale de `docs/sample-data.json` o del propio Excel: 715 eventos, 12 columnas, 46 hallazgos, 6 incidentes, 4 críticos y 2 altos, ventana de 5 h 58 min entre las 07:46:07 y las 13:44:06 del 23/10/2026, los seis identificadores de incidente, las 12 filas de evidencia y los bytes de salida (253.305.558 hacia 198.51.100.88).

Tres puntos que requieren tu decisión al portar:

- **El texto de las nueve secciones del informe** no viene en `sample-data.json`, que trae hechos y no prosa. Se redactó usando solo esos hechos, con el tono del brief, y cita los Log_ID reales. Los números coinciden con el dashboard. Al conectar el backend, ese texto se reemplaza por el que devuelve la API: la maqueta no pretende ser el texto final del motor de reglas.
- **`frontend/src/app/core/testing/report-fixtures.ts` describe un análisis con 2 incidentes**, no 6. Es un fixture de forma, no de contenido, y por eso no se usó para los números. Si ese archivo se usa como referencia de contenido en algún test, conviene revisarlo aparte.
- **Los mensajes de error** son representativos: «Detalle: 400 · el archivo no contiene filas de eventos» muestra el patrón de una línea de detalle técnico. En el port se debe mostrar el `detail` real del backend, tal como ya hace `ApiFailure`, sin reformularlo.

## 8. Redacción

Se aplicó el brief al pie de la letra: español neutro con tú, sin usted, sin superlativos, sin lenguaje de ventas, sin guiones largos ni rayas en ningún texto, sin mayúscula después de dos puntos salvo nombre propio. Los campos que vienen del SIEM (Log_ID, Event_ID, Result, descripciones de evento) se muestran tal como llegan: son datos, no copy, y traducirlos rompería la trazabilidad contra el Excel.

Los títulos de incidente del backend usan flechas («Fuerza bruta → inicio de sesión sospechoso»). Se respetan: son parte del dato, no decoración.

## 9. Qué descarté

- **Tres direcciones visuales distintas.** El brief fija paleta, tipografía, pie y estructura de las tres pantallas; tres variantes habrían sido tres veces el mismo sistema con distinto color. Una dirección coherente y tres pantallas terminadas rinde más para portar.
- **Vidrio esmerilado, desenfoques y cualquier `backdrop-filter`.** La cabecera se vuelve translúcida con color, sin blur.
- **Líneas de marco en página y contenedor.** Los planos se separan por valor de superficie. Los únicos bordes son los de control (campo, botón secundario) y los separadores internos de tabla y sección.
- **Etiquetas pequeñas en mayúsculas arriba de los títulos.** Se reemplazaron por la línea «Paso n de 3» en caja normal.
- **Las dos versiones del informe apiladas.** Era la primera entrega y estaba mal: con un selector arriba, mostrar las dos completas obliga a scrollear media página para llegar a la segunda y deja ambiguo qué PDF se descarga. Ahora el selector decide qué versión se lee y la descarga sigue a la versión elegida. Si alguien quiere las dos, cambia el selector: es un clic, no una página entera.
- **Ranking de direcciones IP de origen.** El brief lo prohíbe porque en este export una dirección interna aparece como origen de diez equipos. La interfaz lo dice explícitamente en el panel de alcance, en lugar de omitirlo en silencio.
- **Gráfico de torta o de anillo para la distribución de riesgo.** Cuatro categorías con dos valores en cero se leen mejor como cuatro números.
- **Un verde de éxito.** Ya explicado en la paleta.
- **Estados vacíos ilustrados.** Un icono grande y un texto genérico no dicen nada. El estado vacío explica qué va a aparecer y en qué orden.

## 10. Notas para el port a Angular Material

- Los tokens entran como variables CSS globales en `styles.scss`. Angular Material 20 permite mapear su tema oscuro sobre las mismas variables; conviene declararlas en `:root` y no dentro de un componente.
- Componentes con más trabajo de override: `mat-form-field` (altura y borde del campo de búsqueda), `mat-table` + `mat-sort-header` (encabezado en caja normal, filetes internos), `mat-paginator` (botones cuadrados de 36 px), `mat-select` si el informe termina usando pestañas, y `mat-progress-bar` (barra de 6 px sin animación de brillo).
- La tabla de la maqueta fija la primera columna con `position: sticky` y dibuja su barra de desplazamiento. En Angular, `mat-table` necesita el contenedor con `overflow-x: auto` y la celda fija aplicada a `th` y `td` por separado.
- **Búsqueda de la tabla: filtrado en vivo sobre la API.** Hoy el campo de la maqueta es solo el control; el comportamiento pedido es el de un buscador que filtra mientras se escribe: cada tecla (con unos 250 a 300 ms de espera) dispara la consulta al backend con el texto, y la tabla se vuelve a pintar con el resultado, sin recargar la página ni volver a leer el Excel. Detalles que no se pueden perder: cancelar la petición anterior cuando llega una tecla nueva, reiniciar la paginación a la página 1 con cada búsqueda, y no filtrar en el cliente sobre las doce filas que están a la vista, porque el archivo tiene 715. El texto de ayuda bajo el campo lo dice: «La tabla se filtra mientras escribes».
- El campo de búsqueda es un solo rectángulo: el borde y el foco viven en el contenedor y la lupa va adentro, a la derecha. En Material eso es el `mat-form-field` con el icono como `matSuffix`.
- El paginador envuelve en varias líneas en pantallas angostas en lugar de recortarse. Con `mat-paginator` conviene el mismo criterio: `flex-wrap` y botones que no bajen de 36 px.
- El gráfico de horas es seleccionable y esa selección es estado del componente: un `<button>` por tramo con `aria-pressed`, el detalle debajo en una región `aria-live`, y el pico como valor inicial. Al portarlo, la selección no debe reiniciarse con cada refresco de datos, y los identificadores de incidente llevan `white-space: nowrap` para que no se corten en el guión.
- `prefers-reduced-motion` ya está contemplado: ninguna animación de esqueleto ni de transición corre si el sistema lo pide.
- El pie del documento es «Karen Gil, Analista SOC 2», sin la etiqueta «Pie del documento:» delante. La maqueta lo muestra al final de las dos versiones y en la tarjeta de descarga, para que no se pierda el requisito en ninguna de las dos salidas.
- El encabezado de la aplicación dice «Análisis SOC 2». Reemplaza a «Analizador SOC 2», que era más largo y no entraba en una línea al lado del logotipo. El pie lleva «Proyecto final DOJO-WoSEC» y los perfiles van montados sobre los dos iconos, sin la URL escrita, para que en el teléfono no queden dos líneas de texto largo.
