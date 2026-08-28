"""The provider catalogue probe: must not leak, must not lie, must not be
provider-specific.

Model ids were guessed for months because nothing in a developer sandbox could
ask a vendor what it serves — the keys live in CI. The probe runs there. Three
properties matter more than its output:

* it never prints a key (rule 6);
* a failed probe reports failure rather than looking healthy, which is the
  pathology every NVIDIA fix in this repo has been unwinding;
* it names no provider and no model in its logic, so adding a provider stays a
  config entry (``config/llm/providers.yaml``, ADR-008 §2).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_SCRIPTS = REPO_ROOT / ".github/scripts"
SCRIPT = GITHUB_SCRIPTS / "probe_catalogues.py"
WORKFLOW = REPO_ROOT / ".github/workflows/catalogue-probe.yml"

SECRET = "sk-do-not-print-me-0123456789"


@pytest.fixture
def probe():
    sys.path.insert(0, str(GITHUB_SCRIPTS))
    import probe_catalogues as mod

    return mod


def _provider(**overrides) -> SimpleNamespace:
    base = {
        "id": "acme",
        "kind": "openai",
        "base_url": "https://api.acme.test/v1",
        "key_env": ["ACME_API_KEY"],
        "default_model": "acme/model-1",
        "tier": "free",
        "priority": 10,
        "auth_style": "bearer",
        "extra_headers": {},
        "requires_key": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestItIsNotBuiltForOneVendor:
    """The bug being fixed is single-provider hardcoding; the fix must not
    reintroduce it in the diagnostic."""

    def test_no_model_id_appears_in_the_script(self) -> None:
        """The probe asks what exists; it must not tell.

        Checked against the real catalogue rather than a hand-written list of
        substrings — a substring check here matched the adapter kind "ollama"
        for containing "llama", which is the same false-confidence this whole
        line of work has been removing.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        body = code.split('"""', 2)[-1]  # drop the module docstring

        catalogue = yaml.safe_load(
            (REPO_ROOT / "config/llm/models.yaml").read_text(encoding="utf-8")
        )
        known = list((catalogue.get("models") or {}))
        assert known, "the catalogue is empty; this guard would pass vacuously"
        offenders = [model_id for model_id in known if model_id in body]
        assert not offenders, f"probe hardcodes catalogue models: {offenders}"

    def test_provider_ids_are_not_hardcoded_in_the_logic(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        body = source.split('"""', 2)[-1]
        for vendor in ("nvidia", "cerebras", "groq", "openrouter"):
            assert vendor not in body.lower(), (
                f"{vendor!r} is named in the probe's logic; providers come from config"
            )

    def test_every_adapter_kind_has_a_list_route(self, probe) -> None:
        """Whatever kinds the config can express, the probe must handle."""
        from packages.llm.config import load_config

        providers = list(load_config().providers.values())
        assert providers, "no providers configured; this guard would pass vacuously"
        # Resolved kinds, not raw ones: providers.yaml says `kind: lmstudio`
        # and `kind: vllm`, which are aliases for the OpenAI adapter. Checking
        # the raw value caught four providers the probe could not have read.
        missing = {probe._kind(p) for p in providers} - set(probe._LIST_MODELS)
        assert not missing, f"no list-models route for adapter kinds: {missing}"

    def test_it_walks_every_configured_provider(self, probe) -> None:
        ids = [p.id for p in probe._providers(None)]
        assert len(ids) > 1, "the probe must consider more than one provider"


class TestNoKeyEverReachesTheLog:
    """Rule 6: secrets are never logged, not even partially."""

    def test_a_full_run_never_emits_the_key(self, probe, monkeypatch, capsys) -> None:
        monkeypatch.setenv("ACME_API_KEY", SECRET)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])
        monkeypatch.setattr(
            probe, "_request", lambda p, path, key, payload=None: {"data": [{"id": "m"}]}
        )
        probe.main([])
        out = capsys.readouterr().out
        assert SECRET not in out
        assert SECRET[:10] not in out
        assert "key present: yes" in out

    def test_a_failing_request_never_emits_the_key(self, probe, monkeypatch, capsys) -> None:
        """Error paths print exception text — that must not carry the key."""
        monkeypatch.setenv("ACME_API_KEY", SECRET)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])

        def _boom(p, path, key, payload=None):
            raise OSError("connection refused")

        monkeypatch.setattr(probe, "_request", _boom)
        probe.main([])
        assert SECRET not in capsys.readouterr().out


class TestAFailedProbeIsNotASuccess:
    def test_no_reachable_provider_is_a_non_zero_exit(self, probe, monkeypatch) -> None:
        monkeypatch.delenv("ACME_API_KEY", raising=False)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])
        assert probe.main([]) == 1

    def test_an_unreachable_provider_is_a_non_zero_exit(self, probe, monkeypatch) -> None:
        monkeypatch.setenv("ACME_API_KEY", SECRET)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])

        def _boom(p, path, key, payload=None):
            raise OSError("no route to host")

        monkeypatch.setattr(probe, "_request", _boom)
        assert probe.main([]) == 1

    def test_a_listed_but_unservable_model_is_a_non_zero_exit(
        self, probe, monkeypatch
    ) -> None:
        """Listing is not proof. A retired id can still appear in a catalogue."""
        monkeypatch.setenv("ACME_API_KEY", SECRET)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])

        def _request(p, path, key, payload=None):
            if payload is None:
                return {"data": [{"id": "acme/model-1"}]}
            raise OSError("410 Gone")

        monkeypatch.setattr(probe, "_request", _request)
        assert probe.main(["--chat", "acme"]) == 1

    def test_a_healthy_provider_passes(self, probe, monkeypatch) -> None:
        monkeypatch.setenv("ACME_API_KEY", SECRET)
        monkeypatch.setattr(probe, "_providers", lambda only: [_provider()])

        def _request(p, path, key, payload=None):
            if payload is None:
                return {"data": [{"id": "acme/model-1"}]}
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr(probe, "_request", _request)
        assert probe.main(["--chat", "acme"]) == 0


class TestAuthFollowsTheProviderDeclaration:
    def test_bearer_is_the_default(self, probe) -> None:
        assert probe._auth_headers(_provider(), "k") == {"Authorization": "Bearer k"}

    def test_x_api_key_style(self, probe) -> None:
        headers = probe._auth_headers(_provider(auth_style="x-api-key"), "k")
        assert headers["x-api-key"] == "k"
        assert "anthropic-version" in headers

    def test_query_style_sends_no_auth_header(self, probe) -> None:
        assert probe._auth_headers(_provider(auth_style="query"), "k") == {}

    def test_no_key_sends_no_auth_header(self, probe) -> None:
        assert probe._auth_headers(_provider(), "") == {}


class TestTheWorkflowIsSafeAndReadOnly:
    @pytest.fixture
    def workflow(self) -> dict:
        return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_inputs_are_not_interpolated_into_the_shell(self) -> None:
        """A ${{ }} expansion inside `run:` is pasted in as shell source, so a
        crafted input would execute as a command."""
        text = WORKFLOW.read_text(encoding="utf-8")
        for block in text.split("run: |")[1:]:
            assert "${{" not in block, "workflow inputs must reach run: via env"

    def test_it_only_reads(self, workflow: dict) -> None:
        assert workflow["permissions"] == {"contents": "read"}

    def test_it_is_dispatch_only(self, workflow: dict) -> None:
        # `on` parses as True under YAML 1.1 unless quoted; accept either key.
        triggers = workflow.get("on", workflow.get(True))
        assert set(triggers) == {"workflow_dispatch"}, (
            "a scheduled probe would need a loops/registry.yaml entry"
        )

    def test_it_does_not_commit_or_push(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for forbidden in ("git commit", "git push", "create_pull_request", "gh pr"):
            assert forbidden not in text


class TestTheWorkflowInstallsWhatTheImportNeeds:
    """The first real run died in 10 seconds on ModuleNotFoundError: httpx.

    The probe itself only uses ``urllib``, so installing ``pyyaml`` looked
    sufficient. It is not: ``_providers`` imports ``packages.llm.config``, and
    ``packages/llm/__init__`` imports the router, which imports ``httpx``. The
    dependency is real but invisible at the call site — exactly the kind of
    thing that is cheap to assert and expensive to rediscover.
    """

    def test_the_install_step_covers_the_transitive_imports(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        install = [line for line in text.splitlines() if "pip install" in line]
        assert install, "the workflow must install the config dependencies"
        joined = " ".join(install)
        for package in ("pyyaml", "httpx"):
            assert package in joined, f"{package} is needed to load the provider config"
