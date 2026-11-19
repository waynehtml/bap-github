"""Forwarded user information for the current Streamlit execution."""

from dataclasses import dataclass, field

import streamlit as st


@dataclass(frozen=True)
class RequestContext:
    """Request metadata, not an authorization decision.

    Read a fresh context on every execution. Never cache or serialize the context
    or token. Local requests may have no forwarded headers. Projects must enforce
    their own authorization before using privileged backend clients.
    """

    user_token: str | None = field(default=None, repr=False)
    user_name: str | None = None
    user_email: str | None = None
    user_id: str | None = None

    @classmethod
    def current(cls) -> "RequestContext":
        """Read current headers without retaining them in shared or session state."""
        headers = st.context.headers
        return cls(
            user_token=headers.get("X-Forwarded-Access-Token"),
            user_name=headers.get("X-Forwarded-Preferred-Username"),
            user_email=headers.get("X-Forwarded-Email"),
            user_id=headers.get("X-Forwarded-User"),
        )
