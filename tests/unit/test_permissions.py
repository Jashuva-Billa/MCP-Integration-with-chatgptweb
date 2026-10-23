"""
Tests for the centralized permission policy engine.
Verifies profile behavior, capability gating, runtime profile switching,
and denial messages.
"""
import pytest
from app.config import settings
from app.core.permissions import PermissionProfile, PolicyViolation, PROFILES, PolicyEngine


def test_safe_profile_denies_delete_file():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.SAFE
    engine._rules = PROFILES[PermissionProfile.SAFE]
    with pytest.raises(PolicyViolation):
        engine.require_fs_delete_file()


def test_safe_profile_denies_delete_directory():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.SAFE
    engine._rules = PROFILES[PermissionProfile.SAFE]
    with pytest.raises(PolicyViolation):
        engine.require_fs_delete_directory()


def test_full_profile_allows_delete_file():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.FULL
    engine._rules = PROFILES[PermissionProfile.FULL]
    engine.require_fs_delete_file()   # should not raise


def test_full_profile_allows_delete_directory():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.FULL
    engine._rules = PROFILES[PermissionProfile.FULL]
    engine.require_fs_delete_directory()   # should not raise


def test_full_profile_denies_git_push():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.FULL
    engine._rules = PROFILES[PermissionProfile.FULL]
    with pytest.raises(PolicyViolation):
        engine.require_git_push()


def test_unrestricted_allows_git_push(monkeypatch):
    monkeypatch.setattr(settings, "MCP_GIT_PUSH_ENABLED", True)
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.UNRESTRICTED
    engine._rules = PROFILES[PermissionProfile.UNRESTRICTED]
    engine.require_git_push()   # should not raise


def test_unrestricted_allows_git_reset_hard():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.UNRESTRICTED
    engine._rules = PROFILES[PermissionProfile.UNRESTRICTED]
    engine.require_git_reset_hard()   # should not raise


def test_full_profile_denies_git_reset_hard():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.FULL
    engine._rules = PROFILES[PermissionProfile.FULL]
    with pytest.raises(PolicyViolation):
        engine.require_git_reset_hard()


def test_effective_timeout_capped():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.SAFE
    engine._rules = PROFILES[PermissionProfile.SAFE]
    assert engine.effective_timeout(9999) == 120   # safe profile cap


def test_unrestricted_has_no_binary_allowlist():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.UNRESTRICTED
    engine._rules = PROFILES[PermissionProfile.UNRESTRICTED]
    assert engine.effective_allowed_binaries() is None


def test_safe_profile_has_binary_allowlist():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.SAFE
    engine._rules = PROFILES[PermissionProfile.SAFE]
    binaries = engine.effective_allowed_binaries()
    assert binaries is not None
    assert "python" in binaries
    assert "pytest" in binaries


def test_profile_runtime_switch():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.SAFE
    engine._rules = PROFILES[PermissionProfile.SAFE]

    with pytest.raises(PolicyViolation):
        engine.require_fs_delete_file()

    engine.set_profile(PermissionProfile.FULL)
    engine.require_fs_delete_file()   # now allowed

    assert engine.profile == PermissionProfile.FULL


def test_describe_returns_dict():
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.FULL
    engine._rules = PROFILES[PermissionProfile.FULL]
    d = engine.describe()
    assert d["profile"] == "full"
    assert "fs_delete_file" in d
    assert "git_commit" in d


def test_trusted_admin_profile_capabilities(monkeypatch):
    monkeypatch.setattr(settings, "MCP_GIT_PUSH_ENABLED", True)
    engine = PolicyEngine.__new__(PolicyEngine)
    engine._profile = PermissionProfile.TRUSTED_ADMIN
    engine._rules = PROFILES[PermissionProfile.TRUSTED_ADMIN]

    # Authorized capabilities
    engine.require_git_push()       # Allowed for trusted admin
    engine.require_git_fetch()      # Allowed
    engine.require_git_pull()       # Allowed
    engine.require_network("test")  # Allowed
    engine.require_fs_delete_file() # Allowed
    assert engine.effective_timeout(9999) == 600

    # Safety boundary: destructive hard reset is guarded
    with pytest.raises(PolicyViolation):
        engine.require_git_reset_hard()


def test_network_access_gating():
    # Safe profile has network disabled
    engine_safe = PolicyEngine.__new__(PolicyEngine)
    engine_safe._profile = PermissionProfile.SAFE
    engine_safe._rules = PROFILES[PermissionProfile.SAFE]
    with pytest.raises(PolicyViolation):
        engine_safe.require_network("outbound call")

    # Trusted admin has network enabled
    engine_admin = PolicyEngine.__new__(PolicyEngine)
    engine_admin._profile = PermissionProfile.TRUSTED_ADMIN
    engine_admin._rules = PROFILES[PermissionProfile.TRUSTED_ADMIN]
    engine_admin.require_network("outbound call")  # should not raise

