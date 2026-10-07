import importlib.util
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location('dj_bridge', Path(__file__).parents[1] / 'provider/bridge.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.request = AsyncMock(return_value={'id': 'job-one'})
        self.bridge = module.DjBridge(self.request)

    async def test_session_and_queue_isolation(self):
        await self.bridge.suggest('guest-one', 'group', 'quiet jazz', 8)
        for owner, queue in [('guest-two', 'group'), ('guest-one', 'other')]:
            with self.assertRaises(ValueError):
                await self.bridge.job(owner, queue, 'job-one')
        self.request.assert_awaited_once()

    async def test_rate_limit_before_addon_call(self):
        await self.bridge.suggest('guest', 'group', 'jazz', 8)
        with self.assertRaises(ValueError):
            await self.bridge.suggest('guest', 'group', 'rock', 8)
        self.request.assert_awaited_once()

    async def test_strip_capabilities_and_only_fetch_owned_job(self):
        await self.bridge.suggest('guest', 'group', 'jazz', 8)
        self.request.return_value = {'id': 'job-one', 'state': 'ready', 'tracks': [], 'admin_token': 'secret', 'queued': False}
        self.assertEqual(await self.bridge.job('guest', 'group', 'job-one'), {'id': 'job-one', 'state': 'ready', 'tracks': []})
        self.assertEqual(self.request.await_args.args, ('/api/jobs/job-one', None))

    async def test_validation_does_not_call_addon(self):
        for prompt, count in [('', 8), ('jazz', True), ('jazz', 200), ('x'*1001, 8)]:
            with self.assertRaises(ValueError):
                await self.bridge.suggest('guest', 'group', prompt, count)
        self.request.assert_not_awaited()

    async def test_expired_job(self):
        self.bridge.jobs['old'] = ('guest', 'group', -10000)
        with self.assertRaises(ValueError):
            await self.bridge.job('guest', 'group', 'old')
        self.request.assert_not_awaited()
