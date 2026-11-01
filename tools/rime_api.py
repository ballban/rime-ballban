# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""A minimal ctypes binding to librime, enough to deploy build/rime and read the candidates for typed keys.

librime allows one engine per process with fixed folders, so create one Rime object per process.
The library comes from RIME_LIB, else from deps/librime (tools/fetch_deps.py).
"""

import ctypes
import os
import platform
import shutil
from ctypes import POINTER, Structure, c_char_p, c_int, c_size_t, c_void_p
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "rime"
USER = ROOT / "build" / "test-user"
SCHEMA = "ballban"


class RimeTraits(Structure):
    _fields_ = [
        ("data_size", c_int),
        ("shared_data_dir", c_char_p),
        ("user_data_dir", c_char_p),
        ("distribution_name", c_char_p),
        ("distribution_code_name", c_char_p),
        ("distribution_version", c_char_p),
        ("app_name", c_char_p),
        ("modules", c_void_p),
        ("min_log_level", c_int),
        ("log_dir", c_char_p),
        ("prebuilt_data_dir", c_char_p),
        ("staging_dir", c_char_p),
    ]


class RimeComposition(Structure):
    _fields_ = [
        ("length", c_int),
        ("cursor_pos", c_int),
        ("sel_start", c_int),
        ("sel_end", c_int),
        ("preedit", c_char_p),
    ]


class RimeCandidate(Structure):
    _fields_ = [("text", c_char_p), ("comment", c_char_p), ("reserved", c_void_p)]


class RimeMenu(Structure):
    _fields_ = [
        ("page_size", c_int),
        ("page_no", c_int),
        ("is_last_page", c_int),
        ("highlighted_candidate_index", c_int),
        ("num_candidates", c_int),
        ("candidates", POINTER(RimeCandidate)),
        ("select_keys", c_char_p),
    ]


class RimeContext(Structure):
    _fields_ = [
        ("data_size", c_int),
        ("composition", RimeComposition),
        ("menu", RimeMenu),
        ("commit_text_preview", c_char_p),
        ("select_labels", c_void_p),
    ]


class RimeCommit(Structure):
    _fields_ = [("data_size", c_int), ("text", c_char_p)]


class RimeCandidateListIterator(Structure):
    _fields_ = [("ptr", c_void_p), ("index", c_int), ("candidate", RimeCandidate)]


def _data_size(struct: type[Structure]) -> int:
    # data_size counts the bytes after the field itself (rime_api.h RIME_STRUCT_INIT).
    return ctypes.sizeof(struct) - ctypes.sizeof(c_int)


def find_library() -> Path:
    if env := os.environ.get("RIME_LIB"):
        return Path(env)
    lib = ROOT / "deps" / "librime" / "dist" / "lib"
    name = {"Windows": "rime.dll", "Darwin": "librime.1.dylib"}.get(platform.system(), "librime.so.1")
    return lib / name


def _text(value: bytes | None) -> str:
    return value.decode("utf-8") if value else ""


class Rime:
    def __init__(self, shared: Path = BUILD, user: Path = USER, fresh: bool = False, forget: bool = False):
        """fresh drops the whole user folder (a full redeploy); forget drops only what Rime learned from commits."""
        if not (shared / f"{SCHEMA}.schema.yaml").is_file():
            raise FileNotFoundError(f"{shared} has no {SCHEMA}.schema.yaml; run python tools/build.py first")
        if fresh and user.exists():
            shutil.rmtree(user)
        if forget and user.exists():
            for learned in user.glob("*.userdb*"):
                shutil.rmtree(learned) if learned.is_dir() else learned.unlink()
        self.log_dir = user / "log"
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir)
        self.log_dir.mkdir(parents=True)

        self._lib = lib = ctypes.CDLL(str(find_library()))
        lib.RimeSetup.argtypes = [POINTER(RimeTraits)]
        lib.RimeInitialize.argtypes = [POINTER(RimeTraits)]
        lib.RimeStartMaintenance.argtypes = [c_int]
        lib.RimeStartMaintenance.restype = c_int
        lib.RimeCreateSession.restype = c_size_t
        lib.RimeDestroySession.argtypes = [c_size_t]
        lib.RimeSelectSchema.argtypes = [c_size_t, c_char_p]
        lib.RimeSelectSchema.restype = c_int
        lib.RimeSimulateKeySequence.argtypes = [c_size_t, c_char_p]
        lib.RimeSimulateKeySequence.restype = c_int
        lib.RimeClearComposition.argtypes = [c_size_t]
        lib.RimeGetContext.argtypes = [c_size_t, POINTER(RimeContext)]
        lib.RimeGetContext.restype = c_int
        lib.RimeFreeContext.argtypes = [POINTER(RimeContext)]
        lib.RimeGetCommit.argtypes = [c_size_t, POINTER(RimeCommit)]
        lib.RimeGetCommit.restype = c_int
        lib.RimeFreeCommit.argtypes = [POINTER(RimeCommit)]
        lib.RimeCandidateListBegin.argtypes = [c_size_t, POINTER(RimeCandidateListIterator)]
        lib.RimeCandidateListBegin.restype = c_int
        lib.RimeCandidateListNext.argtypes = [POINTER(RimeCandidateListIterator)]
        lib.RimeCandidateListNext.restype = c_int
        lib.RimeCandidateListEnd.argtypes = [POINTER(RimeCandidateListIterator)]

        user.mkdir(parents=True, exist_ok=True)
        # librime keeps these pointers, so the bytes must outlive the engine.
        self._strings = [str(shared).encode(), str(user).encode(), str(self.log_dir).encode()]
        self._traits = RimeTraits(
            data_size=_data_size(RimeTraits),
            shared_data_dir=self._strings[0],
            user_data_dir=self._strings[1],
            distribution_name=b"rime-ballban tests",
            distribution_code_name=b"rime-ballban-tests",
            distribution_version=b"0",
            app_name=b"rime.ballban-tests",
            min_log_level=int(os.environ.get("RIME_LOG_LEVEL", "2")),  # 0 info, 1 warning, 2 error
            log_dir=self._strings[2],
        )
        lib.RimeSetup(ctypes.byref(self._traits))
        lib.RimeInitialize(ctypes.byref(self._traits))
        if lib.RimeStartMaintenance(1):
            lib.RimeJoinMaintenanceThread()
        self.session = lib.RimeCreateSession()
        if not self.session or not lib.RimeSelectSchema(self.session, SCHEMA.encode()):
            raise RuntimeError(f"cannot select schema {SCHEMA}; see {self.log_dir}")

    def errors(self) -> list[str]:
        """Error lines librime logged so far (deployment and Lua errors land here)."""
        lines = []
        for path in sorted(self.log_dir.glob("*ERROR*")):
            text = path.read_text(encoding="utf-8", errors="replace")
            lines += [line for line in text.splitlines() if line.startswith("E")]
        return lines

    def type(self, keys: str, limit: int = 30) -> tuple[str, list[tuple[str, str]]]:
        """Type keys from an empty composition; returns the preedit and the first candidates as (text, comment)."""
        lib = self._lib
        lib.RimeClearComposition(self.session)
        lib.RimeSimulateKeySequence(self.session, keys.encode())
        context = RimeContext(data_size=_data_size(RimeContext))
        preedit = ""
        if lib.RimeGetContext(self.session, ctypes.byref(context)):
            preedit = _text(context.composition.preedit)
            lib.RimeFreeContext(ctypes.byref(context))
        found = []
        iterator = RimeCandidateListIterator()
        if lib.RimeCandidateListBegin(self.session, ctypes.byref(iterator)):
            while len(found) < limit and lib.RimeCandidateListNext(ctypes.byref(iterator)):
                found.append((_text(iterator.candidate.text), _text(iterator.candidate.comment)))
            lib.RimeCandidateListEnd(ctypes.byref(iterator))
        return preedit, found

    def commit(self, keys: str) -> str:
        """Type keys and return what is committed (keys may end with {space}, {Return}, ...)."""
        lib = self._lib
        lib.RimeClearComposition(self.session)
        lib.RimeSimulateKeySequence(self.session, keys.encode())
        commit = RimeCommit(data_size=_data_size(RimeCommit))
        if not lib.RimeGetCommit(self.session, ctypes.byref(commit)):
            return ""
        text = _text(commit.text)
        lib.RimeFreeCommit(ctypes.byref(commit))
        return text

    def close(self) -> None:
        if self.session:
            self._lib.RimeDestroySession(self.session)
            self.session = 0
        self._lib.RimeFinalize()
