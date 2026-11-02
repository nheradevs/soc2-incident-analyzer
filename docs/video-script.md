# Guion del video demostrativo (máximo 5 minutos)

**Entregable:** video de la carga del Excel al análisis y la generación del PDF.
**Regla de oro:** el video no demuestra que la app funciona. Demuestra que sabes qué mirar. Cada minuto tiene que mostrar una decisión, no un clic.

Los nombres de pantalla, botones y textos de este guion son los que la app muestra hoy. Si al grabar ves otro texto, cambió la interfaz y hay que ajustar el guion.

## Antes de grabar (5 minutos de preparación)

1. Terminal 1: `cd ~/Documents/soc2/backend && uv run uvicorn app.main:app --port 8000`
2. Terminal 2: `cd ~/Documents/soc2/frontend && nvm use && npm start`
3. Abre `http://localhost:4200` y deja el Excel a mano en el escritorio.
4. Cerrá notificaciones, pestañas y el chat. Fuente del navegador en 110 a 125 por ciento para que el texto se lea.
5. Ensayá una vez cronometrado. Si te pasás de 5 minutos, recorta el minuto 2 (dashboard). Nunca recortes el minuto 3 ni el cierre del PDF.

## 0:00 a 0:25 · Qué es esto

Pantalla de Cargar, sin tocar nada.

> "Soy analista SOC Nivel 2 en una consultora en Estocolmo. Un cliente nos exportó los logs de un grupo de incidentes en un Excel, sin darnos acceso a ninguna plataforma. Mi trabajo es decir qué pasó, con qué evidencia, y qué hacer. Construí esta aplicación para hacerlo de forma reproducible."

No expliques el stack todavía. A nadie que te entreviste le importa el framework en el minuto uno.

## 0:25 a 1:10 · Cargar y desconfiar del archivo

Arrastra el archivo `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`. Aparece la tabla de eventos y el panel de calidad de datos.

> "715 eventos, 12 columnas, casi 6 horas de un solo día. Antes de analizar nada, la app audita el archivo: encontró que DC-01 y DC01 son la misma máquina, y que el identificador de evento mezcla números con textos como PROXY_ACCESS. Si eso no se normaliza, un detector que busca el evento 4625 devuelve cero filas y el ataque desaparece en silencio."

Baja un poco y mostrá la búsqueda de la tabla escribiendo `PROXY_ACCESS`.

> "La búsqueda filtra contra el servidor mientras escribo, no en el navegador."

## 1:10 a 2:00 · Análisis: qué hay y qué no hay

Entra a Análisis. Muestra los indicadores, la serie por hora y el volumen saliente.

> "Seis incidentes. Cuatro críticos, dos altos. Y acá hay una decisión deliberada: no vas a encontrar un ranking de direcciones IP de origen. En este archivo una dirección interna aparece como origen de diez equipos distintos, así que rankearlas sería ruido disfrazado de inteligencia. Lo que sí ves es el volumen saliente agrupado solo por destino externo."

Señala el destino `203.0.113.88`.

> "Y fíjate en este: no lo dibujo como cero megabytes. Los registros no traen el tamaño, y no medido no es cero. Esa diferencia es la que después sostiene el informe."

Un gesto rápido al gráfico por hora: haz clic en dos tramos distintos.

> "El gráfico arranca en la hora con más eventos, las nueve de la mañana, y puedo cambiar el tramo."

## 2:00 a 3:05 · El hallazgo principal

Abre el incidente `INC-20261023-0902`. Baja por los hallazgos y abrí las filas de evidencia.

> "Esta es la cadena completa, en 20 minutos: cuatro intentos RDP desde una dirección externa, acceso exitoso como CORP\admin, asignación de privilegios, PowerShell con comando codificado, reconocimiento con net view, salto lateral a FS-SRV01 con origen APP-SRV01, acceso al recurso Finance, empaquetado con tar y conexión saliente a 203.0.113.88."

> "Ocho de las diez reglas dispararon sobre el mismo incidente. Y cada afirmación tiene su fila: EVT-00188 es el acceso, EVT-00225 el salto lateral. Podés abrir el Excel y verificarlo."

No leas todos los identificadores. Muestra dos y decí que están todos citados.

## 3:05 a 3:40 · El momento que te distingue

Abre el incidente `INC-20261023-0936`, el que figura con la marca de validación.

> "Este es el caso que más me importa mostrar. La cuenta backupsvc ejecuta vssadmin delete shadows, que es precursor clásico de ransomware, y lee 16 archivos financieros en cuatro minutos. Podría haberlo reportado como ransomware y el video habría sonado más grave."

> "Pero esa misma cuenta hace lecturas legítimas de Finanzas: 23 de los 64 accesos del archivo. Y vssadmin también lo usan herramientas de respaldo. Así que la app lo reporta como alto, requiere validación humana, y en el texto generado la palabra ransomware no aparece. Un falso positivo en un informe de seguridad cuesta más caro que un hallazgo no reportado, porque destruye la confianza en todo el resto del documento."

## 3:40 a 4:30 · El informe

Entra a Informe. Muestra el switch entre las dos versiones y recorré las nueve secciones de cada una.

> "El mismo análisis en dos versiones. La ejecutiva habla de impacto de negocio y plan de acción, sin una sola cita técnica. La técnica cita los identificadores de fila uno por uno. Nueve secciones en ambas: resumen, hallazgos, explicación técnica, evidencias, criticidad y justificación, impacto, plan de acción, recomendaciones y límites del análisis."

Señala la línea de estado de la redacción asistida.

> "Y acá: redacción asistida no configurada en esta instalación. El informe no está incompleto. Los hallazgos los decide un motor de reglas, no un modelo. La IA, si se configura, solo redacta, y su salida se descarta si cita una fila que no existe o si afirma una criticidad distinta a la del clasificador."

## 4:30 a 4:55 · El PDF

Descargá con el botón de la versión activa y abrí el archivo. Portada con clasificación, tabla de niveles, tabla de evidencia con identificadores, paginación.

> "17 páginas, generado en el servidor, con portada, clasificación general, las dos versiones y las tablas de evidencia. Este es el archivo que se entrega."

## 4:55 a 5:00 · Cierre

> "El código está en el repositorio, con 281 pruebas en el backend y 71 en el frontend. El motor decide, la IA redacta, y cada conclusión se puede verificar contra una fila del Excel."

## Errores que arruinan el video

| Error | Por qué duele |
| --- | --- |
| Mostrar el código fuente | Cinco minutos no alcanzan y no demuestra criterio analítico |
| Decir el stack en el minuto uno | A nadie que te entreviste le importa el framework antes del problema |
| Inventar un número en vivo | Todo lo que digas tiene que estar en pantalla o en el PDF |
| Saltear el caso ambiguo | Es la sección que prueba que sabes distinguir un indicador de una conclusión |
| Grabar sin ensayar | Te quedás sin tiempo justo en el PDF |
| Audio con eco o ventilador | Un video con mal audio se percibe como descuido aunque el trabajo sea bueno |

## Checklist antes de subir

- [ ] El video no pasa de 5:00. La duración es requisito.
- [ ] Se ve el nombre del archivo `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`.
- [ ] Se ve al menos un identificador de fila en pantalla y el mismo en el PDF.
- [ ] Se ve la portada del PDF abierta, no sólo el botón de descarga.
- [ ] Se escucha la frase sobre por qué no hay ranking de direcciones IP.
- [ ] Se escucha la frase sobre por qué backupsvc no se reporta como ransomware.
- [ ] El PDF subido al formulario es el mismo que se ve en el video.
