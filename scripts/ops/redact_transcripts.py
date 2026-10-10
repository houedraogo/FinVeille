"""Expurge les secrets des transcriptions locales (JSONL) sans jamais les afficher.

Pourquoi : les sorties d'outils (ex. `docker inspect`, `cat .env`) sont conservées en clair dans
les fichiers de session (~/.claude/projects/**/*.jsonl). Ce script remplace les VALEURS de
secrets par `[REDACTED:<type>]` ; les noms de variables et le reste du texte sont conservés.

Garanties
---------
* Aucune valeur n'est affichée : seuls des compteurs par type sont imprimés.
* Une copie expurgée est écrite à côté, vérifiée (chaque ligne reste du JSON valide, même
  nombre de lignes, plus aucune valeur détectable), PUIS remplace l'original (remplacement
  atomique). Si une vérification échoue, l'original n'est pas touché.
* Aucune copie NON expurgée n'est conservée (elle contiendrait les secrets) ; la copie
  expurgée remplace l'original et sert de sauvegarde exploitable.
* Les fichiers modifiés récemment (session probablement active) sont ignorés par défaut :
  les expurger pendant que l'application y écrit risquerait de les corrompre. Fermez la
  session, puis relancez avec --include-recent.

Usage :
    python redact_transcripts.py CHEMIN [CHEMIN...]            # simulation : compte seulement
    python redact_transcripts.py CHEMIN [...] --apply          # applique
    python redact_transcripts.py CHEMIN [...] --apply --include-recent
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PLACEHOLDER_PREFIXES = ("[REDACTED", "***", "<", "$", "{", "%")

# Jetons au format reconnaissable (valeur seule, sans nom de variable).
TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("stripe_webhook", re.compile(r"\bwhsec_[A-Za-z0-9]{16,}")),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
)

# NOM=valeur où le nom évoque un secret ; la valeur s'arrête à un espace, un guillemet, un \n échappé…
ASSIGNMENT = re.compile(
    r"(?P<name>\b[A-Za-z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|API_?KEY|APP_?KEY|ACCESS_?KEY|PRIVATE_?KEY|TOKEN|"
    r"ENCRYPTION_?KEY|SIGNING_?KEY|CLIENT_?SECRET|DSN)[A-Za-z0-9_]*)(?P<sep>\s*=\s*)(?P<value>[^\s\"'\\,;)}\]]{6,})",
)
# Mots de passe intégrés dans une URL : schéma://utilisateur:motdepasse@hôte
URL_CREDENTIALS = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.-]*://[^:@/\s\"'\\]+:)(?P<pw>[^@\s\"'\\/]{4,})(?P<tail>@)")
# Options de ligne de commande : -p'motdepasse', --password=xxx, PGPASSWORD=xxx (couvert par ASSIGNMENT)
CLI_PASSWORD = re.compile(r"(?P<flag>--(?:password|passwd|token|secret|api-key)[= ])(?P<value>[^\s\"'\\]{4,})")


def _is_placeholder(value: str) -> bool:
    return value.startswith(PLACEHOLDER_PREFIXES) or value.lower() in {"changeme", "password", "secret", "example"}


def redact_text(text: str, counter: Counter | None = None) -> str:
    counter = counter if counter is not None else Counter()

    def assignment(match: re.Match[str]) -> str:
        if _is_placeholder(match.group("value")):
            return match.group(0)
        counter["variable_secrete"] += 1
        return f"{match.group('name')}{match.group('sep')}[REDACTED:variable]"

    def url(match: re.Match[str]) -> str:
        if _is_placeholder(match.group("pw")):
            return match.group(0)
        counter["mot_de_passe_dans_url"] += 1
        return f"{match.group('head')}[REDACTED:url]{match.group('tail')}"

    def cli(match: re.Match[str]) -> str:
        if _is_placeholder(match.group("value")):
            return match.group(0)
        counter["option_cli"] += 1
        return f"{match.group('flag')}[REDACTED:cli]"

    text = ASSIGNMENT.sub(assignment, text)
    text = URL_CREDENTIALS.sub(url, text)
    text = CLI_PASSWORD.sub(cli, text)
    for label, pattern in TOKEN_PATTERNS:
        text, count = pattern.subn(f"[REDACTED:{label}]", text)
        if count:
            counter[label] += count
    return text


def residual_findings(text: str) -> int:
    """Nombre de valeurs encore détectables (doit être 0 après expurgation)."""
    return sum(1 for _ in _iter_matches(text))


def _iter_matches(text: str):
    for m in ASSIGNMENT.finditer(text):
        if not _is_placeholder(m.group("value")):
            yield m
    for m in URL_CREDENTIALS.finditer(text):
        if not _is_placeholder(m.group("pw")):
            yield m
    for m in CLI_PASSWORD.finditer(text):
        if not _is_placeholder(m.group("value")):
            yield m
    for _label, pattern in TOKEN_PATTERNS:
        yield from pattern.finditer(text)


def process_file(path: Path, apply: bool) -> dict:
    counter: Counter = Counter()
    lines_in = 0
    out_fd, out_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".redacting", dir=str(path.parent))
    ok = True
    reason = ""
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as source, \
            os.fdopen(out_fd, "w", encoding="utf-8", errors="surrogateescape", newline="") as target:
        for line in source:
            lines_in += 1
            new_line = redact_text(line, counter)
            if new_line != line and path.suffix == ".jsonl":
                try:
                    json.loads(new_line)
                except ValueError:
                    ok, reason = False, f"ligne {lines_in} invalide après expurgation"
                    break
            target.write(new_line)
    result = {"file": path.name, "lines": lines_in, "found": dict(counter), "applied": False, "ok": ok, "reason": reason}
    if ok:
        with open(out_name, encoding="utf-8", errors="surrogateescape", newline="") as check:
            lines_out = 0
            residual = 0
            for line in check:
                lines_out += 1
                residual += residual_findings(line)
        if lines_out != lines_in:
            ok, reason = False, "nombre de lignes différent"
        elif residual:
            ok, reason = False, f"{residual} valeur(s) encore détectable(s)"
        result.update(ok=ok, reason=reason, residual=residual)
    if ok and apply and counter:
        os.replace(out_name, path)
        result["applied"] = True
    else:
        os.unlink(out_name)
    return result


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        p = Path(item)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.jsonl")))
        elif p.is_file():
            files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--apply", action="store_true", help="remplace réellement les fichiers (sinon simulation)")
    parser.add_argument("--include-recent", action="store_true", help="inclut les fichiers modifiés il y a moins de 2 h")
    parser.add_argument("--recent-hours", type=float, default=2.0)
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    exit_code = 0
    scanned = skipped = flagged = 0
    for path in collect(args.paths):
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h < args.recent_hours and not args.include_recent:
            skipped += 1
            print(f"IGNORÉ (modifié il y a {age_h:.1f} h, session probablement active): {path.name}")
            continue
        scanned += 1
        result = process_file(path, args.apply)
        found = sum(result["found"].values())
        if found or not result["ok"]:
            flagged += 1
            status = "APPLIQUÉ" if result["applied"] else ("simulation" if result["ok"] else "ÉCHEC")
            print(f"{status}: {result['file']} — {found} valeur(s) {dict(result['found'])} sur {result['lines']} lignes"
                  + (f" — {result['reason']}" if result["reason"] else ""))
        if not result["ok"]:
            exit_code = 1
    print(f"Bilan: {scanned} fichier(s) analysé(s), {flagged} avec secrets ou en échec, {skipped} ignoré(s) (récents).")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
