from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import gnetclisdk.proto.server_pb2 as pb
from annet.annlib.command import Command, CommandList
from gnetclisdk.client import HostParams

from gnetcli_adapter.gnetcli_adapter import GnetcliDeployer, GnetcliFetcher


def test_make_api_uses_url_without_starter():
    fetcher = GnetcliFetcher(url="127.0.0.1:50050")

    async def run():
        with patch("gnetcli_adapter.gnetcli_adapter.GnetcliStarter") as starter:
            async with fetcher.make_api() as api:
                assert api._server == "127.0.0.1:50050"
            starter.assert_not_called()

    asyncio.run(run())


def test_serial_deploy_preserves_credentials_and_results():
    deployer = GnetcliDeployer(
        url="127.0.0.1:50050",
        dev_login="device-login",
        dev_password="device-password",
    )
    api = Mock()
    args = SimpleNamespace(max_parallel=1)
    device_ok = Mock(fqdn="ok.example.net")
    device_failed = Mock(fqdn="failed.example.net")
    cmds_ok = CommandList()
    cmds_failed = CommandList()
    deploy_error = RuntimeError("deploy failed")

    async def deploy_result(_api, device, _cmds, _args, _progress_bar, _credentials):
        if device is device_failed:
            return deploy_error
        return None

    deployer.deploy = AsyncMock(side_effect=deploy_result)

    result = asyncio.run(
        deployer._bulk_deploy(
            api=api,
            deploy_cmds={device_ok: cmds_ok, device_failed: cmds_failed},
            args=args,
        )
    )

    assert result.hostnames == ["ok.example.net", "failed.example.net"]
    assert result.results == {
        "ok.example.net": None,
        "failed.example.net": deploy_error,
    }
    assert deployer.deploy.await_count == 2
    for call, device, cmds in zip(
        deployer.deploy.await_args_list,
        (device_ok, device_failed),
        (cmds_ok, cmds_failed),
    ):
        assert call.args[:5] == (api, device, cmds, args, None)
        credentials = call.args[5]
        assert credentials.login == "device-login"
        assert credentials.password == "device-password"


def test_suppress_errors_does_not_fail_deploy_and_continues_commands():
    deployer = GnetcliDeployer(url="127.0.0.1:50050")
    suppressed_result = pb.CMDResult(status=1, error=b"ignored error")
    successful_result = pb.CMDResult(status=0, out=b"done")
    session = Mock()
    session.cmd = AsyncMock(side_effect=[suppressed_result, successful_result])

    @asynccontextmanager
    async def cmd_session(**_kwargs):
        yield session

    api = Mock()
    api.cmd_session = cmd_session
    tracker = Mock()
    commands = CommandList(
        [
            Command("ignored command", suppress_errors=True),
            Command("next command"),
        ]
    )

    seen_exc, results = asyncio.run(
        deployer._deploy(
            api=api,
            device=Mock(fqdn="device.example.net"),
            host_params=HostParams(device="cisco"),
            command_groups=[("Run command", commands)],
            files={},
            tracker=tracker,
        )
    )

    assert seen_exc == []
    assert results == [successful_result]
    assert session.cmd.await_count == 2
    tracker.command_done_error_suppressed.assert_called_once_with("ignored error")
    tracker.command_done_error.assert_not_called()
