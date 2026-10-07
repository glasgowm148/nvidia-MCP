"""Redact account fields, signed URLs and credentials before returning diagnostics.

Redaction is defence in depth, not a guarantee. Rules, applied in order:

* ``SECRET`` classifies setting ids, dict keys, XML tags and attribute names. It combines
  substring rules (``password``, ``token``, ``api_key`` ...) with segment rules that match a
  whole trailing segment such as ``rd.auth``, ``trakt.refresh`` or ``<pass>``.
* Header rules (``Authorization:``, ``Cookie:``, ``Bearer``/``Basic`` values).
* JSON/Python-style quoted pairs (``"access_token": "abc"``, ``'pin': 1234``).
* ``key=value`` / ``key: value`` pairs, including quoted keys.
* URL userinfo (``smb://user:pass@host``) and secret query parameters for any scheme;
  http(s)/smb/ftp URLs are withheld entirely because signed stream URLs are common.
* Email addresses.
"""

import json
import re
import xml.etree.ElementTree as ET

from defusedxml.ElementTree import fromstring

# Substrings that are credential-like anywhere in an identifier.
_SUBSTRING = (
    r"password|passwd|passcode|token|secret|api[_.-]?key|authorization|cookie"
    r"|refresh[_.-]?(?:token|key)|credential|client[_.-]?id|username|email|account|lockcode"
)
# Words that are credential-like only as a whole trailing segment (``rd.auth``, ``pin``).
_SEGMENT_WORDS = (
    r"pass|passwd|password|passcode|pin|user|username|auth|refresh|token|secret|key"
    r"|apikey|api_key|client_secret|lockcode|cookie|session|sessionid|sid"
)
SECRET = re.compile(rf"{_SUBSTRING}|(?:^|[._-])(?:{_SEGMENT_WORDS})$", re.I)
# XML element names that hold a credential value. ``<key>`` is excluded: keymaps use it.
XML_SECRET_EXEMPT = {"key"}

URL = re.compile(r"(?:https?|smb|ftp)://[^\s<>\"']+", re.I)
USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/@<>\"':]+(?::[^\s/@<>\"']*)?@")
QUERY = re.compile(
    r"(?i)([?&;](?:access_token|refresh_token|id_token|token|api[_-]?key|apikey|key|password"
    r"|pass|passwd|pin|auth|authorization|signature|sig|secret|client_secret|code|session"
    r"|sessionid|sid|cookie|user|username)=)[^&\s\"'<>#]+"
)
HEADER = re.compile(
    r"(?im)\b((?:proxy-)?authorization|cookie|set-cookie|x-api-key|x-auth-token|api-key)"
    r"(\s*:\s*)[^\r\n,}\"']+"
)
BEARER = re.compile(r"(?i)\b(Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]{4,}")
QUOTED_PAIR = re.compile(
    r"""(?x)
    (?P<q>["'])(?P<key>[^"'\\\s]{1,80})(?P=q)\s*:\s*
    (?P<value>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|-?\d[\d.]*)
    """
)
PAIR = re.compile(
    rf"""(?ix)
    ((?<![A-Za-z0-9])["']?
      (?:[A-Za-z0-9_.-]*?(?:{_SUBSTRING})[A-Za-z0-9_]*
        |(?:[A-Za-z0-9_.-]*[._-])?(?:{_SEGMENT_WORDS}))
     ["']?\s*[=:]\s*["']?)
    (?!\[redacted\])([^\s,;"'&}}<>]+)
    """
)
MAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
# Plain-text XML rules for logs/snippets that are not a parseable document.
XML_OPEN = re.compile(r"<(?P<tag>[A-Za-z_][\w.-]*)(?P<attrs>\s[^<>]*?)?(?P<end>/?)>")
XML_ATTR = re.compile(r"""(?P<name>[A-Za-z_][\w.:-]*)(?P<eq>\s*=\s*)(?P<value>"[^"]*"|'[^']*')""")
XML_ELEMENT = re.compile(
    r"<(?P<tag>[A-Za-z_][\w.-]*)(?P<attrs>\s[^<>]*?)?>(?P<body>[^<]+)</(?P=tag)\s*>"
)


def _quoted(match):
    if not SECRET.search(match["key"]):
        return match[0]
    value = match["value"]
    quote = value[0] if value[0] in "\"'" else ""
    return match[0][: match.start("value") - match.start()] + f"{quote}[redacted]{quote}"


def _xml_id(attrs) -> str:
    for match in XML_ATTR.finditer(attrs or ""):
        if match["name"].lower() == "id":
            return match["value"][1:-1]
    return ""


def _xml_open(match):
    attrs = match["attrs"]
    if not attrs:
        return match[0]
    secret_id = is_secret(_xml_id(attrs))

    def attr(m):
        name = m["name"]
        if SECRET.search(name) or (secret_id and name.lower() in ("value", "default")):
            quote = m["value"][0]
            return f"{name}{m['eq']}{quote}[redacted]{quote}"
        return m[0]

    return f"<{match['tag']}{XML_ATTR.sub(attr, attrs)}{match['end']}>"


def _xml_element(match):
    if (_secret_tag(match["tag"]) or is_secret(_xml_id(match["attrs"]))) and match["body"].strip():
        return match[0].replace(">" + match["body"] + "<", ">[redacted]<", 1)
    return match[0]


def _credential_rules(value: str) -> str:
    value = XML_ELEMENT.sub(_xml_element, value)
    value = XML_OPEN.sub(_xml_open, value)
    value = USERINFO.sub(r"\1[redacted]@", value)
    value = QUERY.sub(r"\1[redacted]", value)
    value = HEADER.sub(r"\1\2[redacted]", value)
    value = BEARER.sub(r"\1 [redacted]", value)
    value = QUOTED_PAIR.sub(_quoted, value)
    return PAIR.sub(r"\1[redacted]", value)


def text(value: str, known=()) -> str:
    for secret in sorted((s for s in known if s and len(s) >= 8), key=len, reverse=True):
        value = value.replace(secret, "[redacted]")
    value = _credential_rules(value)
    value = URL.sub("[URL redacted]", value)
    return MAIL.sub("[email redacted]", value)


def contains_secret(value: str) -> bool:
    """True when credential rules (not the blanket URL/email rules) would change ``value``."""
    return _credential_rules(value) != value


def secret_fields(content: str, kind: str):
    """Credential values in a parsed XML/JSON document, for detecting edits that touch them."""
    found = []
    if kind == ".xml":
        for node in fromstring(content).iter():
            if is_secret(node.get("id", "")) or _secret_tag(node.tag):
                for child in node.iter():
                    found.append(
                        (
                            child.tag,
                            node.get("id"),
                            child.text,
                            child.get("value"),
                            child.get("default"),
                        )
                    )
            found += [(node.tag, key, node.get(key)) for key in node.attrib if SECRET.search(key)]
    elif kind == ".json":

        def walk(value, path):
            if isinstance(value, dict):
                secret_id = is_secret(value.get("id", ""))
                for key, item in value.items():
                    if SECRET.search(str(key)) or (secret_id and key in ("value", "default")):
                        found.append((path, key, json.dumps(item, sort_keys=True)))
                    else:
                        walk(item, path + (key,))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, path + (index,))

        walk(json.loads(content), ())
    return found


def is_secret(identifier) -> bool:
    return bool(SECRET.search(str(identifier or "")))


def scrub(value, known=()):
    if isinstance(value, dict):
        sensitive = bool(
            value.get("secret") or value.get("sensitive") or value.get("is_secret")
        ) or is_secret(value.get("id", ""))
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


def _secret_tag(tag) -> bool:
    tag = str(tag)
    return tag.lower() not in XML_SECRET_EXEMPT and bool(SECRET.search(tag))


def file_text(value: str, known=()) -> str:
    if value.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(scrub(json.loads(value), known), indent=2)
        except ValueError:
            if SECRET.search(value) or QUOTED_PAIR.search(value):
                return "[Malformed JSON containing sensitive fields; raw contents withheld]"
    if value.lstrip().startswith("<"):
        try:
            root = fromstring(value)
            for node in root.iter():
                if is_secret(node.get("id", "")) or _secret_tag(node.tag):
                    for child in node.iter():
                        if child.text and child.text.strip():
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
            if SECRET.search(value) or re.search(rf"<(?:{_SEGMENT_WORDS})\b", value, re.I):
                return "[Malformed XML containing sensitive fields; raw contents withheld]"
    return text(value, known)
