"""tests/test_seo_fixer.py - repo-aware SEO auto-fixer tests (issue #533)."""
from __future__ import annotations

from pathlib import Path

import pytest

from models.seo_audit import SeoFixRequest
from services.seo_fixer import SeoFixer, _humanize_filename, run_fixes

BROKEN_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <p>Welcome to our store where we sell hand forged garden tools that last for decades and ship worldwide.</p>
    <img src="img/hero-banner_2.png">
    <a href="https://external.example.org" target="_blank">External</a>
    <script src="//cdn.example.com/lib.js"></script>
</body>
</html>
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(BROKEN_HTML, encoding="utf-8")
    (tmp_path / "about").mkdir()
    (tmp_path / "about" / "index.html").write_text(BROKEN_HTML, encoding="utf-8")
    # a directory that must be skipped
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.html").write_text("<html></html>", encoding="utf-8")
    return tmp_path


class TestHumanize:
    def test_humanize_filename(self):
        assert _humanize_filename("img/hero-banner_2.png") == "Hero banner 2"
        assert _humanize_filename("x/y/team-photo.jpg?v=2") == "Team photo"


class TestDryRun:
    def test_dry_run_does_not_write(self, repo: Path):
        before = (repo / "index.html").read_text()
        result = run_fixes(SeoFixRequest(
            repo_path=str(repo), base_url="https://example.com", apply=False,
        ))
        assert result.dry_run
        assert (repo / "index.html").read_text() == before
        assert not (repo / "robots.txt").exists()
        assert result.files_scanned == 2  # node_modules skipped
        assert result.actions, "dry run must still report proposed actions"
        assert all(not a.applied for a in result.actions)

    def test_dry_run_produces_diffs(self, repo: Path):
        result = run_fixes(SeoFixRequest(
            repo_path=str(repo), base_url="https://example.com", apply=False,
        ))
        modified = [a for a in result.actions if a.action == "modified"]
        assert modified
        assert any("+++" in a.diff for a in modified)


class TestApply:
    @pytest.fixture
    def applied(self, repo: Path):
        result = run_fixes(SeoFixRequest(
            repo_path=str(repo), base_url="https://example.com",
            site_name="Example Store", apply=True,
        ))
        return repo, result

    def test_html_fixes_applied(self, applied):
        repo, _result = applied
        content = (repo / "index.html").read_text()
        assert '<meta charset="utf-8">' in content
        assert 'name="viewport"' in content
        assert '<html lang="en">' in content
        assert 'name="description"' in content
        assert '<link rel="canonical" href="https://example.com">' in content
        assert 'property="og:title"' in content
        assert 'name="twitter:card"' in content

    def test_image_alt_added(self, applied):
        repo, _result = applied
        content = (repo / "index.html").read_text()
        assert 'alt="Hero banner 2"' in content

    def test_noopener_added(self, applied):
        repo, _ = applied
        content = (repo / "index.html").read_text()
        assert 'rel="noopener"' in content

    def test_protocol_relative_rewritten(self, applied):
        repo, _ = applied
        content = (repo / "index.html").read_text()
        assert 'src="https://cdn.example.com/lib.js"' in content
        assert 'src="//cdn.example.com' not in content

    def test_geo_files_created(self, applied):
        repo, _result = applied
        assert (repo / "robots.txt").exists()
        robots = (repo / "robots.txt").read_text()
        assert "Sitemap: https://example.com/sitemap.xml" in robots

        assert (repo / "sitemap.xml").exists()
        sitemap = (repo / "sitemap.xml").read_text()
        assert "<loc>https://example.com</loc>" in sitemap
        assert "<loc>https://example.com/about</loc>" in sitemap

        assert (repo / "llms.txt").exists()
        llms = (repo / "llms.txt").read_text()
        assert llms.startswith("# Example Store")

    def test_canonical_url_for_subpage(self, applied):
        repo, _ = applied
        content = (repo / "about" / "index.html").read_text()
        assert '<link rel="canonical" href="https://example.com/about">' in content

    def test_result_counters(self, applied):
        _, result = applied
        assert not result.dry_run
        assert result.files_modified == 2
        assert result.files_created == 3  # robots.txt, sitemap.xml, llms.txt
        assert result.suggestions >= 1   # security headers suggestion
        assert "applied" in result.summary

    def test_fixed_files_are_idempotent(self, applied):
        repo, _ = applied
        second = run_fixes(SeoFixRequest(
            repo_path=str(repo), base_url="https://example.com", apply=True,
        ))
        assert second.files_modified == 0
        assert second.files_created == 0

    def test_fixed_page_passes_audit_checks(self, applied):
        """The fixer's output must satisfy the audit engine's fixable checks."""
        repo, _ = applied
        from services.seo_audit import analyze_page

        content = (repo / "index.html").read_text()
        findings = analyze_page("https://example.com/", content,
                                headers={"content-type": "text/html"})
        fired = {i.check_code for i in findings.issues}
        for code in ("validation_missing_charset", "validation_missing_viewport",
                     "validation_missing_lang", "meta_desc_missing",
                     "canonical_missing", "social_missing_twitter_card",
                     "security_unsafe_cross_origin_links",
                     "security_protocol_relative_resources",
                     "image_missing_alt_attribute"):
            assert code not in fired, f"fixer failed to remediate {code}"


class TestScoping:
    def test_include_checks_restricts_fixes(self, repo: Path):
        result = run_fixes(SeoFixRequest(
            repo_path=str(repo), base_url="https://example.com",
            include_checks=["validation_missing_charset"], apply=True,
        ))
        content = (repo / "index.html").read_text()
        assert '<meta charset="utf-8">' in content
        assert 'name="viewport"' not in content
        assert not (repo / "llms.txt").exists()
        assert result.files_created == 0

    def test_missing_repo_path(self, tmp_path: Path):
        result = run_fixes(SeoFixRequest(repo_path=str(tmp_path / "does-not-exist")))
        assert result.files_scanned == 0
        assert "does not exist" in result.summary

    def test_security_header_suggestion_for_netlify(self, repo: Path):
        (repo / "netlify.toml").write_text("[build]\n", encoding="utf-8")
        result = run_fixes(SeoFixRequest(repo_path=str(repo), apply=False))
        suggestions = [a for a in result.actions if a.action == "suggested"]
        assert any("netlify.toml" in a.file_path for a in suggestions)
        assert any("Content-Security-Policy" in a.diff for a in suggestions)

    def test_lazy_loading_added_below_fold_only(self, tmp_path: Path):
        (tmp_path / "page.html").write_text(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>X</title>'
            '</head><body><img src="hero.png" alt="Hero">'
            '<img src="a.png" alt="A"><img src="b.png" alt="B"></body></html>',
            encoding="utf-8",
        )
        run_fixes(SeoFixRequest(repo_path=str(tmp_path), apply=True,
                                include_checks=["image_not_lazy_loaded"]))
        content = (tmp_path / "page.html").read_text()
        # hero image stays eager; the two below-the-fold images become lazy
        assert content.count('loading="lazy"') == 2
        assert '<img src="hero.png" alt="Hero">' in content

    def test_image_size_attributes_with_real_image(self, tmp_path: Path):
        from PIL import Image

        (tmp_path / "img").mkdir()
        Image.new("RGB", (320, 200)).save(tmp_path / "img" / "photo.png")
        (tmp_path / "page.html").write_text(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>X</title>'
            '</head><body><img src="img/photo.png" alt="Photo"></body></html>',
            encoding="utf-8",
        )
        run_fixes(SeoFixRequest(repo_path=str(tmp_path), apply=True,
                                include_checks=["image_missing_size_attributes"]))
        content = (tmp_path / "page.html").read_text()
        assert 'width="320" height="200"' in content
