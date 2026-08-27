from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from annet.annlib.command import CommandList

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
