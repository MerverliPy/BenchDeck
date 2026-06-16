from __future__ import annotations


class LoadError(ValueError):
    pass


class DuplicateBasenameError(LoadError):
    pass


class MemberCapExceededError(LoadError):
    pass


class OversizeMemberError(LoadError):
    pass


class CorruptArchiveError(LoadError):
    pass


class MalformedJsonError(LoadError):
    pass


class InvalidUtf8Error(LoadError):
    pass


class MissingRequiredMemberError(LoadError):
    pass
