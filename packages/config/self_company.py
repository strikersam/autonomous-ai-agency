"""packages/config/self_company.py — controls for the platform's own company.

The platform runs itself as one company (``services/self_company.py``). These
readers are the only place the feature's environment variables are read
(CLAUDE.md rule 5), re-read on every call so a Platform Controls change
applies without a restart.
"""
from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def self_company_consolidate_enabled() -> bool:
    """Merge duplicate copies of the platform's own company into one at startup."""
    return os.environ.get("SELF_COMPANY_CONSOLIDATE_ENABLED", "true").strip().lower() in _TRUTHY


def admin_email() -> str:
    """The operator account the platform's own company belongs to."""
    return (os.environ.get("ADMIN_EMAIL") or "admin@llmrelay.local").strip()


def public_site_url() -> str:
    """The platform's public website (the Cloudflare Worker frontend).

    This is the site visitors, search engines and AI crawlers see, so it is
    the company's domain and the target of its SEO/GEO/AEO/AIO work. The
    Render URL is the API behind it, not a site anyone should rank.
    """
    url = (os.environ.get("SELF_PUBLIC_SITE_URL") or "").strip()
    return url or "https://autonomous-ai-agency.strikersam.workers.dev"
