import math
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bass import PcmBass, BassFrame
from bridge import Bridge, MusicDynamics
from sendspin_source import FrameBuffer, SendspinSource
from types import SimpleNamespace
from unittest.mock import patch

def tone(frequency, amplitude=.2, rate=48000, seconds=.5):
    return b''.join(struct.pack('<hh',*( [round(32767*amplitude*math.sin(2*math.pi*frequency*i/rate))]*2)) for i in range(round(rate*seconds)))

class TestBass(unittest.TestCase):
    def test_filter_rejects_voice_band(self):
        bass=PcmBass().feed(tone(90),0,48000,2)
        treble=PcmBass().feed(tone(1500),0,48000,2)
        low=sum(f.bass_rms for f in bass[5:]);high=sum(f.bass_rms for f in treble[5:])
        self.assertGreater(low,high*40)
        self.assertEqual(bass[0].timestamp_us,20000)
    def test_pcm_due_time_not_arrival(self):
        bridge=Bridge({});buffer=FrameBuffer(bridge)
        buffer.add(BassFrame(20000,.1),10.5,now=10)
        self.assertEqual(buffer.drain(now=10.4),0);self.assertEqual(bridge.bass_rms,0)
        self.assertEqual(buffer.drain(now=10.5),0);self.assertEqual(bridge.bass_rms,.1)
        buffer.clear();self.assertEqual(bridge.bass_rms,0)
    def test_punch_tracks_bass_even_with_loud_vocals_and_peaks(self):
        dynamics=MusicDynamics();pulses=[]
        for i in range(100):
            bass=.015 if i%25 in (2,3,4) else .0001
            pulses.append(dynamics.process([.8]*32,1,1,1.5,100,.02,bass)[2])
        self.assertGreater(pulses[2],.8)
        self.assertLess(pulses[20],.05)
        self.assertGreater(pulses[27],.8)
        self.assertLess(pulses[45],.05)
    def test_quiet_bass_still_has_punch(self):
        dynamics=MusicDynamics()
        for i in range(10):dynamics.process([.4]*32,.5,0,1,100,.02,.00001)
        self.assertGreater(dynamics.process([.4]*32,.5,0,1,100,.02,.0007)[2],.8)
    def test_unsupported_and_invalid_formats(self):
        analyzer=PcmBass()
        self.assertEqual(analyzer.feed(b'123',0,48000,2),[])
        self.assertEqual(analyzer.feed(b'0000',0,48000,2,24),[])

    def test_source_callback_analyzes_pcm_with_playback_delay(self):
        bridge=Bridge({});source=SendspinSource(bridge,{'light_delay_ms':100})
        source.clock_client=SimpleNamespace(is_time_synchronized=lambda:True,compute_play_time=lambda stamp:stamp+500000,now_us=lambda:0)
        audio=SimpleNamespace(pcm_format=SimpleNamespace(sample_rate=48000,channels=2,bit_depth=16),codec=SimpleNamespace(value='pcm'))
        with patch('sendspin_source.time.monotonic',return_value=10):
            source.receive_audio(0,tone(90,seconds=.04),audio)
        self.assertEqual(source.status()['audio_chunks_received'],1)
        self.assertEqual(len(source.buffer.frames),2)
        source.buffer.drain(now=10.61);self.assertEqual(bridge.bass_rms,0)
        source.buffer.drain(now=10.63);self.assertGreater(bridge.bass_rms,.01)
        source.set_delay(300)
        self.assertAlmostEqual(source.buffer.frames[0][0],10.84)
        source.clear_stream();self.assertEqual(bridge.bass_rms,0)
