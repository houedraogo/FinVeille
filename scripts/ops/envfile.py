"""Édition sûre de fichiers d'environnement (format docker env_file / .env).

Conçu pour la rotation de secrets : la nouvelle valeur n'est JAMAIS passée en argument de
ligne de commande (visible dans `ps`), JAMAIS affichée ni journalisée. Elle est lue sur
l'entrée standard ou dans un fichier à permissions restreintes.

Usage en ligne de commande (la valeur arrive par stdin) :
    python envfile.py set FICHIER CLE            < fichier_valeur_0600
    python envfile.py set-url-password FICHIER CLE [CLE...]  < fichier_valeur_0600
    python envfile.py names FICHIER              # liste des noms de variables, jamais les valeurs
    python envfile.py get FICHIER CLE            # usage interne uniquement (substitution de commande)
"""
from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import quote

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvFileError(ValueError):
    pass


def _validate(key: str, value: str) -> None:
    if not _KEY_RE.match(key):
        raise EnvFileError(f"Nom de variable invalide: {key!r}")
    if value == "" or "\n" in value or "\r" in value or "\x00" in value:
        raise EnvFileError("Valeur vide ou contenant un saut de ligne / caractère nul")


def _write_atomic(path: Path, content: str) -> None:
    """Écrit sans jamais laisser le fichier plus permissif qu'avant, puis le restreint à 0600."""
    tmp = path.with_name(path.name + ".tmp-rotation")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # Windows : pas de bits POSIX
        pass


def set_env_value(path: str | Path, key: str, value: str) -> bool:
    """Remplace (ou ajoute) KEY=value. Renvoie True si la variable existait déjà."""
    path = Path(path)
    _validate(key, value)
    text = path.read_bytes().decode("utf-8") if path.exists() else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline) if text else []
    found = False
    for index, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}\s*=", line):
            lines[index] = f"{key}={value}"
            found = True
    if not found:
        if lines and lines[-1] == "":
            lines.insert(len(lines) - 1, f"{key}={value}")
        else:
            lines.append(f"{key}={value}")
    _write_atomic(path, newline.join(lines))
    return found


_URL_CRED_RE = re.compile(r"^(?P<prefix>[A-Za-z0-9+.-]+://[^:@/\s]+:)(?P<password>[^@\s]*)(?P<suffix>@.*)$")


def set_url_password(path: str | Path, key: str, new_password: str) -> bool:
    """Remplace uniquement le mot de passe d'une URL `schéma://utilisateur:motdepasse@hôte/...`."""
    path = Path(path)
    _validate(key, new_password)
    text = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    changed = False
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*{re.escape(key)}\s*=)(.*)$", line)
        if not match:
            continue
        url = _URL_CRED_RE.match(match.group(2).strip())
        if not url:
            raise EnvFileError(f"{key} ne contient pas d'URL avec identifiants à mettre à jour")
        lines[index] = f"{match.group(1)}{url.group('prefix')}{quote(new_password, safe='')}{url.group('suffix')}"
        changed = True
    if changed:
        _write_atomic(path, newline.join(lines))
    return changed


def variable_names(path: str | Path) -> list[str]:
    names = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match:
            names.append(match.group(1))
    return names


def get_env_value(path: str | Path, key: str) -> str:
    """Valeur d'une variable (usage interne : capturée dans une variable shell, jamais affichée)."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^\s*{re.escape(key)}\s*=(.*)$", line)
        if match:
            return match.group(1)
    raise EnvFileError(f"{key} absent de {path}")


def _read_value() -> str:
    value = sys.stdin.read()
    return value[:-1] if value.endswith("\n") else value


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    command = argv[1]
    if command == "names":
        print("\n".join(variable_names(argv[2])))
        return 0
    if command == "get" and len(argv) == 4:
        # À n'utiliser que dans une substitution de commande : VALEUR="$(python3 envfile.py get F K)"
        sys.stdout.write(get_env_value(argv[2], argv[3]))
        return 0
    if command == "set" and len(argv) == 4:
        existed = set_env_value(argv[2], argv[3], _read_value())
        print(f"{argv[3]}: {'mis à jour' if existed else 'ajouté'} dans {argv[2]}")
        return 0
    if command == "set-url-password" and len(argv) >= 4:
        password = _read_value()
        for key in argv[3:]:
            ok = set_url_password(argv[2], key, password)
            print(f"{key}: {'mot de passe mis à jour' if ok else 'absent'} dans {argv[2]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except EnvFileError as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        sys.exit(1)
