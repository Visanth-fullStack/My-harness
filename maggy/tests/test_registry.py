"""Tests for project registry and project config parsing."""

from __future__ import annotations

from maggy.config import MaggyConfig, ProjectConfig, _from_dict
from maggy.registry import ProjectRegistry


class TestProjectConfigParsing:
    def test_from_dict_parses_projects(self):
        cfg = _from_dict({
            "projects": [
                {
                    "name": "alpha",
                    "repo": "acme/alpha",
                    "path": "~/code/alpha",
                    "default_branch": "main",
                },
                {
                    "name": "beta",
                    "repo": "acme/beta",
                    "path": "~/code/beta",
                    "default_branch": "develop",
                    "icpg": False,
                    "cikg": True,
                },
            ],
        })
        assert [project.name for project in cfg.projects] == ["alpha", "beta"]
        assert cfg.projects[0].icpg is True
        assert cfg.projects[0].cikg is False
        assert cfg.projects[1].default_branch == "develop"
        assert cfg.projects[1].icpg is False
        assert cfg.projects[1].cikg is True


class TestProjectRegistry:
    def test_registry_crud(self):
        alpha = ProjectConfig(
            name="alpha",
            repo="acme/alpha",
            path="/tmp/alpha",
            default_branch="main",
        )
        beta = ProjectConfig(
            name="beta",
            repo="acme/beta",
            path="/tmp/beta",
            default_branch="develop",
        )
        registry = ProjectRegistry(MaggyConfig(projects=[alpha]))
        assert registry.list() == [alpha]
        assert registry.get("alpha") == alpha
        registry.add(beta)
        assert registry.get("beta") == beta
        assert registry.remove("alpha") is True
        assert registry.get("alpha") is None
        assert registry.remove("alpha") is False

    def test_add_duplicate_raises(self):
        import pytest
        alpha = ProjectConfig(
            name="alpha",
            repo="acme/alpha",
            path="/tmp/alpha",
            default_branch="main",
        )
        registry = ProjectRegistry(MaggyConfig(projects=[alpha]))
        with pytest.raises(ValueError, match="already exists"):
            registry.add(alpha)
