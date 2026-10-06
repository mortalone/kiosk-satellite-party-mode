import math
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bass import PcmBass, BassFrame, BassEnvelope
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

    def test_short_hit_survives_between_led_frames_without_spectrum(self):
        bridge=Bridge({});buffer=FrameBuffer(bridge)
        for at,rms in [(10,.0001),(10.02,.015),(10.04,.0001)]:
            self.assertTrue(buffer.add(BassFrame(0,rms),at,now=9.9))
        self.assertEqual(buffer.drain(now=10.05),0)
        self.assertEqual(bridge.bass_rms,.0001)
        self.assertEqual(bridge.bass_hits,1)
        bands,level,peak,rms,pulse=bridge.audio_snapshot(10.05,100)
        self.assertEqual(len(bands),32)
        self.assertGreater(pulse,.7)
        output=MusicDynamics().process(bands,level,peak,1,100,.05,rms,pulse)
        self.assertGreater(output[2],.7)
        with patch('bridge.time.monotonic',return_value=10.05):
            status=bridge.status()
        self.assertTrue(status['audio_fresh']);self.assertFalse(status['spectrum_fresh'])
        self.assertTrue(status['bass_fresh'])
        self.assertEqual(bridge.audio_snapshot(10.3,100),([],0,0,None,None))
        bridge.clear_audio();self.assertEqual(bridge.bass_envelope.pulse(10.05,100),0)

    def test_sampled_pulse_uses_playback_time_not_drain_time(self):
        bridge=Bridge({});buffer=FrameBuffer(bridge)
        buffer.add(BassFrame(0,.0001),10,now=9.9)
        buffer.add(BassFrame(0,.015),10.02,now=9.9)
        buffer.drain(now=10.15)
        self.assertAlmostEqual(bridge.bass_envelope.pulse(10.15,100),math.exp(-.13/.1))
        # A device HTTP delay must cause a fresh read, not replay an old pulse.
        self.assertIsNone(bridge.audio_snapshot(10.4,100)[4])

    def test_repeated_hits_and_sustained_tone_have_no_synthetic_clock(self):
        envelope=BassEnvelope();hits=[]
        for i in range(100):
            if envelope.feed(.015 if i%25 in (2,3,4) else .0001,i*.02):hits.append(i)
        self.assertEqual(hits,[2,27,52,77])
        steady=BassEnvelope()
        self.assertFalse(any(steady.feed(.015,i*.02) for i in range(100)))
        self.assertFalse(steady.feed(0,5))
        self.assertEqual(steady.pulse(5,100),0)

    def test_late_pcm_does_not_replay_a_hit(self):
        bridge=Bridge({});buffer=FrameBuffer(bridge)
        buffer.add(BassFrame(0,.015),10,now=9.9)
        buffer.drain(now=10.4)
        self.assertEqual(bridge.bass_hits,0)
        self.assertEqual(bridge.bass_at,0)
