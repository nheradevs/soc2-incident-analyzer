"""Deterministic Spanish report, complete on its own (FSD RF5 / S5).

Both versions render the same nine mandatory sections from the structured brief:
the eight of the client requirement plus `Limitaciones del análisis`, added in
FSD §7.4. Every paragraph is computed from the analysis (no placeholder, no
wall-clock value), so the same brief always produces the same bytes.

The two audiences differ in vocabulary, not in facts:

* ``ejecutiva`` speaks about business impact and never cites a `Log_ID`;
* ``tecnica`` explains each finding, quoting the evidence that supports it.

The criticality, its justification, the evidence lists and the limitations are
always rule-written: FSD RF3 requires the justification to be traceable, and the
limitations are mandatory statements. Assisted writing can only rewrite the
narrative sections (see `app.reporting.compose`).
"""

from __future__ import annotations

from typing import Any

from app.detection.context import count_es
from app.reporting.narrative import NARRATIVE_TEMPLATE

VERSIONS: tuple[str, ...] = ("ejecutiva", "tecnica")
VERSION_LABEL_ES = {
    "ejecutiva": "Versión ejecutiva",
    "tecnica": "Versión técnica",
}

SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("resumen-ejecutivo", "Resumen ejecutivo"),
    ("hallazgos-identificados", "Hallazgos identificados"),
    ("explicacion-tecnica", "Explicación técnica de cada hallazgo"),
    ("evidencias-logs", "Evidencias encontradas en los logs"),
    ("criticidad-justificacion", "Criticidad y justificación"),
    ("impacto-organizacion", "Posible impacto en la organización"),
    ("plan-de-accion", "Plan de acción: investigar → contener → remediar"),
    ("recomendaciones-generales", "Recomendaciones generales de seguridad"),
    ("limitaciones-analisis", "Limitaciones del análisis"),
)
SECTION_KEYS = tuple(key for key, _ in SECTION_SPECS)
SECTION_TITLES = tuple(title for _, title in SECTION_SPECS)

LEVEL_PLURAL_ES = {
    "crítico": "críticos",
    "alto": "altos",
    "medio": "medios",
    "bajo": "bajos",
}

# Business wording of each detection category (executive version).
CATEGORY_PLAIN_ES = {
    "brute-force": (
        "se intentaron adivinar contraseñas mediante intentos repetidos de inicio de sesión"
    ),
    "suspicious-logon": "se produjo un inicio de sesión fuera de lo habitual",
    "privilege-escalation": (
        "se asignaron privilegios administrativos dentro de una sesión no habitual"
    ),
    "command-execution": (
        "se ejecutaron comandos y procesos no justificados en los equipos afectados"
    ),
    "lateral-movement": "la actividad se desplazó de un equipo a otro dentro de la red",
    "other-anomaly": "se observó actividad anómala sobre datos y servicios",
}

# Potential impact of each category, stated as a possibility (section 6).
IMPACT_PHRASE_ES = {
    "brute-force": "compromiso de credenciales y uso indebido de las cuentas afectadas",
    "suspicious-logon": "acceso no autorizado a los equipos afectados con una cuenta válida",
    "privilege-escalation": (
        "operación con privilegios administrativos por parte de un atacante"
    ),
    "command-execution": "ejecución de código no autorizado en los equipos afectados",
    "lateral-movement": (
        "propagación del ataque hacia servidores con información sensible"
    ),
    "other-anomaly": "pérdida, alteración o salida de información sin detección oportuna",
}

INVESTIGATE_ES = {
    "brute-force": (
        "revisar los intentos fallidos y confirmar si alguna credencial quedó comprometida"
    ),
    "suspicious-logon": (
        "verificar con la persona titular de la cuenta si el inicio de sesión corresponde "
        "a su actividad"
    ),
    "privilege-escalation": (
        "auditar la asignación de privilegios y el uso de la cuenta afectada"
    ),
    "command-execution": (
        "analizar la línea de comandos y el binario ejecutado en el equipo afectado"
    ),
    "lateral-movement": "revisar los accesos desde el equipo de origen hacia los destinos",
    "other-anomaly": "determinar qué datos se leyeron o transfirieron y hacia dónde",
}
CONTAIN_ES = {
    "brute-force": (
        "bloquear el origen externo y forzar el cambio de contraseña de las cuentas afectadas"
    ),
    "suspicious-logon": "suspender la sesión y la cuenta hasta confirmar su legitimidad",
    "privilege-escalation": (
        "retirar los privilegios especiales temporales y revisar los grupos administrados"
    ),
    "command-execution": (
        "aislar el equipo afectado de la red y conservar la evidencia antes de limpiarlo"
    ),
    "lateral-movement": (
        "segmentar el acceso entre los equipos implicados y revocar sesiones remotas"
    ),
    "other-anomaly": (
        "cortar la salida hacia el destino externo implicado y preservar los registros"
    ),
}
REMEDIATE_ES = {
    "brute-force": "aplicar autenticación multifactor y una política de bloqueo progresivo",
    "suspicious-logon": "revisar la política de acceso remoto y exigir un segundo factor",
    "privilege-escalation": (
        "aplicar el mínimo privilegio y separar las cuentas administrativas"
    ),
    "command-execution": (
        "actualizar el software afectado y restringir la ejecución de comandos"
    ),
    "lateral-movement": (
        "aplicar segmentación de red y limitar el acceso administrativo entre equipos"
    ),
    "other-anomaly": "implantar control de salida de datos y revisar la retención de registros",
}
VALIDATION_INVESTIGATE = (
    "validar primero si la actividad corresponde a una tarea legítima de respaldo o "
    "administración, porque el patrón también es compatible con ella"
)
VALIDATION_CONTAIN = "no aplicar una contención irreversible hasta completar esa validación"

# General recommendations. `categories=None` means "always shown"; the order of
# this table is the order of the report, which keeps the output deterministic.
RECOMMENDATIONS: tuple[dict[str, Any], ...] = (
    {
        "categories": frozenset({"brute-force", "suspicious-logon"}),
        "tecnica": (
            "Exigir autenticación multifactor en las cuentas privilegiadas y en el acceso "
            "remoto (RDP/VPN), y bloquear el inicio de sesión desde direcciones externas "
            "no autorizadas."
        ),
        "ejecutiva": (
            "Activar la verificación en dos pasos en las cuentas con más permisos y en el "
            "acceso desde fuera de la oficina."
        ),
    },
    {
        "categories": frozenset({"privilege-escalation"}),
        "tecnica": (
            "Revisar la asignación de privilegios administrativos y aplicar el mínimo "
            "privilegio, separando las cuentas de administración de las de uso diario."
        ),
        "ejecutiva": (
            "Revisar quién tiene permisos de administrador y reducir esa lista a lo "
            "imprescindible."
        ),
    },
    {
        "categories": frozenset({"command-execution"}),
        "tecnica": (
            "Restringir PowerShell, cmd.exe y la ejecución desde rutas escribibles como "
            "C:\\Temp o C:\\ProgramData mediante listas de permitidos, y registrar la línea "
            "de comandos completa."
        ),
        "ejecutiva": (
            "Limitar qué programas pueden ejecutarse en los servidores y dejar registro de "
            "cada ejecución."
        ),
    },
    {
        "categories": frozenset({"lateral-movement"}),
        "tecnica": (
            "Segmentar la red y limitar el acceso administrativo entre estaciones y "
            "servidores de archivos; revisar los recursos compartidos de alto valor."
        ),
        "ejecutiva": (
            "Separar la red por áreas para que un equipo comprometido no alcance los "
            "servidores con información sensible."
        ),
    },
    {
        "categories": frozenset({"other-anomaly"}),
        "tecnica": (
            "Controlar el tráfico saliente por destino y volumen (proxy/DLP) y alertar "
            "sobre transferencias anómalas hacia direcciones externas."
        ),
        "ejecutiva": (
            "Vigilar cuánta información sale hacia internet y avisar cuando el volumen sea "
            "anómalo."
        ),
    },
    {
        "categories": None,
        "tecnica": (
            "Ampliar la retención de registros y la ventana de análisis más allá de "
            "{duration} para poder establecer recurrencia y tendencia."
        ),
        "ejecutiva": (
            "Conservar los registros durante más tiempo y analizar periodos más largos que "
            "{duration} para detectar repeticiones."
        ),
    },
    {
        "categories": None,
        "tecnica": (
            "Incorporar el tipo de cuenta (humana, de servicio, de máquina) como atributo "
            "del export para que el análisis no dependa de la convención de nombres."
        ),
        "ejecutiva": (
            "Etiquetar en el inventario qué cuentas son de personas y cuáles de servicios, "
            "para no analizarlas igual."
        ),
    },
)


def _minutes_label(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    if hours:
        return f"{hours} h"
    return f"{rest} min"


def _count_noun(count: int, singular: str, plural: str) -> str:
    return f"{count_es(count)} {singular if count == 1 else plural}"


def _join_and(values: list[str]) -> str:
    if not values:
        return "ninguna"
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} y {values[-1]}"


def _join_semicolon(values: list[str]) -> str:
    return "; ".join(values)


def _sentence(text: str) -> str:
    cleaned = text.strip()
    return cleaned if cleaned.endswith((".", ":", ";")) else f"{cleaned}."


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _evidence_reference(log_ids: list[str]) -> str:
    total = count_es(len(log_ids))
    if len(log_ids) <= 4:
        return f"{', '.join(log_ids)} ({total} Log_ID)"
    shown = ", ".join(log_ids[:4])
    hidden = count_es(len(log_ids) - 4)
    return f"{shown} y {hidden} más ({total} Log_ID)"


def _level_distribution(scope: dict[str, Any]) -> str:
    return ", ".join(
        f"{level['level']} {level['incidents']}" for level in scope["levels"]
    )


def _level_summary(scope: dict[str, Any]) -> str:
    parts = [
        f"{count_es(level['incidents'])} {LEVEL_PLURAL_ES[level['level']]}"
        for level in scope["levels"]
        if level["incidents"]
    ]
    return _join_and(parts)


def _resumen_ejecutivo(brief: dict[str, Any], version: str) -> list[str]:
    scope = brief["scope"]
    if not brief["incidents"]:
        return [
            f"Se analizaron {count_es(scope['events_analysed'])} eventos registrados "
            f"entre las {scope['start']} y las {scope['end']} del {scope['date']} "
            f"({_minutes_label(scope['duration_minutes'])}). El análisis no identificó "
            "incidentes de seguridad con la evidencia disponible en este export.",
        ]
    if version == "ejecutiva":
        external = _count_noun(
            len(scope["external_sources"]), "dirección externa", "direcciones externas"
        )
        return [
            f"Entre las {scope['start']} y las {scope['end']} del {scope['date']} se "
            f"registraron {count_es(scope['events_analysed'])} eventos de seguridad. El "
            f"análisis identificó {count_es(scope['incidents'])} incidentes que requieren "
            f"atención: {_level_summary(scope)}.",
            f"En conjunto, los incidentes afectan a "
            f"{_count_noun(len(scope['users']), 'cuenta', 'cuentas')}, "
            f"{_count_noun(len(scope['hosts']), 'equipo', 'equipos')} y "
            f"{external} que participaron como origen del ataque.",
            f"El incidente más grave es «{brief['incidents'][0]['title']}» "
            f"({brief['incidents'][0]['level']}) y agrupa "
            f"{count_es(brief['incidents'][0]['event_count'])} eventos.",
            "Las conclusiones se basan únicamente en los registros del export; las "
            "limitaciones se explican en la sección 9.",
        ]
    return [
        f"Se analizaron {count_es(scope['events_analysed'])} eventos normalizados del "
        f"export del SIEM entre las {scope['start']} y las {scope['end']} del "
        f"{scope['date']} ({_minutes_label(scope['duration_minutes'])}). El motor de "
        f"detección produjo {count_es(scope['findings'])} hallazgos agrupados en "
        f"{count_es(scope['incidents'])} incidentes de seguridad.",
        f"Distribución por criticidad: {_level_distribution(scope)}.",
        f"Categorías con hallazgos: "
        f"{_join_and(scope['categories_covered_labels'])}.",
        "Toda cifra de este informe proviene del motor de reglas y de la matriz de "
        "clasificación; la redacción asistida no decide hallazgos, niveles ni conteos.",
    ]


def _hallazgos_identificados(brief: dict[str, Any], version: str) -> list[str]:
    incidents = brief["incidents"]
    if not incidents:
        return ["No se identificaron incidentes en este export."]
    body = [
        f"El análisis agrupa {count_es(len(incidents))} incidentes correlacionados. La "
        "criticidad es la del motor de reglas y no la del campo Severity del SIEM."
    ]
    for incident in incidents:
        accounts = _count_noun(
            len(incident["entities"]["users"]), "cuenta", "cuentas"
        )
        hosts = _count_noun(len(incident["entities"]["hosts"]), "equipo", "equipos")
        if version == "tecnica":
            body.append(
                f"• {incident['id']} · {incident['title']}: criticidad "
                f"{incident['level']} (impacto {incident['impact']} × confianza "
                f"{incident['confidence']}), {count_es(incident['event_count'])} eventos y "
                f"{count_es(len(incident['findings']))} hallazgos. Ventana: "
                f"{incident['start']} → {incident['end']} del {incident['date']} "
                f"({incident['duration_minutes']} min); {accounts}, {hosts}."
            )
        else:
            body.append(
                f"• {incident['title']}: criticidad {incident['level']}. Agrupa "
                f"{count_es(len(incident['findings']))} hallazgos sobre {accounts} "
                f"y {hosts}, con {count_es(incident['event_count'])} eventos registrados "
                f"entre las {incident['start']} y las {incident['end']} del "
                f"{incident['date']}."
            )
    return body


def _explicacion_tecnica(brief: dict[str, Any], version: str) -> list[str]:
    incidents = brief["incidents"]
    if not incidents:
        return ["No hay hallazgos que explicar en este export."]
    body: list[str] = []
    for incident in incidents:
        if version == "ejecutiva":
            sentences = " ".join(
                _sentence(_capitalize(CATEGORY_PLAIN_ES[category]))
                for category in incident["categories"]
            )
            body.append(
                f"{incident['title']}. {sentences} Se registraron "
                f"{count_es(incident['event_count'])} eventos entre las "
                f"{incident['start']} y las {incident['end']} del {incident['date']}. "
                f"Criticidad {incident['level']}."
            )
            continue
        body.append(
            f"{incident['id']} · {incident['title']}: "
            f"{count_es(len(incident['findings']))} hallazgos correlacionados "
            f"({_join_and(incident['categories_labels'])})."
        )
        for finding in incident["findings"]:
            body.append(
                f"{finding['code']} · {finding['title']}: "
                f"{count_es(finding['event_count'])} eventos entre "
                f"{finding['start']} y {finding['end']} del {incident['date']}; "
                f"criticidad {finding['level']}. {_sentence(finding['rationale'])} "
                f"Evidencia: {_evidence_reference(finding['evidence'])}."
            )
    return body


def _evidencias_logs(brief: dict[str, Any], version: str) -> list[str]:
    incidents = brief["incidents"]
    total = sum(len(incident["evidence"]) for incident in incidents)
    if not incidents:
        return ["No se identificaron eventos de evidencia en este export."]
    if version == "tecnica":
        body = [
            f"Los {count_es(total)} eventos de evidencia citados existen en el export y "
            "son los mismos que sustentan la clasificación de cada incidente."
        ]
        for incident in incidents:
            body.append(
                f"{incident['id']}: {count_es(len(incident['evidence']))} eventos de "
                f"evidencia entre las {incident['start']} y las {incident['end']} del "
                f"{incident['date']}. Log_ID: {', '.join(incident['evidence'])}."
            )
        return body
    body = [
        "No se incluyen identificadores técnicos (Log_ID) en esta versión: están en la "
        f"versión técnica. La evidencia son {count_es(total)} eventos de registro del "
        f"{brief['scope']['date']}, distribuidos así:"
    ]
    for incident in incidents:
        body.append(
            f"• {incident['title']}: {count_es(len(incident['evidence']))} eventos entre "
            f"las {incident['start']} y las {incident['end']} del {incident['date']}."
        )
    return body


def _criticidad_justificacion(brief: dict[str, Any], version: str) -> list[str]:
    if version == "tecnica":
        intro = (
            "La criticidad no la decide la redacción asistida: la asigna el motor de reglas "
            "con la matriz impacto × confianza, y su justificación se genera con reglas a "
            "partir de los datos del hallazgo."
        )
    else:
        intro = (
            "La criticidad no la decide la redacción asistida: la asignan las reglas del "
            "análisis a partir de los datos registrados."
        )
    body: list[str] = [intro]
    for incident in brief["incidents"]:
        if version == "tecnica":
            body.append(
                f"{incident['id']}: criticidad {incident['level']} (impacto "
                f"{incident['impact']} × confianza {incident['confidence']}). "
                f"{_sentence(incident['justification'])}"
            )
            continue
        # The executive text states the same classification from the structured
        # factors of the matrix, so the rule-written justification (which cites
        # `Log_ID`s) is not duplicated into a business-language section.
        validation = (
            "El caso está marcado como «requiere validación»: el patrón también es "
            "compatible con actividad legítima y no se presenta como compromiso confirmado."
            if incident["requires_validation"]
            else "La evidencia sostiene el nivel asignado sin marcas de ambigüedad."
        )
        body.append(
            f"{incident['id']}, criticidad {incident['level']}: impacto potencial "
            f"{incident['impact']} y confianza {incident['confidence']} en la evidencia, "
            f"que agrupa {count_es(incident['event_count'])} eventos y "
            f"{count_es(len(incident['findings']))} hallazgos. {validation}"
        )
    if not brief["incidents"]:
        body.append("No hay incidentes que clasificar en este export.")
    return body


def _impacto_organizacion(brief: dict[str, Any], version: str) -> list[str]:
    if not brief["incidents"]:
        return [
            "Sin incidentes identificados, no se declara un impacto organizacional "
            "atribuible a este export."
        ]
    body = [
        "El impacto descrito es potencial: expresa qué podría ocurrir si el incidente se "
        "confirma, no un daño ya verificado."
    ]
    for incident in brief["incidents"]:
        phrases = [
            IMPACT_PHRASE_ES[category]
            for category in incident["categories"]
            if category in IMPACT_PHRASE_ES
        ]
        scope = (
            f"{_count_noun(len(incident['entities']['users']), 'cuenta', 'cuentas')} y "
            f"{_count_noun(len(incident['entities']['hosts']), 'equipo', 'equipos')}"
        )
        if incident["entities"]["shares"]:
            shares = _count_noun(
                len(incident["entities"]["shares"]),
                "recurso compartido",
                "recursos compartidos",
            )
            scope += f", con acceso a {shares}"
        validation = (
            " El incidente está marcado como «requiere validación»: no se presenta como "
            "compromiso confirmado."
            if incident["requires_validation"]
            else ""
        )
        if version == "tecnica":
            body.append(
                f"{incident['id']} · {incident['title']}: si se confirma, el impacto "
                f"posible es {_join_semicolon(phrases)}. Alcance observado: {scope}. "
                f"Criticidad {incident['level']}.{validation}"
            )
        else:
            body.append(
                f"{incident['title']}: si se confirma, para la organización el impacto "
                f"posible es {_join_semicolon(phrases)}. Afectaría a {scope}. "
                f"Criticidad {incident['level']}.{validation}"
            )
    return body


def _plan_de_accion(brief: dict[str, Any], version: str) -> list[str]:
    if not brief["incidents"]:
        return [
            "No hay incidentes sobre los que ejecutar un plan de acción en este export."
        ]
    body: list[str] = []
    for incident in brief["incidents"]:
        categories = [item for item in incident["categories"] if item in INVESTIGATE_ES]
        investigate = [INVESTIGATE_ES[category] for category in categories]
        contain = [CONTAIN_ES[category] for category in categories]
        remediate = [REMEDIATE_ES[category] for category in categories]
        if incident["requires_validation"]:
            investigate.insert(0, VALIDATION_INVESTIGATE)
            contain.insert(0, VALIDATION_CONTAIN)
        account = (
            f" ({incident['id']})" if version == "tecnica" else ""
        )
        body.extend(
            [
                f"{incident['title']}{account}: criticidad {incident['level']}",
                f"Investigar: {_join_semicolon(investigate)}.",
                f"Contener: {_join_semicolon(contain)}.",
                f"Remediar: {_join_semicolon(remediate)}.",
            ]
        )
    return body


def _recomendaciones_generales(brief: dict[str, Any], version: str) -> list[str]:
    covered = set(brief["scope"]["categories_covered"])
    duration = _minutes_label(brief["scope"]["duration_minutes"])
    items = [
        recommendation[version].format(duration=duration)
        for recommendation in RECOMMENDATIONS
        if recommendation["categories"] is None
        or recommendation["categories"] & covered
    ]
    return [f"• {_sentence(item)}" for item in items]


def _limitaciones_analisis(brief: dict[str, Any], version: str) -> list[str]:
    scope = brief["scope"]
    missing = scope["categories_uncovered_labels"]
    if missing:
        coverage_note = (
            f" En este export no se identificaron hallazgos en "
            f"{count_es(len(missing))} de las 6 categorías ({_join_and(missing)})."
        )
    else:
        coverage_note = " Las 6 categorías tienen al menos un hallazgo en estos registros."
    service_accounts = scope["service_name_accounts"]
    if service_accounts:
        account_note = (
            f" Por convención de nombre, {_join_and(service_accounts)} podría ser una "
            "cuenta de servicio, pero el registro no lo confirma y se contabiliza como "
            "cuenta humana."
        )
    else:
        account_note = ""
    return [
        f"1. Ventana de datos de {_minutes_label(scope['duration_minutes'])} de un único "
        f"día ({scope['date']}): no permite establecer recurrencia, persistencia histórica "
        "ni tendencia.",
        "2. Sin acceso a plataformas (SIEM/EDR/DNS/netflow): el análisis se limita a los "
        "campos exportados en el archivo; no se consultó telemetría adicional.",
        "3. Los payloads ofuscados aparecen redactados en el origen "
        "([REDACTED_SYNTHETIC], <base64_redacted>): no es posible determinar qué ejecutaba "
        "el comando codificado ni cuál era el canal de mando y control.",
        "4. La columna Source_IP no resuelve a un nombre de equipo: la relación "
        "origen y destino se toma del texto del evento cuando está disponible.",
        "5. Las direcciones externas pertenecen a rangos de documentación (RFC 5737): no "
        "hay atribución geográfica ni reputación real, porque no se consultó inteligencia "
        "de amenazas.",
        "6. La columna Severity del SIEM es inconsistente y no se usa para clasificar; la "
        "criticidad proviene de la matriz impacto × confianza.",
        "7. La ausencia de un hallazgo no prueba ausencia de compromiso: solo indica que no "
        f"hay evidencia en este export.{coverage_note}",
        "8. El export no declara el tipo de cuenta: las cuentas de servicio se identifican "
        "por convención de nombre y no por un atributo del dato; el análisis no puede "
        f"afirmar cuáles lo son sin ese atributo.{account_note}",
    ]


_BUILDERS = (
    _resumen_ejecutivo,
    _hallazgos_identificados,
    _explicacion_tecnica,
    _evidencias_logs,
    _criticidad_justificacion,
    _impacto_organizacion,
    _plan_de_accion,
    _recomendaciones_generales,
    _limitaciones_analisis,
)


def render_sections(brief: dict[str, Any], version: str) -> list[dict[str, Any]]:
    """Render the nine deterministic sections of one audience version."""
    if version not in VERSIONS:
        raise ValueError(f"Versión de informe no válida: {version}")
    sections = []
    for number, ((key, title), build) in enumerate(
        zip(SECTION_SPECS, _BUILDERS, strict=True), start=1
    ):
        sections.append(
            {
                "number": number,
                "key": key,
                "title": f"{number}. {title}",
                "body": build(brief, version),
                "narrative": NARRATIVE_TEMPLATE,
                "narrative_reason": None,
            }
        )
    return sections
