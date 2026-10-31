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
- T2 [S1] Excel ingestion + normalización (FSD §4) + reporte de calidad de datos + table view — commit `feat/ingest` — **desbloqueada**: esquema fijado en FSD §3
- T3 [S2,S8] Detection engine: D1a-D7 con umbrales de FSD §6 + correlación; los 6 incidentes de FSD §8 como test de regresión — commit `feat/detection`
- T4 [S4] Risk classification with justification (matriz impacto × confianza; no usa `Severity` del SIEM) — commit `feat/risk`
- T5 [S3] Dashboard: interactive charts by severity; sin "top IPs" como indicador de riesgo — commit `feat/dashboard`
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
