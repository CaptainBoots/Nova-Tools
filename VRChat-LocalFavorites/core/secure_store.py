"""
core/secure_store.py
──────────────────────
Persists the VRChat session cookie using one of three strategies,
selectable in Settings ("secure_storage_mode" in config):

  "keyring"         — OS credential store (Windows Credential Manager /
                       macOS Keychain / Linux Secret Service) via the
                       `keyring` package. No extra password needed at
                       launch; protected by your OS login session.
  "master_password" — an encrypted blob on disk (AES-256-GCM). The key
                       is derived (PBKDF2-HMAC-SHA256) from a password
                       typed once per launch — that password itself is
                       NEVER written to disk anywhere, only used
                       in-memory to derive the key each time.
  "none"            — nothing is ever persisted; log in to VRChat fresh
                       every launch.

Pure backend — no Qt imports here (§3 point 3 of the porting guide).
ui/master_password_dialog.py is the only place allowed to prompt for
the password and call into password-manager CLIs; this module only
ever handles bytes/dicts.
"""

from __future__ import annotations

import base64
import binascii
import json
import os

try:
    import keyring
except ImportError:  # keyring is optional — "master_password"/"none" modes don't need it
    keyring = None

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

KEYRING_SERVICE = "vrchat-social-logger"
KEYRING_USERNAME = "session-cookies"

# OWASP's current (2023+) floor for PBKDF2-HMAC-SHA256 is 600,000
# iterations; we use a slightly lower figure to keep unlock snappy on
# older hardware while staying well above the pre-2023 100k baseline.
# Bump this over time as hardware gets faster — it only affects newly
# written blobs, old ones keep working since the iteration count travels
# with the blob itself.
PBKDF2_ITERATIONS = 480_000


class WrongPassword(Exception):
    """The blob exists but the supplied password didn't decrypt it.
    Deliberately the ONLY failure mode _decrypt ever surfaces distinctly
    — see the comment on load_master_password() for why."""


class CorruptBlob(Exception):
    """The blob file exists and is readable, but isn't a valid blob
    (bad JSON, missing fields, wrong-length nonce, etc.) — e.g. a
    write that got interrupted mid-save, a disk error, or manual
    tampering. This is deliberately NOT the same case as a wrong
    password: retrying with a different password can't fix a corrupt
    file, so callers should stop retrying and fall back to a fresh
    login instead of looping."""


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
    return kdf.derive(password.encode("utf-8"))


def _encrypt(plaintext: bytes, password: str) -> dict:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return {
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt(blob: dict, password: str) -> bytes:
    try:
        salt = base64.b64decode(blob["salt"])
        nonce = base64.b64decode(blob["nonce"])
        ciphertext = base64.b64decode(blob["ciphertext"])
        iterations = blob.get("iterations", PBKDF2_ITERATIONS)
    except (KeyError, TypeError, binascii.Error) as exc:
        raise CorruptBlob(f"Session file is malformed: {exc}")

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    key = kdf.derive(password.encode("utf-8"))
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        # AES-GCM's tag check fails for a wrong key OR a corrupted/
        # tampered blob — we deliberately don't try to tell those apart
        # (and never echo the attempted password back anywhere) so a
        # failure message can't be used to fish for info about the blob.
        raise WrongPassword("Incorrect password.")
    except ValueError as exc:
        # Malformed nonce/ciphertext length, etc. — a corrupt file, not
        # a wrong password (a wrong password produces InvalidTag, not
        # ValueError, since the key derivation itself always succeeds).
        raise CorruptBlob(f"Session file is malformed: {exc}")


class SecureStore:
    def __init__(self, blob_path: str):
        self.blob_path = blob_path

    # ── keyring mode ──────────────────────────────────────────────────

    def save_keyring(self, cookies: dict):
        if keyring is None:
            raise RuntimeError("The 'keyring' package is not installed.")
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, json.dumps(cookies))

    def load_keyring(self) -> dict | None:
        if keyring is None:
            return None
        try:
            raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except Exception:
            return None  # backend unavailable (e.g. no Secret Service running on this Linux session)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def clear_keyring(self):
        if keyring is None:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except Exception:
            pass

    # ── master-password mode ─────────────────────────────────────────

    def has_master_password_blob(self) -> bool:
        return os.path.exists(self.blob_path)

    def save_master_password(self, cookies: dict, password: str):
        plaintext = json.dumps(cookies).encode("utf-8")
        blob = _encrypt(plaintext, password)
        os.makedirs(os.path.dirname(self.blob_path), exist_ok=True)
        with open(self.blob_path, "w", encoding="utf-8") as f:
            json.dump(blob, f)

    def load_master_password(self, password: str) -> dict:
        """Raises WrongPassword on a bad password, CorruptBlob if the
        file exists but isn't usable (bad JSON, missing fields, etc —
        never worth retrying with a different password), or
        FileNotFoundError if there's no blob yet. Callers should let
        all three propagate distinctly rather than treating them the
        same, so the UI can tell 'nothing saved yet' apart from 'wrong
        password' apart from 'this file is broken, stop asking'."""
        with open(self.blob_path, "r", encoding="utf-8") as f:
            try:
                blob = json.load(f)
            except json.JSONDecodeError as exc:
                raise CorruptBlob(f"Session file is not valid JSON: {exc}")
        if not isinstance(blob, dict):
            raise CorruptBlob("Session file has an unexpected format.")
        plaintext = _decrypt(blob, password)  # raises WrongPassword or CorruptBlob
        try:
            return json.loads(plaintext.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CorruptBlob(f"Decrypted session data is not valid: {exc}")

    def clear_master_password(self):
        if os.path.exists(self.blob_path):
            try:
                os.remove(self.blob_path)
            except OSError:
                pass
