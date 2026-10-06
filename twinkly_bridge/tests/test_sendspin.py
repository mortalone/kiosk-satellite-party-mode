import asyncio
import json
import struct
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from aiohttp import ClientSession, web
from aiosendspin.models.visualizer import VisualizerFrame, StreamStartVisualizer
from aiosendspin.noise.trust_store import FileClientPairingStore, InMemoryServerPairingStore
from aiosendspin.noise.keys import Identity

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import Bridge
from sendspin_source import FrameBuffer, SendspinSource, decode_legacy_frame, load_identity


async def eventually_async(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Condition was not satisfied")


class BufferTest(unittest.TestCase):
    def test_future_frames_and_seek_clear(self):
        bridge = Bridge({})
        buffer = FrameBuffer(bridge, maximum=2)
        frame = VisualizerFrame(timestamp_us=1, spectrum=[0, 65535])
        self.assertFalse(buffer.add(frame, 9, now=10))
        self.assertFalse(buffer.add(frame, 41, now=10))
        self.assertTrue(buffer.add(frame, 10.5, now=10))
        self.assertEqual(buffer.drain(now=10.4), 0)
        self.assertFalse(bridge.status()["audio_fresh"])
        self.assertEqual(buffer.drain(now=10.5), 1)
        self.assertEqual(bridge.bands, [0, 1])
        buffer.add(frame, 11, now=10)
        buffer.clear()
        self.assertEqual(buffer.drain(now=12), 0)
        self.assertFalse(bridge.status()["audio_fresh"])

    def test_queue_limits_and_late_frames(self):
        bridge = Bridge({})
        buffer = FrameBuffer(bridge, maximum=1)
        frame = VisualizerFrame(timestamp_us=1, spectrum=[32768])
        self.assertTrue(buffer.add(frame, 10.5, now=10))
        self.assertFalse(buffer.add(frame, 10.6, now=10))
        self.assertEqual(buffer.drain(now=11), 0)
        self.assertFalse(bridge.status()["audio_fresh"])

    def test_wire_data_and_persistent_identity(self):
        packet = bytes([19])+struct.pack(">qHH", 1234, 0, 65535)
        frame = decode_legacy_frame(packet, 2)
        self.assertEqual(frame.timestamp_us, 1234)
        self.assertEqual(frame.spectrum, [0, 65535])
        self.assertIsNone(decode_legacy_frame(packet, 3))
        self.assertIsNone(decode_legacy_frame(b"bad", 3))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self.assertEqual(load_identity(path), load_identity(path))
            self.assertEqual((path/'sendspin_identity.key').stat().st_mode & 0o777, 0o600)


class ProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_websocket_stream_pause_and_scheduling(self):
        await self.check_legacy_stream(True)

    async def test_legacy_visualizer_only_fallback(self):
        await self.check_legacy_stream(False)

    async def check_legacy_stream(self, player):
        received = []
        socket_ready = asyncio.Event()
        live_socket = []
        async def endpoint(request):
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            live_socket.append(socket)
            await socket.send_json({"type":"server/hello","payload":{"server_id":"test","name":"test"}})
            async for message in socket:
                data = json.loads(message.data)
                received.append(data)
                if data['type'] == 'client/time':
                    now = time.monotonic_ns()//1000
                    await socket.send_json({"type":"server/time","payload":{"client_transmitted":data['payload']['client_transmitted'],"server_received":now,"server_transmitted":now}})
                    socket_ready.set()
            return socket
        app = web.Application(); app.router.add_get('/sendspin',endpoint)
        runner = web.AppRunner(app);await runner.setup()
        site = web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port = site._server.sockets[0].getsockname()[1]
        bridge = Bridge({})
        source = SendspinSource(bridge, {'sendspin_url':f'ws://127.0.0.1:{port}/sendspin', 'sendspin_player':player})
        render = asyncio.create_task(source.render())
        async with ClientSession() as session:
            task = asyncio.create_task(source.legacy(Identity.generate(),session))
            try:
                await asyncio.wait_for(socket_ready.wait(),2)
                await eventually_async(lambda: source.status()['clock_synced'])
                hello = received[0]['payload']
                self.assertEqual(hello['supported_roles'],['player@v1','visualizer@v1','artwork@v1'] if player else ['visualizer@v1','artwork@v1'])
                self.assertEqual('player@v1_support' in hello, player)
                socket = live_socket[0]
                if player:
                    self.assertEqual(hello['player@v1_support']['supported_commands'], ['volume','mute'])
                    self.assertEqual({f['codec'] for f in hello['player@v1_support']['supported_formats']}, {'pcm'})
                    state = next(m['payload'] for m in received if m['type']=='client/state')['player']
                    self.assertEqual(state['volume'],100)
                    self.assertFalse(state['muted'])
                    await socket.send_json({'type':'stream/start','payload':{'player':{'codec':'pcm','sample_rate':48000,'channels':2,'bit_depth':16}}})
                    await socket.send_bytes(bytes([4])+struct.pack('>q',time.monotonic_ns()//1000)+bytes(1920))
                    await eventually_async(lambda: source.status()['audio_chunks_received']==1)
                    self.assertEqual(source.status()['audio_bytes_received'],1920)
                    self.assertFalse(bridge.status()['audio_fresh'], 'audio must not drive LEDs or create a visualizer frame')
                    await socket.send_json({'type':'server/command','payload':{'player':{'command':'volume','volume':37}}})
                    await eventually_async(lambda: any(m['type']=='client/state' and m['payload'].get('player',{}).get('volume')==37 for m in received))
                    await socket.send_json({'type':'server/command','payload':{'player':{'command':'mute','mute':True}}})
                    await eventually_async(lambda: any(m['type']=='client/state' and m['payload'].get('player',{}).get('muted') is True for m in received))
                await socket.send_json({'type':'stream/start','payload':{'visualizer':{'types':['spectrum'],'rate_max':20,'spectrum':{'n_disp_bins':2}}}})
                due = time.monotonic_ns()//1000+250000
                await socket.send_bytes(bytes([19])+struct.pack('>qHH',due,0,65535))
                await asyncio.sleep(0.07)
                self.assertFalse(bridge.status()['audio_fresh'])
                await eventually_async(lambda: bridge.status()['audio_fresh'])
                self.assertEqual(bridge.bands,[0,1])
                await socket.send_json({'type':'group/update','payload':{'group_name':'Living Room','playback_state':'paused'}})
                await eventually_async(lambda: source.status()['playback']=='paused')
                self.assertFalse(bridge.status()['audio_fresh'])
            finally:
                source.stopping.set();await asyncio.wait_for(task,2)
                render.cancel();await asyncio.gather(render,return_exceptions=True)
                await runner.cleanup()

    async def test_noise_client_with_official_reference_server(self):
        await self.check_noise_stream(True)

    async def test_noise_visualizer_only_fallback(self):
        await self.check_noise_stream(False)

    async def check_noise_stream(self, player):
        from aiosendspin.server import SendspinServer
        from aiosendspin.models.core import StreamStartMessage, StreamStartPayload
        from aiosendspin.models.player import StreamStartPlayer
        from aiosendspin.models.types import AudioCodec
        server = SendspinServer(asyncio.get_running_loop(),Identity.generate(),'test',pairing_store=InMemoryServerPairingStore())
        self.addAsyncCleanup(server._client_session.close)
        runner = web.AppRunner(server._create_web_application());await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        site = web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port = site._server.sockets[0].getsockname()[1]
        bridge = Bridge({})
        source = SendspinSource(bridge,{'sendspin_url':f'ws://127.0.0.1:{port}/sendspin', 'sendspin_player':player})
        render = asyncio.create_task(source.render())
        with tempfile.TemporaryDirectory() as folder:
            identity = load_identity(Path(folder))
            store = await FileClientPairingStore.open(Path(folder)/'pairing.json')
            await store.store_pairing_config(replace(await store.get_pairing_config(),unpaired_access_enabled=True))
            async with ClientSession() as session:
                task = asyncio.create_task(source.modern(identity,store,session))
                try:
                    await eventually_async(lambda: server.get_client(identity.peer_id) is not None)
                    await server.trust_unpaired(identity.peer_id)
                    await eventually_async(lambda: source.status()['connected'])
                    client = server.get_client(identity.peer_id)
                    self.assertEqual(set(client.negotiated_role_ids),{'player@v1','visualizer@v1','artwork@v1'} if player else {'visualizer@v1','artwork@v1'})
                    await eventually_async(lambda: client.role('visualizer@v1') is not None)
                    client.group.start_stream()
                    await eventually_async(lambda: source.status()['playback']=='playing')
                    if player:
                        await eventually_async(lambda: client.role('player@v1') is not None)
                        self.assertEqual([c.value for c in client.info.player_support.supported_commands], ['volume','mute'])
                        self.assertEqual({f.codec for f in client.info.player_support.supported_formats}, {AudioCodec.PCM})
                        client.send_role_message('player',StreamStartMessage(payload=StreamStartPayload(player=StreamStartPlayer(codec=AudioCodec.PCM, sample_rate=48000, channels=2, bit_depth=16))))
                        stamp=server.clock.now_us()+300000
                        client.send_binary(bytes([4])+struct.pack('>q',stamp)+bytes(1920),role_family='player',timestamp_us=stamp,message_type=4)
                        await eventually_async(lambda: source.status()['audio_chunks_received']==1)
                        self.assertEqual(source.status()['audio_bytes_received'],1920)
                        self.assertFalse(bridge.status()['audio_fresh'])
                        role = client.role('player@v1')
                        await eventually_async(lambda: role.get_audio_requirements() is not None)
                        role.set_volume(37)
                        await eventually_async(lambda: role.volume==37)
                        role.set_mute(True)
                        await eventually_async(lambda: role.muted)
                    client.role('artwork@v1').send_artwork(0, b'cover-test', time.monotonic_ns()//1000)
                    await eventually_async(lambda: bridge.cover_data == b'cover-test')
                    client.send_role_message('visualizer',StreamStartMessage(payload=StreamStartPayload(visualizer=StreamStartVisualizer.from_support(source.support))))
                    # Give the protocol time filter its two initial samples.
                    await asyncio.sleep(0.6)
                    await eventually_async(lambda: source.status()['clock_synced'])
                    self.assertEqual(source.status()['frames_received'],0,
                        'clock status must update even before music frames arrive')
                    for _ in range(50):
                        stamp=server.clock.now_us()+400000
                        packet=bytes([19])+struct.pack('>q',stamp)+struct.pack('>32H',*([65535]*32))
                        client.send_binary(packet,role_family='visualizer',timestamp_us=stamp,message_type=19)
                        await asyncio.sleep(0.1)
                        if bridge.status()['audio_fresh']:
                            break
                    self.assertTrue(bridge.status()['audio_fresh'], repr(source.status()))
                    self.assertEqual(bridge.bands,[1]*32)
                    self.assertEqual(source.status()['protocol'],'noise')
                finally:
                    source.stopping.set();await asyncio.wait_for(task,2)
        render.cancel();await asyncio.gather(render,return_exceptions=True)
        await server.stop_server();await runner.cleanup()


if __name__ == '__main__':
    unittest.main()
