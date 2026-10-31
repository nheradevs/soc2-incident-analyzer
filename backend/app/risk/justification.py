"""Rule-written Spanish justification (FSD RF3).

Every sentence is assembled from the finding's own numbers — its `Log_ID` list,
its entity counts, its time window, the volume its detector measured — plus the
matrix factors that decided the level. There is no LLM here and no generic
filler: the text always names the level, the factor that supports it and the
factor that kept it from the next level up.

Impact phrases and validation notes live in tables keyed by `(code, variant)`,
mirroring the impact table of `matrix.py`, so the wording of a rule is edited in
one place and never drifts from the level it describes.
"""

from __future__ import annotations

from typing import Any

from app.detection.context import count_es, hhmmss, minutes_between
from app.detection.models import Entities, Finding, Incident
from app.risk.matrix import (
    CONFIDENCE_LEVELS,
    LEVEL_RANK,
    LEVELS,
    RiskScore,
    external_origin,
    measured_megabytes,
    targets_file_server,
    variant_of,
)

LIST_LIMIT = 4

IMPACT_PHRASE: dict[tuple[str, str], str] = {
    ("D1a", "D1a"): (
        "{n} intentos fallidos de inicio de sesión sobre la cuenta {users}, sin ningún "
        "acceso exitoso registrado"
    ),
    ("D1b", "D1b"): (
        "password spray desde {ips}: {n} intentos fallidos repartidos en {n_users} cuentas "
        "distintas ({users})"
    ),
    ("D1c", "D1c"): (
        "fallos de inicio de sesión desde el origen externo {ips}: la línea base medida no "
        "registra ningún fallo desde fuera de la red interna"
    ),
    ("D1d", "D1d"): (
        "acceso exitoso posterior a fallos previos sobre {users} desde {ips}: compromiso de "
        "credenciales confirmado"
    ),
    ("D2", "D2"): (
        "inicio de sesión exitoso de {users} en {hosts} con origen {origin}, señalado por el "
        "detector por encima de la línea base"
    ),
    ("D3", "D3"): (
        "privilegios especiales asignados a {users} en {hosts} sobre una sesión que no es "
        "línea base"
    ),
    ("D4", "iis-apppool"): (
        "proceso interactivo lanzado por el grupo de aplicaciones de IIS en {hosts}: ejecución "
        "de comandos a través del servidor web"
    ),
    ("D4", "powershell-codificado"): (
        "ejecución de PowerShell con payload codificado y redactado en el origen: el registro "
        "muestra la ejecución, no el contenido"
    ),
    ("D4", "vssadmin-delete-shadows"): (
        "eliminación de copias de sombra con vssadmin: precursora habitual de ransomware y "
        "también usada por herramientas de respaldo"
    ),
    ("D4", "archivo-comprimido"): (
        "creación de un archivo comprimido en una ruta pública: preparación de una salida de "
        "datos"
    ),
    ("D4", "net-view"): (
        "enumeración de recursos compartidos: reconocimiento para elegir el siguiente objetivo"
    ),
    ("D4", "programdata"): (
        "ejecución desde C:\\ProgramData, una ruta escribible por usuarios sin privilegios: "
        "evasión y persistencia ligera"
    ),
    ("D4", "whoami"): (
        "ejecución de whoami: reconocimiento de identidad sin efecto sobre los datos"
    ),
    ("D5", "D5"): (
        "movimiento lateral hacia {hosts}{file_server} desde otro equipo, con accesos a "
        "recursos en los minutos siguientes"
    ),
    ("D6", "rareza"): (
        "evento de descripción única en el export: rareza sin contexto que la relacione con "
        "un ataque"
    ),
    ("D6", "lectura-masiva"): (
        "acceso masivo y regular a objetos en {hosts}: compatible con exfiltración y con una "
        "herramienta de respaldo"
    ),
    ("D6", "persistencia"): (
        "persistencia creada fuera de la ventana de mantenimiento: ejecución automática que "
        "sobrevive al reinicio y cuyo contenido no muestran los registros"
    ),
    ("D7", "D7"): (
        "transferencia saliente de {mb} medidos en {n} solicitudes proxy hacia un destino "
        "externo"
    ),
}
DEFAULT_IMPACT_PHRASE = (
    "patrón detectado por la regla {code} sobre {users} en {hosts}, cuyo alcance no está "
    "descrito por la matriz"
)

VALIDATION_NOTE: dict[tuple[str, str], str] = {
    ("D4", "vssadmin-delete-shadows"): (
        "la eliminación de copias de sombra también la ejecutan herramientas de respaldo y los "
        "registros no muestran cifrado de archivos"
    ),
    ("D6", "lectura-masiva"): (
        "la lectura masiva también la produce una herramienta de respaldo sobre el mismo "
        "recurso y los registros no muestran la salida de los datos"
    ),
}
DEFAULT_VALIDATION_NOTE = (
    "el mismo patrón también lo produce actividad administrativa o de respaldo legítima"
)

FILE_SERVER_NOTE = ", un servidor de archivos"


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _names(values: tuple[str, ...], empty: str) -> str:
    if not values:
        return empty
    shown = list(values[:LIST_LIMIT])
    hidden = len(values) - len(shown)
    text = ", ".join(shown)
    if hidden:
        text += f" y {count_es(hidden)} más"
    return text


def _entity_detail(entities: Entities) -> str:
    details: list[str] = []
    for values, singular, plural in (
        (entities.users, "cuenta", "cuentas"),
        (entities.hosts, "equipo", "equipos"),
        (entities.source_ips, "IP de origen", "IPs de origen"),
        (entities.shares, "recurso compartido", "recursos compartidos"),
    ):
        if values:
            label = _plural(len(values), singular, plural)
            details.append(f"{count_es(len(values))} {label} ({_names(values, 'sin nombre')})")
    return ", ".join(details) if details else "sin entidades identificadas"


def _megabytes_text(value: float) -> str:
    return f"{value:.1f} MB".replace(".", ",")


def _context(finding: Finding) -> dict[str, Any]:
    megabytes = measured_megabytes(finding)
    return {
        "code": finding.code,
        "title": finding.title,
        "n": count_es(len(finding.evidence)),
        "n_users": count_es(len(finding.entities.users)),
        "users": _names(finding.entities.users, "una cuenta no identificada"),
        "hosts": _names(finding.entities.hosts, "un equipo no identificado"),
        "ips": _names(finding.entities.source_ips, "origen no registrado"),
        "shares": _names(finding.entities.shares, "sin recurso compartido"),
        "origin": "externo" if external_origin(finding) else "interno",
        "mb": _megabytes_text(megabytes) if megabytes is not None else "",
        "file_server": FILE_SERVER_NOTE if targets_file_server(finding) else "",
    }


def _impact_phrase(finding: Finding) -> str:
    template = IMPACT_PHRASE.get(
        (finding.code, variant_of(finding)), DEFAULT_IMPACT_PHRASE
    )
    return template.format(**_context(finding))


def _validation_note(finding: Finding) -> str:
    return VALIDATION_NOTE.get((finding.code, variant_of(finding)), DEFAULT_VALIDATION_NOTE)


def _evidence_sentence(finding: Finding) -> str:
    evidence = finding.evidence
    first, last = evidence[0], evidence[-1]
    reference = first if first == last else f"{first}–{last}"
    origin = "externo" if external_origin(finding) else "interno"
    return (
        f"{count_es(len(evidence))} {_plural(len(evidence), 'evento', 'eventos')} de evidencia "
        f"({reference}) sobre {_entity_detail(finding.entities)}, con origen {origin}, entre "
        f"{hhmmss(finding.first_seen)} y {hhmmss(finding.last_seen)} del "
        f"{finding.first_seen:%d/%m/%Y}."
    )


def _limit_reasons(finding: Finding, score: RiskScore, next_level: str) -> list[str]:
    reasons: list[str] = []
    if score.requires_validation:
        reasons.append(
            "está marcado como «requiere validación» y no se presenta como compromiso "
            "confirmado"
        )
    if score.single_row:
        first = finding.evidence[0] if finding.evidence else "sin evidencia citada"
        reasons.append(
            f"la evidencia es una única fila ({first}) y una única fila no sostiene un patrón"
        )
    if score.confidence != CONFIDENCE_LEVELS[-1]:
        reasons.append(f"la confianza en la evidencia es {score.confidence}")
    if LEVEL_RANK[score.impact] < LEVEL_RANK[next_level]:
        reasons.append(
            f"el impacto potencial es {score.impact} y no alcanza el de «{next_level}»"
        )
    if not reasons:
        reasons.append("la combinación de impacto y confianza no alcanza el nivel siguiente")
    return reasons


def _support_sentence(
    finding: Finding, score: RiskScore, level: str, subject: str = "la evidencia"
) -> str:
    if level == LEVELS[0]:
        return (
            f"Alcanza el nivel máximo: el impacto es {score.impact} y {subject} lo sostiene "
            f"con {count_es(score.event_count)} eventos y confianza {score.confidence}."
        )
    next_level = LEVELS[LEVELS.index(level) - 1]
    return f"No alcanza «{next_level}»: {'; '.join(_limit_reasons(finding, score, next_level))}."


def _validation_sentence(finding: Finding, subject: str, label: str = "") -> str:
    reference = f" {label}:" if label else ":"
    return (
        f"Requiere validación humana{reference} {_validation_note(finding)}. Por eso {subject} "
        f"no se presenta como compromiso confirmado."
    )


def finding_justification(finding: Finding, score: RiskScore) -> str:
    """Justify one finding from its own numbers and its matrix factors."""
    parts = [
        f"Criticidad {score.level}: impacto {score.impact} × confianza {score.confidence} en "
        f"la evidencia.",
        f"Impacto: {_impact_phrase(finding)}.",
        f"Evidencia: {_evidence_sentence(finding)}",
        _support_sentence(finding, score, score.level),
    ]
    if score.requires_validation:
        parts.append(_validation_sentence(finding, "el hallazgo"))
    return " ".join(parts)


def incident_justification(
    incident: Incident,
    governing: Finding,
    governing_score: RiskScore,
    level: str,
    validated_governing: Finding | None = None,
) -> str:
    """Justify an incident as the level of its most severe finding.

    `validated_governing` is one of the findings that set the incident level and
    is marked `requires_validation`; when present, the incident must state that
    it is not a confirmed compromise (FSD §8, INC-6).
    """
    parts = [
        f"Criticidad {level}: el incidente hereda el nivel del hallazgo más grave "
        f"({governing.code}, «{governing.title}», criticidad {governing_score.level}): "
        f"{_impact_phrase(governing)}.",
        f"Agrupa {count_es(len(incident.findings))} "
        f"{_plural(len(incident.findings), 'hallazgo', 'hallazgos')} correlacionados y "
        f"{count_es(incident.event_count)} eventos entre {hhmmss(incident.first_seen)} y "
        f"{hhmmss(incident.last_seen)} "
        f"({minutes_between(incident.first_seen, incident.last_seen)} min) del "
        f"{incident.first_seen:%d/%m/%Y}, con {_entity_detail(incident.entities)}.",
        _support_sentence(governing, governing_score, level, "el hallazgo que lo fija"),
    ]
    if validated_governing is not None:
        parts.append(
            _validation_sentence(
                validated_governing,
                "el incidente",
                label=f"el hallazgo {validated_governing.code} que sostiene ese nivel",
            )
        )
    elif incident.requires_validation:
        parts.append(
            "Parte del incidente requiere validación humana y no se presenta como confirmado."
        )
    return " ".join(parts)
