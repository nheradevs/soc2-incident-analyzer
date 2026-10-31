# Guion del video demostrativo (máximo 5 minutos)

**Entregable:** video de la carga del Excel al análisis y la generación del PDF.
**Regla de oro:** el video no demuestra que la app funciona — demuestra **que vos sabés qué mirar**. Cada minuto tiene que mostrar una decisión, no un clic.

---

## Antes de grabar (5 minutos de preparación)

1. Terminal 1: `cd backend && uv run uvicorn app.main:app --port 8000`
2. Terminal 2: `cd frontend && npm start`
3. Abrí `http://localhost:4200` y dejá el Excel a mano en el escritorio.
4. Cerrá notificaciones, pestañas y el chat. Fuente del navegador en 110–125 % para que el texto se lea en el video.
5. Ensayá **una vez** cronometrado. Si te pasás de 5 minutos, recortá la sección 3 (dashboard), nunca la 5 (caso ambiguo) ni la 7 (PDF).

---

## 0:00 – 0:25 · Qué es esto

> "Soy analista SOC Nivel 2 en una consultora en Estocolmo. Un cliente nos exportó los logs de un grupo de incidentes en un Excel, sin darnos acceso a ninguna plataforma. Mi trabajo es decir qué pasó, con qué evidencia, y qué hacer. Construí esta aplicación para hacerlo de forma reproducible."

No expliques el stack todavía. Nadie contrata un stack.

---

## 0:25 – 1:10 · Cargar y desconfiar del archivo

**Mostrá:** arrastrar `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`, la tabla de eventos y **el panel de calidad de datos**.

> "715 eventos, 12 columnas, casi 6 horas de un solo día. Antes de analizar nada, la app audita el archivo: encontró que `DC-01` y `DC01` son la misma máquina —91 y 30 eventos—, y que `Event_ID` mezcla números con textos como `PROXY_ACCESS`. Si eso no se normaliza, un detector que busca el evento 4625 devuelve cero filas y el ataque desaparece en silencio."

**Este es el primer diferenciador:** el 90 % de los proyectos de este tipo se comen un `NaN` y reportan "no se encontraron incidentes".

---

## 1:10 – 2:00 · Dashboard: qué hay y qué no hay

**Mostrá:** KPIs, serie horaria, gráfico de salida por destino externo, lista de incidentes.

> "Seis incidentes: cuatro críticos, dos altos. Y acá hay una decisión deliberada: no vas a encontrar un ranking de IPs de origen. En este archivo una IP interna aparece como origen de diez equipos distintos, así que rankearlas sería ruido disfrazado de inteligencia. Lo que sí ves es el volumen saliente agrupado sólo por destino externo."

> "Y fijate en este destino: `203.0.113.88`. No lo dibujo como cero megabytes: los registros no traen el tamaño, y 'no medido' no es 'cero'. Esa diferencia es la que después sostiene el informe."

---

## 2:00 – 3:05 · El hallazgo principal

**Mostrá:** drill-down de `INC-20261023-0902`, scrolleá los hallazgos y abrí las filas de evidencia.

> "Esta es la cadena completa, en 20 minutos: cuatro intentos RDP desde una IP externa, acceso exitoso como `CORP\admin`, asignación de privilegios, PowerShell con comando codificado, reconocimiento con `net view`, salto lateral a `FS-SRV01` con origen `APP-SRV01`, acceso al recurso `Finance`, empaquetado con `tar` y conexión saliente a `203.0.113.88`."

> "Ocho de las diez reglas dispararon sobre el mismo incidente. Y cada afirmación tiene su fila: `EVT-00188` es el logon, `EVT-00225` el salto lateral. Podés abrir el Excel y verificarlo."

**No leas todos los `Log_ID`.** Mostrá dos y decí que están todos citados.

---

## 3:05 – 3:40 · El momento que te distingue

**Mostrá:** el incidente `INC-20261023-0936`, nivel **alto** con la marca de validación.

> "Este es el caso que más me importa mostrar. La cuenta `backupsvc` ejecuta `vssadmin delete shadows` —que es precursor clásico de ransomware— y lee 16 archivos financieros en cuatro minutos. Podría haber escrito 'ransomware' y quedar como un campeón."

> "Pero esa misma cuenta hace lecturas legítimas de Finanzas: 23 de los 64 accesos del archivo. Y `vssadmin` también lo usan herramientas de backup. Así que la app lo reporta como **alto, requiere validación humana**, y en el texto generado la palabra ransomware no aparece. Un falso positivo en un informe de seguridad cuesta más caro que un hallazgo no reportado, porque destruye la confianza en todo el resto del documento."

**Si el profesor se lleva una sola cosa, que sea esta.**

---

## 3:40 – 4:30 · El informe

**Mostrá:** la pantalla de informe, cambiá entre ejecutivo y técnico, mostrá las nueve secciones.

> "El mismo análisis en dos versiones. La ejecutiva habla de impacto de negocio y plan de acción, sin una sola cita técnica. La técnica cita los `Log_ID` uno por uno. Nueve secciones en ambas: resumen, hallazgos, explicación técnica, evidencias, criticidad y justificación, impacto, plan de acción —investigar, contener, remediar—, recomendaciones y limitaciones."

**Mostrá la línea de estado:**
> "Y acá: 'Redacción asistida: no configurada en esta instalación'. El informe no está incompleto. Los hallazgos los decide un motor de reglas, no un modelo. La IA, si se configura, sólo redacta — y su salida se descarta si cita un `Log_ID` que no existe o si afirma una severidad distinta a la del clasificador."

---

## 4:30 – 4:55 · El PDF

**Mostrá:** descargar y abrir el PDF. Portada con clasificación, tabla de niveles, tabla de evidencia con `Log_ID`, paginación.

> "17 páginas, generado en el servidor con ReportLab, con portada, clasificación general, las dos versiones y las tablas de evidencia. Este es el archivo que se entrega."

---

## 4:55 – 5:00 · Cierre

> "El código está en el repo, con 280 tests en el backend y 66 en el frontend. El motor decide; la IA redacta; y cada conclusión se puede verificar contra una fila del Excel."

---

## Errores que arruinan el video (evitalos)

| Error | Por qué duele |
|---|---|
| Mostrar el código fuente | 5 minutos no alcanzan y no demuestra criterio analítico |
| Decir "usa Angular 20, FastAPI y ReportLab" en el minuto 1 | Nadie contrata frameworks; contratan juicio |
| Inventar un número en vivo | Todo lo que digas tiene que estar en pantalla o en el PDF |
| Saltear el caso ambiguo (3:05) | Es la sección que prueba que sabés distinguir un indicador de una conclusión |
| Grabar sin ensayar | Te vas a quedar sin tiempo justo en el PDF |
| Audio con eco o ventilador | Un video con mal audio se percibe como descuido, aunque el trabajo sea bueno |

---

## Checklist final antes de subir

- [ ] Video ≤ 5:00 (cortá si te pasás: la duración es requisito)
- [ ] Se ve el nombre del archivo `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`
- [ ] Se ve al menos un `Log_ID` en pantalla y el mismo en el PDF
- [ ] Se ve la portada del PDF abierta, no sólo el botón de descarga
- [ ] Se escucha la frase sobre por qué no hay ranking de IPs
- [ ] Se escucha la frase sobre por qué `backupsvc` no se reporta como ransomware
- [ ] El PDF subido al formulario es el **mismo** que se ve en el video
