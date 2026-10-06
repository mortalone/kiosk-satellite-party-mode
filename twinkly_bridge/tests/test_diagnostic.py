import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from diagnostic import Diagnostic
from bridge import Bridge
from sendspin_source import FrameBuffer
from bass import BassFrame

class DiagnosticTest(unittest.TestCase):
    def test_opt_in_timeout_and_restart(self):
        now=[10.];trace=Diagnostic(clock=lambda:now[0])
        trace.add('bass',rms=.1);self.assertEqual(trace.export()['events'],[])
        trace.start({'settings':{'pattern':'pulse'}})
        trace.add('bass',rms=.1);now[0]=70.
        trace.add('bass',rms=.2)
        self.assertFalse(trace.status()['active'])
        self.assertEqual(len(trace.export()['events']),1)
        trace.start({});self.assertEqual(trace.status()['events'],0)
        trace.stop();trace.add('bass');self.assertEqual(trace.status()['events'],0)

    def test_bounded_and_metadata_isolation(self):
        trace=Diagnostic(limit=2);metadata={'settings':{'pattern':'pulse'}}
        trace.start(metadata);metadata['settings']['pattern']='mirror'
        for _ in range(3):trace.add('bass',rms=.1)
        self.assertEqual(trace.status()['events'],2)
        self.assertTrue(trace.status()['truncated']);self.assertFalse(trace.status()['active'])
        self.assertEqual(trace.export()['metadata']['settings']['pattern'],'pulse')

    def test_capture_actual_bass_decisions_and_rejected_schedule(self):
        bridge=Bridge({});bridge.diagnostic.start({})
        buffer=FrameBuffer(bridge)
        buffer.add(BassFrame(0,.1),9,now=10)
        bridge.bass(.0001,10);bridge.bass(.015,10.02)
        events=bridge.diagnostic.export()['events']
        self.assertEqual(events[0]['reason'],'past_due')
        self.assertFalse(events[0]['accepted'])
        self.assertFalse(events[1]['hit']);self.assertTrue(events[2]['hit'])
        self.assertNotIn('pcm',events[2])

    def test_led_trace_records_output_and_source(self):
        from test_bridge import FakeDevice, eventually
        bridge=Bridge({'fps':30,'device_ip':'192.168.0.165'},factory=lambda _host:FakeDevice())
        bridge.diagnostic.start({})
        bridge.control({'mode':'music','pattern':'pulse','punch':100})
        bridge.bass(.0001);bridge.bass(.015)
        bridge.thread.start()
        try:
            eventually(lambda:any(e['kind']=='led' for e in bridge.diagnostic.export()['events']))
        finally:
            bridge.stopping.set();bridge.wake.set();bridge.thread.join(timeout=2)
        event=next(e for e in bridge.diagnostic.export()['events'] if e['kind']=='led')
        self.assertEqual(event['bass_source'],'pcm')
        self.assertEqual(event['pattern'],'pulse')
        self.assertGreater(event['brightness_max'],0)
        self.assertGreaterEqual(event['send_ms'],0)
