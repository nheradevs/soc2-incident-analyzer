# Brief de diseño: analizador SOC Nivel 2

Documento para trabajar el rediseño de la interfaz con otro agente. Recoge el estado actual del producto y las decisiones visuales y de redacción que debe respetar.

## 1. Qué es el producto

Aplicación web que recibe un archivo Excel exportado de un SIEM, analiza los registros de seguridad con reglas deterministas, clasifica el riesgo de cada hallazgo y genera un informe técnico en dos versiones, ejecutiva y técnica, exportable a PDF.

Escenario de uso: una consultora de ciberseguridad en Estocolmo recibe de un cliente el export de un grupo de incidentes, sin acceso a ninguna plataforma. Un analista SOC Nivel 2 tiene que explicar qué pasó, con qué evidencia y qué hacer al respecto.

El principio que ordena todo el producto: el motor de reglas decide los hallazgos, la interfaz los muestra y la IA, si está configurada, solo redacta. Cada afirmación del informe cita el identificador de la fila del Excel que la sostiene.

## 2. Las tres pantallas

| Ruta | Pantalla | Contenido |
| --- | --- | --- |
| `/cargar` | Carga y exploración | Zona de arrastre y selector de archivo, panel de calidad de datos, tabla paginada de eventos con búsqueda y ordenamiento |
| `/analisis` | Dashboard | Indicadores del análisis, gráficos, lista de incidentes ordenada por severidad y detalle de un incidente con sus filas de evidencia |
| `/informe` | Informe | Dos versiones del informe con sus nueve secciones, estado de la redacción asistida y descarga del PDF |

## 3. Flujo de datos que la interfaz debe reflejar

1. Carga del `.xlsx` y validación del contenido.
2. Normalización del export, que resuelve diez problemas del archivo de origen (entre ellos dos escrituras del mismo equipo y un identificador de evento que mezcla números con texto).
3. Diez detectores deterministas sobre los eventos normalizados.
4. Correlación de hallazgos en incidentes, que comparten cuenta o dirección IP de origen y ocurren en una ventana de treinta minutos.
5. Clasificación de cada hallazgo por impacto potencial y confianza en la evidencia.
6. Composición del informe en dos versiones.
7. Exportación a PDF.

Sobre el archivo real que acompaña al proyecto: 715 eventos, 12 columnas, una ventana de 5 horas y 58 minutos, seis incidentes, 46 hallazgos, cuatro de criticidad crítica y dos alta.

## 4. Tipografía

- Títulos: Poppins.
- Texto normal: una fuente que acompañe a Poppins, legible en tamaños pequeños y con buen rendimiento de lectura en pantalla.
- Jerarquía de encabezados correcta, sin saltos de nivel y con tamaños coherentes entre sí.
- Respetar los tamaños: no inflar títulos ni encoger el texto de lectura. El cuerpo de texto debe quedar cómodo, sin bajar de un tamaño legible en escritorio ni en móvil.

## 5. Voz y redacción

- Español neutro, con tratamiento de tú. No usar usted.
- Tono profesional y directo, sin lenguaje de ventas ni de marketing.
- Nada de términos exagerados ni superlativos.
- No inventar información ni métricas.
- No usar guiones largos ni rayas (—) en ningún texto de la interfaz ni en el PDF.
- No poner mayúscula después de dos puntos, salvo que siga un nombre propio.
- Respetar el uso de mayúsculas, del punto y seguido, del punto y aparte y del punto y coma.
- Evitar las construcciones que suenan a texto generado por una máquina.

## 6. Paleta

Seis colores, que deben respetarse y aplicarse de forma consistente:

| Color | Uso previsto |
| --- | --- |
| `#0E161B` | Fondo principal |
| `#162022` | Superficie de secciones |
| `#232E30` | Superficie de tarjetas |
| `#314048` | Bordes, separadores, estados intermedios |
| `#56666F` | Texto secundario, iconografía |
| Texto principal | Definir un tono claro de la misma familia, con contraste suficiente sobre las superficies |

La interfaz es oscura. La paleta no debe ampliarse con colores ajenos salvo los semánticos imprescindibles para criticidad, y aun así dentro de una lógica sobria.

## 7. Lo que no se debe usar

- Líneas en los bordes de la página o del contenedor principal.
- Efectos de vidrio esmerilado, desenfoques decorativos o transparencias de moda.
- Neón, resplandores o degradados llamativos.
- Etiquetas pequeñas en mayúsculas sobre los títulos, del tipo que se usa como adorno.
- Cualquier recurso visual que aparezca por costumbre y no por necesidad.

## 8. Estructura y componentes

- Cabecera que se desplaza con la página y se vuelve ligeramente transparente al hacer scroll.
- Pie de página con la autoría y los enlaces personales.
- El dashboard debe ordenarse por prioridad de lectura. Una distribución posible: indicadores del análisis a un lado y gráficos al otro, con el resto del contenido debajo. La decisión final queda a criterio del diseño, pero los gráficos deben ser claros y legibles, con etiquetas comprensibles, sin ruido visual y sin series inventadas.
- Diseño adaptable a móvil, tableta y escritorio.
- Buenas prácticas de accesibilidad: contraste suficiente, foco visible, etiquetas en los controles y atributos de estado para lectores de pantalla.

## 9. Marca y pies de página

- Logotipo en `logon.png`, en la raíz del repositorio. Todavía no está versionado.
- Favicon: una letra N blanca sobre fondo negro.
- Pie de página de la web: autoría de Karen Gil, enlace a `https://github.com/nheradevs` y a `https://www.linkedin.com/in/karen-gil-g/`.
- Pie de página del PDF: Karen Gil, Analista SOC 2. Hoy el PDF muestra "Consultora de ciberseguridad - Estocolmo" y debe pasar a mostrar la autoría.

## 10. Referencias visuales

- https://websitedemos.net/gardeners-services-02/?customize=template
- https://websitedemos.net/childcare-blog-02/?customize=template
- https://websitedemos.net/musical-instrument-maker-02/?customize=template

## 11. Restricciones funcionales que el rediseño no puede romper

- Los datos que muestra la interfaz provienen de la API y no se recalculan en el cliente.
- No existe un ranking de direcciones IP de origen como indicador de riesgo, porque en este export una dirección interna aparece como origen de diez equipos distintos. La interfaz no debe introducirlo.
- Los destinos externos sin volumen medido se muestran como "bytes no registrados", nunca como cero.
- El estado de la redacción asistida se informa en una línea y no debe presentarse como un informe incompleto.
- Las cuentas anónimas y de máquina se excluyen de los rankings y la interfaz declara cuáles excluyó y por qué.
- Cada hallazgo conserva la referencia a la fila del Excel que lo sostiene. Esa referencia se muestra al usuario.

## 12. Deuda visual del estado actual

- El texto de la interfaz y del PDF usa guiones largos en once lugares. Deben eliminarse.
- El tratamiento actual es de usted en varios mensajes. Debe pasar a tú.
- El PDF incluye como pie la línea de la consultora y no la autoría.
- El logotipo no está en el repositorio y la interfaz no lo usa.
- No hay captura del producto en el README del repositorio.
