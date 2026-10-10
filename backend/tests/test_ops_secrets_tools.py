"""Outils d'exploitation : édition sûre des .env et expurgation des transcriptions."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / "scripts" / "ops"
sys.path.insert(0, str(OPS))

import envfile  # noqa: E402
import redact_transcripts as redact  # noqa: E402

FAKE_STRIPE = "sk_live_" + "Ab12" * 6
FAKE_PW = "Zx9" + "kQ2w" * 4


# --- envfile ----------------------------------------------------------------

def test_set_replaces_one_variable_and_keeps_everything_else(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nSTRIPE_SECRET_KEY=old\n# commentaire\nB=2\n", encoding="utf-8")
    assert envfile.set_env_value(env, "STRIPE_SECRET_KEY", "new-value-123") is True
    assert env.read_text(encoding="utf-8") == "A=1\nSTRIPE_SECRET_KEY=new-value-123\n# commentaire\nB=2\n"


def test_set_adds_a_missing_variable_and_preserves_crlf(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"A=1\r\nB=2\r\n")
    assert envfile.set_env_value(env, "NEW_VAR", "xyz") is False
    assert env.read_bytes() == b"A=1\r\nB=2\r\nNEW_VAR=xyz\r\n"


def test_values_with_special_characters_are_written_verbatim(tmp_path):
    env = tmp_path / ".env"
    env.write_text("P=old\n", encoding="utf-8")
    tricky = "a$b#c=d&e%f'g\"h\\i"
    envfile.set_env_value(env, "P", tricky)
    assert env.read_text(encoding="utf-8") == f"P={tricky}\n"


@pytest.mark.parametrize("value", ["", "ligne1\nligne2", "a\x00b"])
def test_invalid_values_are_refused_and_file_untouched(tmp_path, value):
    env = tmp_path / ".env"
    env.write_text("P=old\n", encoding="utf-8")
    with pytest.raises(envfile.EnvFileError):
        envfile.set_env_value(env, "P", value)
    assert env.read_text(encoding="utf-8") == "P=old\n"


def test_url_password_is_replaced_without_touching_user_host_or_path(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "DATABASE_URL=postgresql+asyncpg://finveille:OLD@postgres:5432/finveille\n"
        "DATABASE_SYNC_URL=postgresql://finveille:OLD@postgres:5432/finveille\nOTHER=keep\n", encoding="utf-8")
    envfile.set_url_password(env, "DATABASE_URL", "N3wPass")
    envfile.set_url_password(env, "DATABASE_SYNC_URL", "N3wPass")
    assert env.read_text(encoding="utf-8").splitlines() == [
        "DATABASE_URL=postgresql+asyncpg://finveille:N3wPass@postgres:5432/finveille",
        "DATABASE_SYNC_URL=postgresql://finveille:N3wPass@postgres:5432/finveille",
        "OTHER=keep",
    ]


def test_url_password_is_percent_encoded(tmp_path):
    env = tmp_path / ".env"
    env.write_text("U=postgresql://u:old@h/db\n", encoding="utf-8")
    envfile.set_url_password(env, "U", "p@ss/w:rd")
    assert env.read_text(encoding="utf-8") == "U=postgresql://u:p%40ss%2Fw%3Ard@h/db\n"


def test_names_never_include_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=secret1\nB=secret2\n# C=x\n", encoding="utf-8")
    assert envfile.variable_names(env) == ["A", "B"]


def test_cli_set_reads_the_value_from_stdin_and_prints_no_value(tmp_path, monkeypatch, capsys):
    import io

    env = tmp_path / ".env"
    env.write_text("TOKEN=old\n", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO("brand-new-secret\n"))
    assert envfile.main(["envfile.py", "set", str(env), "TOKEN"]) == 0
    out = capsys.readouterr().out
    assert "brand-new-secret" not in out and "old" not in out
    assert env.read_text(encoding="utf-8") == "TOKEN=brand-new-secret\n"


# --- expurgation ------------------------------------------------------------

def test_assignments_urls_and_tokens_are_redacted_but_names_are_kept():
    text = (f"STRIPE_SECRET_KEY={FAKE_STRIPE} SMTP_PASSWORD={FAKE_PW} "
            f"DATABASE_URL=postgresql://user:{FAKE_PW}@db:5432/x token {FAKE_STRIPE}")
    out = redact.redact_text(text)
    assert FAKE_STRIPE not in out and FAKE_PW not in out
    assert "STRIPE_SECRET_KEY=[REDACTED:variable]" in out
    assert "SMTP_PASSWORD=[REDACTED:variable]" in out
    assert "postgresql://user:[REDACTED:url]@db:5432/x" in out


def test_placeholders_and_non_secret_variables_are_left_alone():
    text = "APP_KEY=<valeur> POSTGRES_PASSWORD=*** DB_HOST=postgres STRIPE_PRICE_PRO=price_1ABC KAFUNDO_SYNC_CREATE_CAP=0"
    assert redact.redact_text(text) == text


def test_laravel_app_key_with_base64_characters_is_redacted():
    out = redact.redact_text("APP_KEY=base64:AbCdEf0123456789+/AbCdEf0123456789=")
    assert out == "APP_KEY=[REDACTED:variable]"


def test_jsonl_escaped_text_stays_valid_json():
    line = json.dumps({"output": f"POSTGRES_PASSWORD={FAKE_PW}\nSMTP_PASSWORD={FAKE_PW}\n\"quoted\" ok"}) + "\n"
    out = redact.redact_text(line)
    parsed = json.loads(out)
    assert FAKE_PW not in parsed["output"] and "POSTGRES_PASSWORD=[REDACTED:variable]" in parsed["output"]
    assert '"quoted" ok' in parsed["output"]


def _write_transcript(path: Path, age_hours: float = 48):
    lines = [json.dumps({"n": i, "text": "rien à signaler"}) for i in range(5)]
    lines.insert(2, json.dumps({"n": 99, "text": f"docker env: STRIPE_SECRET_KEY={FAKE_STRIPE} SMTP_PASSWORD={FAKE_PW}"}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))


def test_simulation_changes_nothing_and_apply_replaces_atomically(tmp_path, capsys):
    transcript = tmp_path / "session.jsonl"
    _write_transcript(transcript)
    before = transcript.read_bytes()
    assert redact.main([str(tmp_path)]) == 0
    assert transcript.read_bytes() == before                      # simulation : intact
    assert redact.main([str(tmp_path), "--apply"]) == 0
    after = transcript.read_text(encoding="utf-8")
    assert FAKE_STRIPE not in after and FAKE_PW not in after
    assert len(after.splitlines()) == 6 and all(json.loads(line) for line in after.splitlines())
    printed = capsys.readouterr().out
    assert FAKE_STRIPE not in printed and FAKE_PW not in printed  # jamais d'affichage de valeur
    assert not list(tmp_path.glob("*.redacting"))                  # pas de fichier temporaire résiduel


def test_recent_files_are_skipped_unless_explicitly_included(tmp_path):
    transcript = tmp_path / "active.jsonl"
    _write_transcript(transcript, age_hours=0.1)
    redact.main([str(tmp_path), "--apply"])
    assert FAKE_PW in transcript.read_text(encoding="utf-8")       # ignoré : session probablement active
    redact.main([str(tmp_path), "--apply", "--include-recent"])
    assert FAKE_PW not in transcript.read_text(encoding="utf-8")


def test_a_file_without_secrets_is_not_rewritten(tmp_path):
    transcript = tmp_path / "clean.jsonl"
    transcript.write_text(json.dumps({"text": "rien"}) + "\n", encoding="utf-8")
    old = time.time() - 48 * 3600
    os.utime(transcript, (old, old))
    mtime = transcript.stat().st_mtime
    redact.main([str(tmp_path), "--apply"])
    assert transcript.stat().st_mtime == mtime


def test_all_files_mode_handles_extensionless_snapshots_and_skips_binaries(tmp_path):
    snapshot = tmp_path / "58ddc0c13008b2bb@v1"
    snapshot.write_text(f"APP_ENV=production\nPOSTGRES_PASSWORD={FAKE_PW}\n", encoding="utf-8")
    binary = tmp_path / "image@v1"
    binary.write_bytes(b"\x89PNG\x00\x00POSTGRES_PASSWORD=" + FAKE_PW.encode())
    for f in (snapshot, binary):
        old = time.time() - 48 * 3600
        os.utime(f, (old, old))
    assert redact.main([str(tmp_path), "--all-files", "--apply"]) == 0
    redacted = snapshot.read_text(encoding="utf-8")
    assert FAKE_PW not in redacted
    assert redacted.startswith("APP_ENV=production\nPOSTGRES_PASSWORD=[REDACTED:variable]")
    assert FAKE_PW.encode() in binary.read_bytes()   # binaire : non touché
