# SOC L2 Incident Analyzer

A web app that takes the SIEM export a client hands you as an Excel file and turns it into a
defensible incident analysis. It runs deterministic detections over the logs, correlates them into
incidents, classifies the risk with a written justification, shows an interactive dashboard that
drills down to the exact evidence rows, and writes a nine-section technical report in two Spanish
versions, exportable to PDF. The scenario is the one the project was built for: a cybersecurity
consultancy in Stockholm, a SOC L2 analyst, and an export of a day of logs with **no access to the
SIEM, EDR, DNS or netflow** that produced it.

**Live: <http://104.198.16.58>**. The real export is analysed end to end there, from the upload to
the PDF. It runs on a single GCP `e2-micro` instance from this repository, so what you see is the
code in `main`, not a mockup.

Every claim the app makes is tied to a `Log_ID` from the file. Nothing is asserted because a rule
"feels" right or because a model said so.

Stack: FastAPI + pandas (Python 3.12) · Angular 20 + Angular Material + barras CSS · ReportLab.

## How it works

```
.xlsx export → ingest/normalize → 10 detection rules → correlation → risk classification
             → dashboard + drill-down → nine-section report (ejecutiva + técnica) → PDF
```

1. **Ingest** reads the export and adds *derived* columns without touching the originals: 12
   observed columns become 36, so a finding can still cite the exact row it came from. The export
   needs that layer: `Event_ID` mixes ints and strings, `Result` changes meaning per log source,
   `DC-01` and `DC01` are the same host, `Destination` is null in 262 rows, and the semantic
   payload (`LogonType`, `share`, `bytes_out`, `uri`, …) is buried in free text.
2. **Detection** is ten independent, pure, unit-tested rules: `D1a`–`D1d` (directed brute force,
   password spray, external exposure, post-compromise logon) and `D2`–`D7` (suspicious logons,
   privilege escalation, suspicious command lines, lateral movement, other anomalies,
   exfiltration).
3. **Correlation** groups findings into incidents. **Classification** then assigns
   crítico / alto / medio / bajo from impact × evidence confidence, with a justification written
   by rules. The same levels feed the dashboard, the report and the PDF (one source of truth).
4. **The report** has the eight sections the client asked for plus a mandatory ninth,
   *Limitaciones del análisis*, in an executive and a technical version. The technical version
   quotes `Log_ID`s; the executive version cites none.

Four decisions the analysis depends on:

- **Thresholds come from the measured baseline, not from habit.** In this export the normal
  maximum is **2 failed logons per account per 10 minutes**, so 3 is signal. The RDP brute force in
  the same export has only **4 attempts**: a `≥5` counting rule would have missed a real attack, so
  external origin (`D1c`) is a separate rule from counting (`D1a`).
- **The SIEM's own `Severity` column is deliberately not used for classification.** It logs a
  privileged-account assignment from an external IP as `Informational`. It is displayed as source
  data and marked untrustworthy; the level is computed.
- **Correlation requires a shared account or a shared source IP, never a shared host alone.**
  Sharing a host is context, not evidence that the same actor did both things.
- **Model output is cited, then checked.** If assisted rewriting names a `Log_ID` that is not in
  that section's allowed evidence, names an `INC-` that does not exist, or asserts a level the
  classifier did not assign, the text is discarded and the deterministic text is kept.

## Quick start

Prerequisites:

- **Node 22**, pinned in `.nvmrc` (`nvm use`).
- **Python 3.12** and **[uv](https://docs.astral.sh/uv/)**; `backend/.python-version` pins 3.12.

Backend (port 8000):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --port 8000
```

Frontend (port 4200, proxies `/api` to 8000):

```bash
cd frontend
npm install
npm start
```

Then open <http://localhost:4200>.

**Where the export is uploaded from:** the client file is committed at the repo root,
`SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`. Drag it onto the upload page (`/cargar`) or pick
it with the file selector. Nothing else is needed, and no network access is required.

**Optional assisted writing.** The report is complete without any key. To enable the optional
model rewrite of three narrative sections:

```bash
cp backend/.env.example backend/.env    # from the repo root, then set NAN_API_KEY
```

Any OpenAI-compatible provider works (`NAN_BASE_URL`, `NAN_MODEL` are configuration). `.env` is
gitignored; the key never reaches the browser.

**Report and PDF from the API** (after an upload; before one, both return 409):

```bash
curl -s -X POST http://localhost:8000/api/report | head -c 400     # both versions + narrative state
curl -s -o informe.pdf http://localhost:8000/api/report/pdf        # nine sections, two versions
```

**Tests and lint:**

```bash
cd backend && uv run pytest -q      # 281 tests
cd backend && uv run ruff check .
cd frontend && npm test             # Karma + a local Chrome; add `-- --watch=false` for one run
```

`scripts/make_synthetic_export.py` builds the large fixture FSD §7 asks for instead of an
unverifiable row count: 50,050 rows copied from the real export, renumbered and shifted one day
apart, marked synthetic in its path, sheet name and workbook properties, written under the
gitignored `backend/out/`. It is never read by the report.

```bash
cd backend && uv run python ../scripts/make_synthetic_export.py
```

Measured on the development machine: 50,050 rows load in 7.5 s, detect in 17.6 s and classify in
0.2 s (25 s end to end, against the FSD's "< 30 s" claim). The real 715-row export analyses in
well under a second.

## Deploy

La instancia viva está en **<http://104.198.16.58>**, desplegada desde este repositorio en una
`e2-micro` de GCP.

La aplicación se publica en **un único servidor** con dos contenedores: `web` (Caddy, lo único
accesible desde Internet, sirve el bundle Angular y hace de proxy de `/api/*`) y `api` (FastAPI, sin
puertos publicados). No hay secretos en el repositorio: `NAN_API_KEY` es opcional y se pasa por
variable de entorno.

**Requisito de máquina:** una VM con **1 GB de RAM** (por ejemplo una GCP `e2-micro`, 2 vCPU
compartidas, 30 GB de disco) sirve para ejecutar la aplicación, pero **no** para compilarla. El
`Dockerfile` es multi-etapa y limita el heap de Node a 768 MB, así que la primera construcción en
una máquina tan pequeña **necesita un archivo de swap de unos 2 GB** o el build muere por falta de
memoria.

```bash
git clone https://github.com/ORG/REPO.git soc2 && cd soc2
docker compose up -d --build      # publica el 80 (y el 443 para HTTPS con dominio real)
```

Los pasos completos (firewall 80/443, IP externa estática, swap, instalación de Docker, clonado,
actualización tras `git push`, HTTPS con dominio propio y el detalle del límite de peticiones
detrás del proxy) están en **[`docs/deploy-gcp.md`](docs/deploy-gcp.md)**.

## What the analysis found

Six separate incidents in 5 h 58 min of a single day (2026-10-23, 07:46:07 → 13:44:06), 46
findings, **four crítico and two alto**. These are the numbers the app produces on the committed
export, not a curated subset.

| Incident | Level | What the logs show | Key evidence (`Log_ID`) |
|---|---|---|---|
| `INC-20261023-0820` | crítico | Password spray from `203.0.113.74`: 33 failed logons across 8 accounts, 19 s apart (08:25 → 08:35), then a successful logon (08:39) and special privileges assigned (08:40). | `EVT-00057`, `EVT-00111`, `EVT-00123`, `EVT-00126` |
| `INC-20261023-0902` | crítico | Complete RDP kill chain in 20 minutes: 4 external logon failures → successful RDP logon as `CORP\admin` → privileges → encoded PowerShell → `net view` → lateral logon with `source=APP-SRV01` → `Finance` share → `tar` staging → outbound HTTPS to `203.0.113.88:443`. Eight of the ten rules fire. | `EVT-00188`, `EVT-00198`, `EVT-00225`, `EVT-00232`, `EVT-00235` |
| `INC-20261023-0936` | alto (*requires validation*) | `CORP\backupsvc`: encoded PowerShell → 16 sequential reads of `Finance\FY2026\*.xlsx` every 16 s → `vssadmin delete shadows`. The same account also performs legitimate Finance reads (23 of the 64 object-access events), and backup tooling uses `vssadmin` too. Reported as requiring validation; **not** called ransomware. | `EVT-00280`, `EVT-00284`, `EVT-00309`, `EVT-00314` |
| `INC-20261023-1042` | crítico | Staging on `WS-018` (`7z.exe` packing `C:\Legal\*.docx` into `C:\Users\Public`), then 22 HTTPS POSTs to `198.51.100.88`: **253,305,558 bytes** measured from the proxy rows. | `EVT-00428`, `EVT-00435`, `EVT-00460` |
| `INC-20261023-1137` | alto | Masquerading persistence on `APP-SRV01`: scheduled task `\Microsoft\Windows\UpdateCheck` running `C:\ProgramData\updatecheck.ps1`, a service installed as `WinUpdateHelper`, and repeated executions, all outside the maintenance window, from a helpdesk account. | `EVT-00523`, `EVT-00524`, `EVT-00564` |
| `INC-20261023-1210` | crítico | Web shell: `/uploads/test.aspx?cmd=whoami` answered **200**, and the IIS application pool then spawned `cmd.exe /c whoami`. | `EVT-00571`, `EVT-00599` |

These numbers are reproducible from the repo: the six clusters are a regression fixture in
`backend/tests/test_detection_incidents.py`, and `backend/tests/test_risk.py` exercises the same
six through the classifier. Levels are the app's Spanish ones (`crítico` / `alto`); the README is
English, the product is not.

## Design decisions worth defending

1. **Thresholds are measured, not assumed.** 2 failed logons per account per 10 minutes is the
   baseline, so 3 fires and 2 does not.
2. **The discriminator is external origin, not count.** The 4-attempt RDP brute force is caught
   because it comes from outside, not because it is frequent.
3. **The SIEM `Severity` column cannot move a level.** Rewriting the whole column to `High` or to
   `Informational` changes nothing (pinned by a test).
4. **Incidents merge only through an account or a source IP.** Merging on a shared host once
   attached an unrelated baseline logon to the RDP kill chain; that defect is gone and pinned.
5. **Evidence is a tuple of `Log_ID`s produced by the rule that fired.** No consumer re-derives
   evidence, and a test asserts every cited id exists in the export.
6. **Measured quantities are typed fields, not prose.** Outbound volume comes from
   `measured_bytes`, so rewording the justification cannot move the severity.
7. **One row can never support crítico**, but only after the rule cites every row it already has.
   Applying that cap to incomplete evidence once produced a wrong severity on the web shell.
8. **Ambiguity is an output.** The service-account case ships `requires_validation` and is never
   escalated into a ransomware claim the logs do not support.
9. **Upload and rate limiting are enforced server-side and by content.** ZIP signature plus
   workbook parts, size checked before the body is read, and client identity taken from the TCP
   peer, never from `X-Forwarded-For`.
10. **The report is a pure function of the analysis.** Same input, same text; the only variable
    part is prose the guard allowed to survive.

## Limitations

Taken from FSD §7.4 and printed in every report:

1. The window is **5 h 58 min of a single day**: no recurrence, persistence history or trend can be
   established.
2. No platform access (SIEM/EDR/DNS/netflow): the analysis is limited to the exported fields.
3. **Payloads are redacted at the source** (`[REDACTED_SYNTHETIC]`, `<base64_redacted>`), so what
   the encoded command did and which channel it used cannot be determined.
4. `Source_IP` does not resolve to a hostname; origin↔destination links are taken from the event
   text when it is available.
5. **The data is synthetic and its external IPs are RFC 5737 documentation ranges**: no
   geolocation, no reputation, no threat intelligence.
6. The SIEM `Severity` column is inconsistent and is not used for classification.
7. Absence of a finding is not proof of absence of compromise. It only means this export has no
   evidence of one.
8. The export **does not declare the account type**: service accounts are recognised by naming
   convention, so `CORP\svc_backup` is classified as a human account and appears in the human
   ranking (the dashboard states which accounts it excludes and why).

## AI use

AI was the **tool that built the project**, which is also what the assignment asked for: agents and
models were used to profile the real export, to write the specification from measured facts (the
unverifiable "100k rows in under 30 s" requirement was replaced with a declared synthetic fixture
before any code was written), to implement the work in reviewable units with tests, and to review
its own output. Several real defects were found and fixed that way, among them the host-based
correlation above and a size check that only ran after the whole upload was already in memory.

The **analysis itself stays deterministic on purpose**. Rules decide findings, levels and counts;
the model may only rewrite the prose of sections 1, 6 and 7, and only if the citation guard
accepts it. Without a key the report is complete and the narrative state is `no_configurada`.
A missing key is not a failure. The guard's own limit is documented: asserted levels are
detected with a finite set of Spanish phrasings, so a novel wording could slip through; the
mitigation is a closed prompt plus a conservative fallback, not NLP.

## Repository layout

```
backend/        FastAPI: ingest → detection → risk → reporting → export (281 tests)
frontend/       Angular 20 + Angular Material + gráficos de barras CSS
docs/FSD.md     Functional spec, measured against the real export (Spanish)
odd/tasks/      Task log with the decisions and the defects found along the way
scripts/        Synthetic volume fixture generator (never used by the report)
```
