"""Redact account fields, signed URLs and credentials before returning diagnostics."""

import json
import re
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import fromstring

SECRET = re.compile(
    r"password|passwd|token|secret|api[_.-]?key|authorization|cookie|refresh[_.-]?(?:token|key)|credential|client[_.-]?id|username|email|account|passcode",
    re.I,
)
URL = re.compile(r"(?:https?|smb|ftp)://[^\s<>\"']+", re.I)
PAIR = re.compile(
    r"(?i)((?:password|passwd|token|secret|api[_.-]?key|authorization|cookie|refresh_token|client_secret|email)\s*[=:]\s*)([^\s,;]+)"
)
MAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
BEARER = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")


def text(value: str, known=()) -> str:
    for secret in sorted((s for s in known if s and len(s) >= 8), key=len, reverse=True):
        value = value.replace(secret, "[redacted]")
    value = URL.sub("[URL redacted]", value)
    value = BEARER.sub(r"\1 [redacted]", value)
    value = PAIR.sub(r"\1[redacted]", value)
    return MAIL.sub("[email redacted]", value)


def scrub(value, known=()):
    if isinstance(value, dict):
        sensitive = bool(
            value.get("secret") or value.get("sensitive") or value.get("is_secret")
        ) or bool(SECRET.search(str(value.get("id", ""))))
        return {
            k: "[redacted]"
            if (
                SECRET.search(str(k))
                or (sensitive and k in ("value", "current", "default", "label2"))
            )
            and not isinstance(v, bool)
            and v is not None
            and not (str(k).lower() in ("accounts", "account") and isinstance(v, (dict, list)))
            else scrub(v, known)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [scrub(v, known) for v in value]
    return text(value, known) if isinstance(value, str) else value


def file_text(value: str, known=()) -> str:
    if value.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(scrub(json.loads(value), known), indent=2)
        except ValueError:
            if SECRET.search(value):
                return "[Malformed JSON containing sensitive fields; raw contents withheld]"
    if value.lstrip().startswith("<"):
        try:
            root = fromstring(value)
            for node in root.iter():
                if SECRET.search(str(node.get("id", ""))) or SECRET.search(node.tag):
                    for child in node.iter():
                        child.text = "[redacted]"
                        for key in ("value", "default"):
                            if key in child.attrib:
                                child.set(key, "[redacted]")
                for key in list(node.attrib):
                    if SECRET.search(key):
                        node.set(key, "[redacted]")
            value = ET.tostring(root, encoding="unicode")
        except Exception:
            # Malformed settings must not leak credential values via raw diagnostics.
            if SECRET.search(value):
                return "[Malformed XML containing sensitive fields; raw contents withheld]"
    return text(value, known)
