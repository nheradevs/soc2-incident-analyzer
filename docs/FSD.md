# FSD — Aplicación de Análisis de Incidentes SOC Nivel 2

**Proyecto final — Bootcamp Analista SOC Nivel 2**
**Versión:** 0.2 (esquema real validado contra el archivo de entrada)
**Fecha:** 2025-11
**Cambio respecto de 0.1:** el archivo `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx` ya está en el repo y fue perfilado. Este documento reemplaza los supuestos sobre el esquema por hechos medidos: estructura real (§3), trampas de datos que obligan a una capa de normalización (§4), umbrales de detección derivados de la línea base real (§6) e incidentes de referencia para aceptación (§8).

---

## 1. Visión general

Aplicación web que importa un archivo Excel exportado de un SIEM (`SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`), ejecuta un motor de detección determinístico sobre los logs, correlaciona eventos y produce un informe técnico de incidentes en español — en versión ejecutiva y técnica — exportable a PDF. La IA (nan.builders, API OpenAI-compatible) apoya la redacción, pero **nunca decide hallazgos**: toda conclusión se sustenta en evidencia citada de los logs.

**Escenario:** consultora de ciberseguridad en Estocolmo; el cliente exportó los logs de un grupo de incidentes y el analista SOC N2 debe identificar qué pasó sin acceso a plataformas.

**Realidad del dato de entrada (medida, no supuesta):** 715 filas × 12 columnas, una sola hoja (`SIEM Export`), 44 KB, ventana de **5 h 58 min de un solo día** (2026-10-23 07:46:07 → 13:44:06). El archivo es de origen sintético y sus IPs externas pertenecen a rangos de documentación RFC 5737 — ver §4.9.

---

## 2. Alcance

### Incluye
1. Carga y visualización del Excel (.xlsx)
2. Análisis de seguridad: detección y correlación de 6 categorías de eventos
3. Dashboard con estadísticas y gráficos interactivos por criticidad
4. Clasificación de riesgos (crítico/alto/medio/bajo) con justificación
5. Informe técnico en 2 versiones (ejecutiva y técnica), en español
6. Exportación del informe a PDF
7. IA integrada para redacción asistida
8. Medidas de seguridad básicas de la aplicación
9. Declaración explícita de limitaciones del análisis (§7.4)

### Excluye
- Integración con Microsoft Sentinel o cualquier plataforma SIEM
- Ingesta en tiempo real / streaming de logs
- Autenticación multiusuario con roles (app de demo de un solo usuario)
- Deployment a producción (corre en local para el demo)
- Enriquecimiento con Threat Intelligence externa (las IPs son de documentación; ver §4.9)

---

## 3. Esquema real del archivo de entrada

Hoja única `SIEM Export`. Encabezado en la fila 1. Filas ordenadas por `Timestamp` ascendente.

| Columna | Tipo observado | Nulos | Contenido / forma real |
|---|---|---|---|
| `Log_ID` | str | 0 | `EVT-00001` … `EVT-00715`, secuencial y correlativo al orden temporal. Es la **clave de evidencia** que cita el informe. |
| `Timestamp` | str | 0 | `YYYY-MM-DD HH:MM:SS`. Se lee como `object`; 17 timestamps duplicados. Zona horaria no declarada. |
| `Hostname` | str | 0 | 11 valores; incluye `DC-01` y `DC01` para la misma máquina (§4.4). |
| `Event_ID` | int **y** str | 0 | Mayoría numéricos (`4624`, `4625`, `4688`…); también `PROXY_ACCESS` y `HTTP_ACCESS` como texto (§4.1). |
| `User` | str | 0 | `CORP\<usuario>`; valores especiales `-` e `IIS APPPOOL\DefaultAppPool` (§4.5). |
| `Source_IP` | str | 0 | 7 IPs internas `10.10.x.x` + 3 externas (`203.0.113.74`, `192.0.2.91`, `198.51.100.77`). No mapea a host (§4.8). |
| `Destination` | str | **262** | Mezcla hostname (`DC-01`), `host:port` (`WEB-01:443`), IP:puerto (`203.0.113.88:443`) y UNC (`\\FS-SRV01\Finance`) (§4.6). |
| `Log_Source` | str | 0 | `Security` 615, `System` 55, `Proxy` 22, `IIS` 21, `PowerShell` 1, `Firewall` 1. |
| `Event_Description` | str | 0 | Texto libre. **Transporta el dato semántico**: `LogonType=10`, `source=APP-SRV01`, `TaskName=…`, `ServiceName=…` (§4.7). |
| `Process_CommandLine` | str | **560** | Línea de comandos, rutas de archivo, nombres de proceso; en Proxy transporta `bytes_out=N uri=/…` (§4.7). |
| `Result` | str | 0 | Semántica por fuente: `Success`/`Failure` (Security), `200`/`404`/`500` (IIS), `Allowed` (Proxy) (§4.3). |
| `Severity` | str | 0 | `Informational` 603, `Warning` 97, `High` 8, `Medium` 7. **Incoherente como clasificación de riesgo** (§4.10). |

**Distribución de `Event_ID` (hecho medido):**

| Event_ID | n | Significado |
|---|---|---|
| 4624 | 111 | Logon exitoso |
| 4625 | 102 | Logon fallido (64 genéricos, 33 `bad password`, 4 RDP, 1 LogonType=3) |
| 4634 | 94 | Logoff |
| 4688 | 92 | Creación de proceso |
| 5140 | 74 | Acceso a recurso compartido |
| 5156 | 67 | Conexión permitida por WFP |
| 4663 | 64 | Acceso a objeto |
| 7036 | 55 | Servicio en ejecución |
| `PROXY_ACCESS` | 22 | HTTPS POST saliente |
| `HTTP_ACCESS` | 21 | Request HTTP en IIS |
| 4672 | 8 | Privilegios especiales asignados |
| 5145 | 2 | Chequeo de acceso a share |
| 4104 | 1 | Script block de PowerShell |
| 4698 | 1 | Tarea programada creada |
| 7045 | 1 | Servicio instalado |

---

## 4. Trampas conocidas y normalización obligatoria

Estas nueve condiciones **no son opcionales**: cada una, ignorada, produce detecciones perdidas en silencio o falsos positivos. Se implementan en una capa previa a los detectores (§9, `ingest/normalize.py` y `ingest/parse.py`), no dentro de cada detector.

| # | Trampa | Efecto si se ignora | Normalización exigida |
|---|---|---|---|
| 4.1 | `Event_ID` mezcla `int` y `str` | Un filtro `Event_ID == 4625` con el tipo mal normalizado devuelve 0 filas y se pierde el ataque | `event_id_norm: str` siempre (`str(x).strip()`), + `event_family: windows\|proxy\|web` |
| 4.2 | `Timestamp` llega como `object` | Correlación temporal rota o comparación lexicográfica | Parseo explícito a `datetime64`; descartar/aislar filas no parseables |
| 4.3 | `Result` cambia de semántica por fuente | `Result == "Failure"` no ve nada de IIS ni Proxy; el web shell (`200`) y el `500` quedan invisibles | `result_norm` unificado: `success\|failure\|http_2xx\|http_4xx\|http_5xx\|allowed` |
| 4.4 | `DC-01` (91 filas) y `DC01` (30) son el mismo host | Top-hosts partido y correlación rota entre 08:39 y 10:25 | `host_norm`: mayúsculas, sin guiones/espacios, alias por tabla de equivalencias |
| 4.5 | `User` incluye `-` (21 filas IIS) y `IIS APPPOOL\DefaultAppPool` | Infla métricas de personas y contamina "top usuarios" | `user_norm` sin dominio + `principal_type: human\|machine\|anonymous\|unknown` |
| 4.6 | `Destination` mezcla host, `host:port`, `ip:port` y UNC, con 262 nulos | No es una entidad consultable; el dashboard agrupa de forma incoherente | `dest_type: host\|endpoint\|share\|none` + `dest_host`, `dest_port` |
| 4.7 | **El dato semántico está en texto libre** (`Event_Description`, `Process_CommandLine`) | No hay columnas para logon type, host de origen, share, tarea, servicio, bytes ni URI | `parse.py` extrae con regex: `logon_type`, `lateral_source`, `share`, `file_path`, `task_name`, `service_name`, `image_path`, `bytes_out`, `uri`; cada valor conserva el `Log_ID` de origen |
| 4.8 | `Source_IP` **no mapea a host** (`10.10.2.15` aparece como origen de 10 hosts distintos) | "Top IPs" es ruido y el salto lateral no se puede inferir por IP | `ip_class: internal\|external` (RFC1918 vs resto). La relación host↔IP solo se toma del texto (`source=…`) o de `Destination`; nunca se infiere |
| 4.9 | Las 3 IPs externas (`203.0.113.x`, `192.0.2.x`, `198.51.100.x`) son **rangos RFC 5737 de documentación** | Cualquier afirmación de atribución geográfica o de reputación sería inventada | Clasificar y declarar en el informe como limitación (§7.4): datos sintéticos, sin TI real |
| 4.10 | La `Severity` del propio SIEM es incoherente | `4672` desde IP externa = `Informational`; 33 fallos de spray = `Warning`; 4 fallos RDP = `Medium` | La criticidad **se calcula** (RF3). La columna del SIEM se muestra como dato de origen y se marca como no confiable |

---

## 5. Requisitos funcionales

### RF1 — Carga de archivos
- El usuario sube un archivo `.xlsx` desde la interfaz (drag & drop + selector).
- Validación: extensión `.xlsx`, tamaño máximo configurable (default 50 MB), rechazo con mensaje claro de otro formato.
- El backend parsea con pandas/openpyxl y devuelve: esquema detectado (columnas), total de filas, rango temporal de los eventos y **reporte de calidad de datos** (nulos por columna, hosts duplicados detectados, tipos mixtos en `Event_ID`).
- Vista de tabla paginada con búsqueda y ordenamiento; cada fila muestra los campos del log y resalta las filas que son evidencia de un hallazgo.
- El archivo analizado queda en sesión; se puede reemplazar cargando otro.

### RF2 — Análisis de seguridad (motor de detección)
Motor **determinístico por reglas** sobre el DataFrame normalizado; cada detector produce hallazgos con evidencia (`Log_ID` de las filas que los sustentan). Los umbrales de la tabla **se derivan de la línea base medida** en el archivo real (§6), no de valores arbitrarios.

| # | Detector | Regla concreta |
|---|---|---|
| D1a | Fuerza bruta dirigida | ≥3 `4625` sobre la **misma cuenta** en ventana de 10 min |
| D1b | Password spray | ≥5 `4625` desde la **misma IP externa** contra ≥3 cuentas distintas en 15 min |
| D1c | Exposición externa | Cualquier `4625` con `ip_class=external` eleva severidad, **aunque el conteo sea bajo** |
| D1d | Compromiso posterior | `4624` exitoso en ≤15 min desde la misma IP/cuenta que un bloque D1a/D1b → escalar a crítico |
| D2 | Inicios sospechosos | `4624` con IP externa; `4624` sobre cuentas privilegiadas; `4624` fuera de horario hábil (ciego con este archivo — §7.4) |
| D3 | Escalamiento | `4672` **correlacionado** con origen externo o con un `4625→4624` previo de la misma IP/cuenta. Un `4672` interno aislado es línea base y **no** genera hallazgo |
| D4 | Comandos y procesos | Lista negra sobre `Process_CommandLine`: `-enc`/`-EncodedCommand`, `vssadmin delete shadows`, `net.exe view`, `whoami`, archivos comprimidos (`7z`/`tar`) con destino en `C:\Users\Public` o `C:\Temp`, ejecución desde `C:\ProgramData`, y **proceso interactivo con padre `IIS APPPOOL\*`** |
| D5 | Movimiento lateral | `4624` LogonType=3/10 donde `lateral_source` ≠ host destino, seguido de `5140`/`5145`/`4663` en ≤10 min sobre el host destino |
| D6 | Otras anomalías | Rareza de frecuencia (`Event_Description` con `n=1`); lectura secuencial masiva de `4663` (>10 objetos en <5 min por usuario); `bytes_out` acumulado por destino externo; `4698`/`7045` fuera de ventana de mantenimiento |
| D7 | Exfiltración | Proxy con `bytes_out` acumulado ≥50 MB hacia una IP externa en ≤15 min, o ≥10 POST consecutivos al mismo destino |

- **Correlación:** los hallazgos individuales se agrupan en *incidentes* cuando comparten entidades normalizadas (usuario, host, IP) y una ventana temporal de **≤30 min** (la ventana total del archivo es de 6 h, así que ventanas de días serían inútiles).
- Cada hallazgo incluye: tipo, severidad propuesta, entidades involucradas, conteo, primera/última ocurrencia, **referencias a los `Log_ID` de evidencia** y `requires_validation: bool` para los casos ambiguos (ver §8, INC-6).
- Límite de rigor (S8): el motor solo afirma lo que los logs muestran; si el esquema no permite detectar algo, se declara en el informe como limitación.

### RF3 — Clasificación de riesgos
- Cada hallazgo/incidente recibe criticidad **crítico / alto / medio / bajo** según matriz: impacto potencial × confianza de la evidencia.
- La justificación es texto generado por reglas (plantilla con datos del hallazgo), no por IA — trazable y auditable.
- El dashboard, el informe y el PDF usan esta misma clasificación (fuente única de verdad).
- La `Severity` del SIEM **no** se usa como insumo de la matriz; se muestra aparte como dato de origen (§4.10).

### RF4 — Dashboard
- KPIs: total de eventos, incidentes por criticidad, usuarios/hosts afectados, ventana temporal, cobertura de detección por categoría.
- Gráficos interactivos (Chart.js): eventos por tiempo, distribución por criticidad, top hosts, top usuarios humanos, tipos de ataque detectados, volumen saliente por destino externo.
- **No** se muestra "top IPs de origen" como indicador de riesgo: en este archivo no es informativo (§4.8). Se muestra sí como "origen externo vs interno".
- Lista de incidentes con drill-down: clic → detalle del hallazgo con su evidencia (`Log_ID`).

### RF5 — Informe técnico (IA + reglas)
Dos versiones en español, mismo contenido estructural:
1. **Ejecutiva:** lenguaje no técnico, foco en impacto de negocio y plan de acción.
2. **Técnica:** detalle por hallazgo, evidencias citadas (`Log_ID`), recomendaciones específicas.

Estructura obligatoria:
1. Resumen ejecutivo
2. Hallazgos identificados
3. Explicación técnica de cada hallazgo
4. Evidencias encontradas en los logs
5. Criticidad y justificación
6. Posible impacto en la organización
7. Plan de acción: investigar → contener → remediar
8. Recomendaciones generales de seguridad
9. **Limitaciones del análisis** (§7.4) — obligatoria, no opcional

**Guardarraíl anti-alucinación:** el backend arma un *brief* estructurado con los hallazgos ya validados + muestras de evidencia y pide al LLM que **redacte**, no que analice. El texto del LLM se valida: los `Log_ID` citados deben existir y corresponder a la evidencia del hallazgo que se está redactando; si no, se descarta y se usa la plantilla determinística.

### RF6 — Exportación PDF
- Generación server-side con ReportLab/WeasyPrint a partir del contenido estructurado del informe (no screenshot del HTML).
- Incluye portada (título, cliente, fecha, clasificación), tablas de hallazgos, las dos versiones y las limitaciones.
- Descarga directa desde la UI.

### RF7 — IA integrada (nan.builders)
- Proveedor: API OpenAI-compatible `https://api.nan.builders/v1`, modelo configurable (default `deepseek-v4-flash`), key en variable de entorno `NAN_API_KEY` (nunca en el repo ni en el cliente).
- Generación de informes con `stream: true` (sin streaming el gateway corta a 120 s con 524).
- `reasoning_effort` configurable; el informe usa valor bajo/medio para latencia razonable.
- Manejo de errores: si la IA no responde, el informe se genera igual con la plantilla determinística y se marca como "sin narrativa IA".

### RF8 — Seguridad de la aplicación
- Upload: validación de tipo MIME + extensión + tamaño; archivo procesado en memoria/temporal con limpieza.
- API key solo en backend; el frontend nunca ve credenciales.
- Sanitización: el contenido del Excel y la salida del LLM se renderizan como texto, nunca como HTML crudo (los logs contienen HTML/URI embebidos).
- CORS restringido a `http://localhost:4200`.
- Límite de tasa básico en endpoints de IA y exportación.
- `.env` en `.gitignore`; `.env.example` documentado en el repo.

---

## 6. Línea base medida y umbrales justificados

Medición sobre los 715 registros reales. La columna "línea base" es lo que el archivo muestra como comportamiento normal; el umbral se elige para no disparar sobre ella.

| Señal | Línea base observada | Umbral elegido | Margen |
|---|---|---|---|
| Fallos `4625` genéricos por usuario | **máximo 2** en cualquier ventana de 10 min (64 filas repartidas en 10 usuarios) | ≥3 en 10 min | Cero falsos positivos sobre la línea base |
| Fallos por `Source_IP` externa | 0 en la línea base (todo el tráfico normal es `10.10.x.x`) | ≥1 con `ip_class=external` | El discriminador es la externalidad, no el conteo |
| Amplitud de cuentas atacadas | 0 desde una sola IP externa | ≥3 cuentas distintas en 15 min | Separar spray de brute force dirigido |
| Privilegios especiales `4672` | 7 de 8 son internos y legítimos | Solo si hay origen externo o `4625→4624` previo | Evita 7 falsos positivos |
| Volumen saliente a IP externa | 0 en la línea base | ≥50 MB en 15 min o ≥10 POST al mismo destino | El INC-4 da 253,3 MB en 22 POST |
| Acceso secuencial a archivos `4663` | lecturas dispersas de `backupsvc` (23 filas legítimas) | >10 objetos con cadencia regular <5 min **+** `requires_validation` | Calibrado para no acusar al backup legítimo |
| Ventana de correlación | archivo completo = 5 h 58 min | ≤30 min entre eventos correlacionados | Suficiente para INC-1 (14 min) e INC-2 (20 min) |

**Nota de calibración importante:** el ataque de fuerza bruta RDP de INC-2 tiene **solo 4 intentos a 60 s**. Una regla de brute force basada puramente en conteo (`≥5`) lo **pierde**. El discriminador correcto es *origen externo + LogonType=10*, por eso D1c existe separado de D1a.

---

## 7. Requisitos no funcionales

- **Rendimiento:** importar y analizar el archivo real (715 filas) en **< 3 s**. Para sostener una afirmación de escala se genera un fixture sintético de ≥50k filas derivado del esquema real, marcado como sintético y **no** usado en el informe entregable; con ese fixture, análisis < 30 s. La afirmación de "100k filas" de la v0.1 se retira por no ser verificable con el archivo del cliente.
- **Usabilidad:** interfaz moderna (Angular Material), flujo guiado en pasos: Cargar → Analizar → Dashboard → Informe → PDF.
- **Idioma:** UI e informes en español; código, commits y comentarios en inglés.
- **Portabilidad:** corre en local con `docker compose up` o dos terminales (uvicorn + ng serve).
- **Mantenibilidad:** detectores como módulos independientes y testeables; sin lógica de negocio en el frontend.

### 7.4 Limitaciones obligatorias del análisis (se listan siempre en el informe, se ajustan según lo detectado):
  1. Ventana de datos de 5 h 58 min de un único día: no permite establecer recurrencia, persistencia histórica ni tendencia.
  2. Sin acceso a plataformas (SIEM/EDR/DNS/netflow): el análisis se limita a los campos exportados.
  3. Payloads ofuscados redactados en el origen (`[REDACTED_SYNTHETIC]`, `<base64_redacted>`): **no es posible determinar qué ejecutaba el comando codificado ni cuál era el canal C2**.
  4. `Source_IP` no resuelve a hostname; la relación origen↔destino se toma del texto del evento cuando está disponible.
  5. IPs externas en rangos de documentación (RFC 5737): sin atribución geográfica ni reputación real (sin TI).
  6. La columna `Severity` del SIEM es inconsistente y no se usa para clasificar.
  7. La ausencia de un hallazgo no prueba ausencia de compromiso: solo indica que no hay evidencia en este export.
  8. El export **no declara el tipo de cuenta**. Las cuentas de servicio se identifican por convención de nombre, no por un atributo del dato: `CORP\svc_backup` se clasifica como humana y por lo tanto aparece en el ranking de cuentas. El dashboard declara qué cuentas excluye y por qué (anónimas y de máquina), pero no puede afirmar cuáles son de servicio sin un atributo que lo respalde.

---

## 8. Verdad de referencia: los incidentes presentes en el archivo

Seis clústeres distintos, verificados por lectura directa. Sirven como **caso de aceptación** (§12) y como fixture de regresión del motor. Todos los números y `Log_ID` son citables en el informe.

### INC-1 · Password spray → acceso exitoso → privilegios — `203.0.113.74` → `DC-01`
33 fallos `4625 bad password` sobre 8 cuentas distintas, cadencia exacta de **19 s**, 08:25:00 → 08:35:08 (`EVT-00057` … `EVT-00111`). Acceso exitoso `EVT-00123` (08:39, `4624`, `CORP\mgarcia` en `DC-01`) y `EVT-00126` (08:40, `4672` en `WS-031`).
**Categorías:** fuerza bruta (variante spray), inicio sospechoso, escalamiento.

### INC-2 · Kill chain completa vía RDP — `198.51.100.77` → `APP-SRV01` → `FS-SRV01`
`EVT-00174/175/178/180` (09:02–09:05, `4625` LogonType=10) → `EVT-00188` (09:06, `4624` RDP como `CORP\admin`) → `EVT-00193` (`4672`) → `EVT-00198` (`powershell.exe -NoProfile -EncodedCommand`, parent `cmd.exe`) → `EVT-00207` (`4104`: `Get-LocalGroupMember Administrators; Get-SmbShare`) → `EVT-00214` (`net.exe view \\FS-SRV01`) → `EVT-00225` (09:16, `4624` LogonType=3 con `source=APP-SRV01` — **movimiento lateral**) → `EVT-00227` (share `\Finance`) → `EVT-00231` (`Finance\Budget2027.xlsx`) → `EVT-00232` (`tar.exe -a -c -f C:\Temp\finance.zip C:\Temp\reports`) → `EVT-00235` (09:21, conexión saliente a `203.0.113.88:443` con `powershell.exe`).
**20 min, 13 eventos. Cubre las 6 categorías requeridas.** Es el hallazgo principal del informe.

### INC-3 · Web shell / explotación de aplicación web — `192.0.2.91` → `WEB-01`
`EVT-00571` (12:10, `200` en `/uploads/test.aspx?cmd=whoami` — **ejecución exitosa**) → 20 requests a `/login?user=admin`, `/admin/` (`500`), `/api/v1/export` (`200`) hasta `EVT-00596` (12:14) → `EVT-00599` (12:15, `4688`: `cmd.exe /c whoami` lanzado por `IIS APPPOOL\DefaultAppPool`).
**Categorías:** comandos y procesos, otras anomalías. La ejecución exitosa del web shell es el hallazgo de mayor criticidad de este clúster.

### INC-4 · Exfiltración vía proxy — `WS-018` · `CORP\rrojas`
`EVT-00428` (10:42, `7z.exe a C:\Users\Public\archive.7z C:\Legal\*.docx` — staging) → 22 `PROXY_ACCESS` HTTPS POST a `198.51.100.88:443`, 10:43:00 → 10:49:18, **253,3 MB** totales (5,8–17,3 MB por request), URI `/upload/session/1…22`.
**Categorías:** otras anomalías / exfiltración.

### INC-5 · Persistencia con masquerading — `APP-SRV01` · `CORP\helpdesk`
`EVT-00523` (11:37, `4698`: tarea `\Microsoft\Windows\UpdateCheck` → `powershell.exe -File C:\ProgramData\updatecheck.ps1`) → `EVT-00524` (11:38, `7045`: servicio `WinUpdateHelper` → `C:\ProgramData\wuhelper.exe`) → 5 ejecuciones posteriores (`EVT-00528/542/548/559/564`, cada 6 min).
**Categorías:** otras anomalías (persistencia), comandos y procesos. Nota: `helpdesk` es cuenta de soporte, no administrador de sistemas — el hallazgo debe indicar el desvío de rol.

### INC-6 · Cuenta de servicio sospechosa — `WS-023` + `FS-SRV01` · `CORP\backupsvc` (**caso ambiguo, `requires_validation`**)
`EVT-00280` (09:36, PowerShell `-EncodedCommand`) → 16× `4663` sobre `Finance\FY2026\document_000..015.xlsx` cada 16 s (09:37:00 → 09:41:00, `EVT-00284…00309`) → `EVT-00314` (09:42, `vssadmin.exe delete shadows /all /quiet`).
**Ambigüedad que el informe debe declarar:** `backupsvc` también realiza lecturas legítimas de `Finance` (23 de los 64 eventos `4663`). Un detector naíf de "acceso masivo = exfiltración" produce un falso positivo, y `vssadmin delete shadows` es precursor de ransomware **pero también** lo usan herramientas de backup. Se reporta como **crítico/requiere validación**, no como ransomware confirmado. Este caso es el que demuestra el criterio de rigor (S8).

---

## 9. Arquitectura

```
frontend/  Angular 17+ + Angular Material + Chart.js
   │  HTTP (JSON)
   ▼
backend/   FastAPI (Python 3.10+)
   ├─ ingest      → pandas + openpyxl; detecta hoja, esquema, calidad de datos
   │   ├─ normalize.py → Event_ID str, timestamp datetime, host canónico, user/principal,
   │   │                 dest_type, ip_class (RFC1918 vs externa), result_norm
   │   └─ parse.py     → extrae del texto libre: logon_type, lateral_source, share,
   │                     file_path, task_name, service_name, image_path, bytes_out, uri
   ├─ detection   → detectores D1a-D7 + correlador (reglas puras, testeables)
   ├─ risk        → matriz de criticidad + justificación por plantilla
   ├─ narrative   → cliente OpenAI-compatible → nan.builders (streaming)
   ├─ reporting   → ensambla informe (ejecutivo/técnico + limitaciones) en estructura
   └─ export      → ReportLab/WeasyPrint → PDF
```

**Contrato API (borrador):**

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/upload` | POST | Sube el .xlsx, devuelve esquema + stats + reporte de calidad de datos |
| `/api/analyze` | POST | Corre detectores + clasificación sobre el frame cargado y devuelve el payload del dashboard: cobertura, distribución por criticidad, serie horaria, top hosts, cuentas humanas (con exclusiones declaradas), salida por destino externo, tipos de ataque y lista de incidentes ordenada por severidad |
| `/api/events` | GET | Eventos paginados (tabla), filtrable por `Log_ID` |
| `/api/incidents/{incident_id}` | GET | Drill-down de un incidente: clasificación, hallazgos con su justificación y las **filas reales** del export citadas como evidencia (unidas por `Log_ID`, 36 columnas) |
| `/api/report` | POST | Genera informe (SSE con progreso, streaming IA) |
| `/api/report/pdf` | GET | Descarga el PDF |

**Estado:** sin base de datos — el DataFrame analizado vive en memoria por sesión (suficiente para demo; sesión = proceso único).

---

## 10. Plan de trabajo

El bloqueante de la v0.1 ("se necesita el archivo real") **está resuelto**: el archivo está en el repo y el esquema está documentado en §3. F1 y F2 quedan desbloqueadas.

| Fase | Tarea | Entregable | Estimado |
|---|---|---|---|
| F0 | Scaffold monorepo + configuración `.env` | Proyecto corre vacío | 0.5 d |
| F1 | Ingesta Excel + normalización (§4) + calidad de datos + vista de tabla | RF1 | 1.5 d |
| F2 | Motor de detección D1a-D7 + correlación, con los 6 incidentes de §8 como test de regresión | RF2 | 2-3 d |
| F3 | Clasificación de riesgo con matriz y justificación por plantilla | RF3 | 0.5 d |
| F4 | Dashboard (sin "top IPs" como riesgo, §RF4) | RF4 | 1-2 d |
| F5 | Informe IA (2 versiones + limitaciones) + guardarraíl de citas | RF5, RF7 | 1-2 d |
| F6 | Export PDF | RF6 | 1 d |
| F7 | Seguridad + fixture de volumen sintético + README | RF8, §7 | 1 d |
| — | Video demo (≤ 5 min) — lo graba el usuario | Entregable bootcamp | — |

---

## 11. Riesgos y supuestos

| Riesgo | Mitigación |
|---|---|
| Falso positivo por cuenta de backup legítima (INC-6) | Campo `requires_validation` + sección de limitaciones; nunca se afirma ransomware sin evidencia de cifrado |
| LLM alucina hallazgos o inventa `Log_ID` | Motor determinístico decide; IA solo redacta; validación de que cada `Log_ID` citado exista en el incidente |
| Timeout 120 s del gateway | Streaming en todas las llamadas de informe |
| Cuota de tokens nan.builders | Modelo flash con cuota amplia; caché de narrativa por informe |
| Afirmación de escala no verificable con 715 filas | Fixture sintético de volumen, declarado como sintético (§7) |
| Datos sintéticos y redactados | Se declara en limitaciones; no se hacen afirmaciones de atribución (§4.9, §7.4) |
| Sobrecorrección: detectores ajustados al detalle del archivo | Reglas expresadas sobre entidades normalizadas, no sobre valores literales del dataset |

---

## 12. Criterios de aceptación

1. Con el archivo real cargado, la app detecta **los 6 incidentes de §8**, cada uno con la evidencia (`Log_ID`) correcta y sin falsos positivos sobre la línea base descrita en §6.
2. En particular: D1c detecta el brute force RDP de INC-2 pese a tener solo 4 intentos (una regla de conteo simple debe fallar este criterio).
3. Ninguna afirmación del informe carece de hallazgo/evidencia que la respalde (auditoría manual de muestra).
4. El informe PDF contiene las 9 secciones obligatorias en español (8 requeridas + limitaciones), en versión ejecutiva y técnica.
5. El flujo completo carga → informe PDF funciona en el demo sin errores.
6. La key de IA no aparece en el código fuente ni en el bundle del frontend.
7. El reporte de calidad de datos de RF1 señala correctamente `DC-01`/`DC01` como mismo host, los 262 nulos de `Destination` y los tipos mixtos de `Event_ID`.
