"""Tests for per-sandbox network isolation and network policy enforcement."""

from __future__ import annotations

from unittest.mock import MagicMock

from lintel.contracts.types import ThreadRef
from lintel.sandbox.docker_backend import DockerSandboxManager
from lintel.sandbox.resource_guard import build_network_policy_script
from lintel.sandbox.types import (
    NetworkEndpoint,
    NetworkPolicy,
    SandboxConfig,
)


def _make_manager_with_mock() -> tuple[DockerSandboxManager, MagicMock]:
    manager = DockerSandboxManager()
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.create.return_value = mock_container
    manager._client = mock_client
    return manager, mock_client


THREAD_REF = ThreadRef("W1", "C1", "t1")


class TestNetworkPolicyScript:
    def test_empty_endpoints_returns_empty(self) -> None:
        policy = NetworkPolicy()
        assert build_network_policy_script(policy) == ""

    def test_single_endpoint_with_port(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="github.com", port=443),),
        )
        script = build_network_policy_script(policy)
        assert "iptables" in script
        assert "github.com" in script
        assert "--dport 443" in script
        assert "-p tcp" in script
        assert "-j DROP" in script

    def test_endpoint_without_port_allows_all_ports(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="pypi.org"),),
        )
        script = build_network_policy_script(policy)
        assert "pypi.org" in script
        assert "--dport" not in script.split("pypi.org")[1].split("\n")[0]

    def test_udp_protocol(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="ntp.ubuntu.com", port=123, protocol="udp"),),
        )
        script = build_network_policy_script(policy)
        assert "-p udp" in script
        assert "--dport 123" in script

    def test_multiple_endpoints(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(
                NetworkEndpoint(host="github.com", port=443),
                NetworkEndpoint(host="pypi.org", port=443),
                NetworkEndpoint(host="registry.npmjs.org", port=443),
            ),
        )
        script = build_network_policy_script(policy)
        assert "github.com" in script
        assert "pypi.org" in script
        assert "registry.npmjs.org" in script

    def test_dns_always_allowed(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="example.com", port=80),),
        )
        script = build_network_policy_script(policy)
        assert "--dport 53" in script

    def test_loopback_always_allowed(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="example.com", port=80),),
        )
        script = build_network_policy_script(policy)
        assert "-o lo -j ACCEPT" in script


class TestIsolatedNetworkCreation:
    async def test_creates_dedicated_network(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        policy = NetworkPolicy(isolate=True)
        config = SandboxConfig(network_enabled=True, network_policy=policy)

        sandbox_id = await manager.create(config, THREAD_REF)

        expected_net_name = f"lintel-sandbox-{sandbox_id[:12]}"
        mock_client.networks.create.assert_called_once_with(
            expected_net_name,
            driver="bridge",
            internal=False,
            labels={"lintel.sandbox_id": sandbox_id},
        )
        # Container should use the dedicated network
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["network_mode"] == expected_net_name

    async def test_no_isolated_network_when_isolate_false(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        policy = NetworkPolicy(isolate=False)
        config = SandboxConfig(network_enabled=True, network_policy=policy)

        await manager.create(config, THREAD_REF)

        mock_client.networks.create.assert_not_called()
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["network_mode"] == "bridge"

    async def test_no_network_when_disabled(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        policy = NetworkPolicy(isolate=True)
        config = SandboxConfig(network_enabled=False, network_policy=policy)

        await manager.create(config, THREAD_REF)

        mock_client.networks.create.assert_not_called()
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["network_mode"] == "none"

    async def test_no_network_when_no_policy(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        config = SandboxConfig(network_enabled=True)

        await manager.create(config, THREAD_REF)

        mock_client.networks.create.assert_not_called()
        create_kwargs = mock_client.containers.create.call_args[1]
        assert create_kwargs["network_mode"] == "bridge"


class TestNetworkPolicyApplied:
    async def test_policy_script_executed_on_create(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        mock_container = mock_client.containers.create.return_value
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="github.com", port=443),),
            isolate=True,
        )
        config = SandboxConfig(network_enabled=True, network_policy=policy)

        await manager.create(config, THREAD_REF)

        # Calls: chown (root), then network policy script (root)
        calls = mock_container.exec_run.call_args_list
        assert len(calls) >= 2
        policy_call = calls[1]
        assert policy_call[1]["user"] == "root"
        script_cmd = policy_call[0][0]
        assert script_cmd[0] == "/bin/sh"

    async def test_legacy_egress_used_when_no_network_policy(self) -> None:
        """NetworkEgressPolicy is used when network_policy is None."""
        from lintel.sandbox.types import NetworkEgressPolicy

        manager, mock_client = _make_manager_with_mock()
        mock_container = mock_client.containers.create.return_value
        config = SandboxConfig(
            network_enabled=True,
            network_egress=NetworkEgressPolicy(allowed_domains=("github.com",)),
        )

        await manager.create(config, THREAD_REF)

        calls = mock_container.exec_run.call_args_list
        assert len(calls) >= 2  # chown + egress script

    async def test_network_policy_takes_precedence_over_egress(self) -> None:
        """When both are set, NetworkPolicy is used, not NetworkEgressPolicy."""
        from lintel.sandbox.types import NetworkEgressPolicy

        manager, mock_client = _make_manager_with_mock()
        mock_container = mock_client.containers.create.return_value
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="github.com", port=443),),
            isolate=False,
        )
        config = SandboxConfig(
            network_enabled=True,
            network_policy=policy,
            network_egress=NetworkEgressPolicy(allowed_domains=("pypi.org",)),
        )

        await manager.create(config, THREAD_REF)

        # Should only have chown + network policy (not egress)
        calls = mock_container.exec_run.call_args_list
        assert len(calls) == 2
        script_arg = calls[1][0][0][2]  # ["/bin/sh", "-c", <script>]
        assert "github.com" in script_arg
        assert "pypi.org" not in script_arg


class TestNetworkCleanupOnDestroy:
    async def test_destroy_removes_dedicated_network(self) -> None:
        manager, mock_client = _make_manager_with_mock()
        mock_network = MagicMock()
        mock_client.networks.get.return_value = mock_network

        policy = NetworkPolicy(isolate=True)
        config = SandboxConfig(network_enabled=True, network_policy=policy)

        sandbox_id = await manager.create(config, THREAD_REF)
        expected_net_name = f"lintel-sandbox-{sandbox_id[:12]}"

        await manager.destroy(sandbox_id)

        mock_client.networks.get.assert_called_with(expected_net_name)
        mock_network.remove.assert_called_once()

    async def test_destroy_without_network_is_fine(self) -> None:
        manager = DockerSandboxManager()
        mock_container = MagicMock()
        manager._containers["s1"] = mock_container

        await manager.destroy("s1")

        mock_container.remove.assert_called_once_with(force=True)
        assert "s1" not in manager._networks


class TestNetworkPolicyTypes:
    def test_network_endpoint_defaults(self) -> None:
        ep = NetworkEndpoint(host="github.com")
        assert ep.port is None
        assert ep.protocol == "tcp"

    def test_network_policy_defaults(self) -> None:
        policy = NetworkPolicy()
        assert policy.allowed_endpoints == ()
        assert policy.isolate is True

    def test_sandbox_config_network_policy_default_none(self) -> None:
        config = SandboxConfig()
        assert config.network_policy is None

    def test_sandbox_config_with_network_policy(self) -> None:
        policy = NetworkPolicy(
            allowed_endpoints=(NetworkEndpoint(host="example.com", port=443),),
            isolate=True,
        )
        config = SandboxConfig(network_policy=policy)
        assert config.network_policy is not None
        assert len(config.network_policy.allowed_endpoints) == 1
        assert config.network_policy.allowed_endpoints[0].host == "example.com"
