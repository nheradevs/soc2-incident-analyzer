# SOC L2 Log Analysis App (Bootcamp final project)

Web app that imports a SIEM Excel export and produces AI-assisted incident analysis with a risk-classified technical report (PDF).
Spec source of truth: `docs/FSD.md` (v0.2, validada contra el archivo real).

## Specs

- S1: Carga de archivos — importar y visualizar el Excel `SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`
- S2: Análisis de seguridad — detectar: fuerza bruta, inicios sospechosos (origen/horario/patrón), escalamiento de privilegios, ejecución sospechosa de comandos/procesos, movimiento lateral, otras anomalías; correlacionar eventos
- S3: Dashboard — estadísticas y gráficos interactivos por criticidad
- S4: Clasificación de riesgos — crítico/alto/medio/bajo con justificación
- S5: Informe técnico — 2 versiones en español (ejecutiva y técnica) con: resumen ejecutivo, hallazgos, explicación técnica por hallazgo, evidencias de los logs, criticidad y justificación, impacto organizacional, plan de acción (investigar/contener/remediar), recomendaciones generales
- S6: Exportación — descarga del informe en PDF
- S7: IA integrada — apoya análisis y redacción; proveedor nan.builders (OpenAI-compatible, `https://api.nan.builders/v1`, key server-side en .env)
- S8: Rigor analítico — no inventar hallazgos; cada conclusión sustentada estrictamente en los registros
- S9: Interfaz moderna, intuitiva y fácil de utilizar
- S10: Sin integración con Microsoft Sentinel ni plataformas

## Schema (hecho medido — FSD §3)

`Log_ID · Timestamp · Hostname · Event_ID · User · Source_IP · Destination · Log_Source · Event_Description · Process_CommandLine · Result · Severity`
715 filas, 1 hoja `SIEM Export`, ventana 2026-10-23 07:46:07 → 13:44:06.

Trampas que obligan a la capa de normalización (FSD §4): `Event_ID` mixto int/str; `Timestamp` como object; `Result` con semántica por fuente; `DC-01`/`DC01` mismo host; `User` `-` e `IIS APPPOOL\*`; `Destination` heterogéneo (262 nulos); dato semántico en texto libre; `Source_IP` no mapea a host; IPs externas en rangos RFC 5737; `Severity` del SIEM inconsistente.

## Tasks

- T1 [S9,S7] Scaffold monorepo: backend FastAPI + frontend Angular 20 — commit `feat/scaffold` → `0f5adc6`
- T2 [S1] Excel ingestion + normalización (FSD §4) + reporte de calidad de datos + table view — commits `8383bbb`, `fdde8ff`, `feat(ui)` — **completa**
- T3 [S2,S8] Detection engine: D1a-D7 + correlación; los 6 incidentes de FSD §8 como regresión — commit `feat(detection)` — **completa**
- T4 [S4] Risk classification with justification (matriz impacto × confianza; no usa `Severity` del SIEM) — commits `0b6f6a5`, `fix(risk)` — **completa**
- T5 [S3] Dashboard: interactive charts by severity; sin "top IPs" como indicador de riesgo — commits `396aa03`, `feat(ui)` — **completa**
- T6 [S5,S7] Report generation: executive + technical versions in Spanish + limitaciones obligatorias, evidence-cited, via nan.builders streaming — commit `feat/report`
- T7 [S6] PDF export — commit `feat/pdf`
- T8 [S10] Security: upload validation, sanitization, CORS, env config — commit `chore/security`
- T9 [S9] Demo polish + README for portfolio — commit `docs/readme`

## Log

- L1 (user): "analiza este requerimiento" — PDF PROYECTO FINAL.pdf adjunto; luego confirmó tener el Excel, eligió Angular ("React es una mierda... puede ser mejor en este caso angular"), stack rápido y sencillo con "un poco de seguridad", IA vía nan.builders (https://nan.builders/docs).
- L2 (user): "Por favor, analiza los archivos de esta carpeta. Deben tener la base para mi último proyecto del bootcamp analista soc 2 en base a las indicaciones de los profesores" — pegado completo del enunciado del bootcamp (contexto Estocolmo/SOC N2, 6 funcionalidades, 8 secciones del informe, entregables PDF + video ≤5 min, valor de portafolio).
- L3 (evidence): el Excel real está en el repo. Perfilado completo: 715 filas × 12 columnas, no "miles de miles"; 6 incidentes plantados verificados con `Log_ID` (FSD §8); línea base de `4625` medida en máximo 2 fallos/usuario/10 min; brute force RDP de INC-2 tiene solo 4 intentos y **no** lo detecta una regla de conteo `≥5` → se separa D1c (externo) de D1a (conteo).
- L4 (user): "Ve por la A" — autoriza actualizar FSD + este documento con el esquema real, las trampas de datos, los umbrales medidos y las 4 correcciones, antes de escribir código.
- L5 (decision): FSD elevado a v0.2. Correcciones aplicadas: (1) se retira el RNF "100k filas en <30 s" por inverificable → fixture sintético declarado; (2) se agrega capa `normalize.py` + `parse.py` a la arquitectura; (3) se agrega §7.4 Limitaciones como sección **obligatoria** del informe (9 secciones, no 8); (4) este Log se actualiza y T2/T3 se declaran desbloqueadas. INC-6 (`backupsvc`) queda como caso de calibración de S8 con `requires_validation`.
- L6 (decision): entorno resuelto. Node 22.23.4 vía nvm (user-scoped en `~/.nvm`, alias `default` → 22), `.nvmrc`=22. Requirió comentar `prefix=/home/nhera/.npm-global` en `~/.npmrc` (backup en `~/.npmrc.bak`): nvm rechazaba activar su Node mientras ese prefix existiera. Backend pinneado a Python 3.12.3 (uv intentaba 3.15.2 de su intérprete managed — demasiado al filo). Angular 20.3.0 (Node 18.19.1 del sistema era el techo de Angular 19).
- L7 (evidence): `feat/scaffold` = `0f5adc6`, 31 archivos. Backend: FastAPI + pydantic-settings, CORS a `http://localhost:4200`, `/api/health`, uvicorn verificado a mano. Frontend: Angular 20 standalone + `proxy.conf.json` (`/api` → `:8000`), build 247 kB initial (bajo el budget de 500 kB). 6 tests verdes (health + contrato CORS), ruff limpio. CORS verificado empíricamente: origen no confiable no recibe `Access-Control-Allow-Origin` y su preflight da 400.
- L8 (evidence): T2 completa en tres work units. `8383bbb` normalización + parseo (40 tests). `fdde8ff` `quality.py` + `/api/upload` + `/api/events` (64 tests). UI Angular Material 20.2.14 (23 specs Karma verdes, build 312 kB initial + chunk lazy de 382 kB).
- L9 (decision): revisión del slice de API detectó que el tamaño del upload se validaba **después** de `await file.read()` completo — un archivo enorme agotaba memoria antes del rechazo (RF8). Corregido con `file.size` y lectura acotada a `max_bytes + 1`.
- L10 (evidence): e2e real por el proxy del dev server (`ng serve` → `/api` → uvicorn), no sólo `HttpTestingController`: upload 715 filas/12 columnas, calidad reporta `DC01` = `DC-01`(91)+`DC01`(30)=121 filas y `event_id` mixto, `search=PROXY_ACCESS` devuelve 22 de 715 en 11 páginas con 36 columnas (12 originales + 24 derivadas), rechazo `.txt` en español. Incidente de entorno: dos intentos fallidos por `pkill -f` que matcheaba la línea de comandos del propio script, y un uvicorn zombie de la verificación del scaffold que ocupaba el puerto 8000 (el `kill` mató el wrapper `uv run`, no al servidor). Regla adoptada: limpiar por PID del puerto, nunca con `pkill -f` sobre patrones que aparecen en el propio script.
- L11 (evidence): T3. `feat(detection)`: 10 detectores (D1a-D1d, D2-D7), modelo Finding/Incident con textos en español, correlador y `detect()`. Sobre el archivo real: **6 incidentes, 46 hallazgos**, todos los `Log_ID` citados existen. 149 tests.
- L12 (bugfix): dos defectos detectados en revisión y corregidos. (1) D3 disparaba con **un solo** fallo de logon interno: `mruiz` tiene 5 fallos en todo el archivo y máximo 1 por ventana de 10 min, o sea línea base según FSD §6. (2) El correlador fusionaba por host compartido, y ese hallazgo se pegó a la kill chain del RDP haciendo que la narrativa dijera "Cuentas involucradas: admin, mruiz" e "IPs: 10.10.1.14...". Correcciones: D3 interno exige la ráfaga de D1a (≥3 fallos/10 min, reutilizando `D1A_MIN_FAILURES`/`D1A_WINDOW`) o origen externo; el correlador sólo une por **cuenta o IP de origen**, nunca por host. Verificado: 6 incidentes siguen, D3 evidence queda en `{EVT-00126, EVT-00193}`, y `mruiz`/`10.10.1.14` no aparecen en ningún incidente. El test que codificaba el defecto se reemplazó por los tests de borde (1 fallo no dispara, 2 no, 3 sí, >10 min no).
- L13 (limitación conocida): en el spray, los D1a por cuenta pueden incluir en su evidencia algún fallo interno de la misma cuenta dentro de la ventana (p. ej. `dtorres`: EVT-00046 interno 08:20:12 + dos externos 08:27/08:29). No es un defecto: la regla es por cuenta según FSD §5 y las tres filas son fallos reales de esa cuenta en 9m33s. Para T6: la narrativa debe nombrar el origen dominante (203.0.113.74) y no presentar la IP interna como atacante.
- L14 (evidence): T4. `0b6f6a5` matriz impacto × confianza con justificación por reglas. Niveles finales: INC-0820 crítico, INC-0902 crítico, INC-0936 alto (con `requires_validation`), INC-1042 crítico, INC-1137 alto, INC-1210 crítico.
- L15 (bugfix): tres defectos de la revisión de T4. (1) El web shell salía `alto`: el tope de "una sola fila no sostiene crítico" — regla correcta — se activaba porque el detector D4 `iis-apppool` citaba sólo `EVT-00599` teniendo `EVT-00571` (`/uploads/test.aspx?cmd=whoami` → **200**) disponible. Ahora cita ambas y el incidente es `crítico`; las filas 4xx del mismo path (`EVT-00573/00574`) **no** se citan. (2) `risk/matrix.py` recuperaba los bytes exfiltrados con un regex sobre la prosa en español: se agregó `measured_bytes` al modelo `Finding` (D7 lo llena: `253305558`) y se eliminó el parser; test que cambia el texto y verifica que el nivel no se mueve. (3) La justificación del spray decía "7 IPs de origen" cuando el ataque vino de una sola externa: ahora separa por `ip_class` — "1 IP externa como origen del ataque (203.0.113.74), 6 IPs internas observadas en la evidencia, no orígenes del ataque".
- L16 (criterio aprendido): una salvaguarda epistémica (el tope de una fila) aplicada sobre evidencia incompleta produce una severidad **incorrecta**, que es peor que no tener la salvaguarda. Antes de aceptar un nivel bajo por un tope, verificar si el detector está citando toda la evidencia que ya tiene.
- L17 (evidence): T5. `396aa03` payload del dashboard + drill-down (192 tests backend). UI en `feat(ui)`: ruta lazy `/analisis`, 6 gráficos Chart.js 4.6.1, lista de incidentes ordenada por severidad, drill-down con evidencia deduplicada y `Log_ID` visible. 49 specs Karma, build 319,82 kB initial sin warnings.
- L18 (decision): dos guardarraíles quedaron en el **backend**, no en la UI, para que la interfaz no pueda equivocarse: no existe ranking de IPs de origen (FSD §4.8) y la salida se agrupa sólo por destino externo, distinguiendo "bytes no registrados" de "cero bytes" (`events_with_bytes=0` → barra ausente + leyenda, nunca 0 MB).
- L19 (bugfix): la navegación usaba `<a href>` (recarga completa de la SPA). Corregido a `routerLink` en los tres enlaces, con `provideRouter([])` en los specs de `ingest-page` y `analysis-page`.
- L20 (limitación registrada): el export no declara tipo de cuenta, así que `CORP\svc_backup` entra en el ranking de cuentas humanas. Queda como limitación #8 del FSD: el dashboard declara qué excluye (anónimas, máquina) y por qué, pero no puede afirmar qué es cuenta de servicio sin un atributo que lo respalde.
