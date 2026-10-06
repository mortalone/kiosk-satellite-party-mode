"""Audio-level regressions: tonal interference, varied kicks and chunk timing."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bass import PcmBass, BassEnvelope


def pcm(signal):
    samples = np.clip(signal * 32767, -32768, 32767).astype('<i2')
    return np.repeat(samples, 2).tobytes()


def features(signal, rate=48000, chunks=None):
    analyzer = PcmBass()
    data = pcm(signal)
    result = []
    position = 0
    chunks = chunks or [round(rate * .1)]
    index = 0
    while position < len(data):
        count = chunks[index % len(chunks)] * 4
        result.extend(analyzer.feed(data[position:position+count],
                      round(position / 4 / rate * 1e6), rate, 2))
        position += count
        index += 1
    return result


def hits(frames, spectral=True):
    envelope = BassEnvelope()
    return [frame.timestamp_us / 1e6 for frame in frames
            if envelope.feed(frame.bass_rms, frame.timestamp_us / 1e6,
                             frame.onset if spectral else None)]


def kicks(rate, seconds, times, frequency=75, amplitude=.25, click=.02):
    time = np.arange(round(rate * seconds)) / rate
    signal = np.zeros(len(time))
    rng = np.random.default_rng(104729)
    for start in times:
        age = time - start
        selected = (age >= 0) & (age < .3)
        age = age[selected]
        # Pitch-dropping drum body plus a short unpitched beater attack.
        signal[selected] += amplitude * (
            np.sin(2*np.pi*(frequency*age + 6*(1-np.exp(-age/.015))))
            * np.exp(-age/.08)
            + click * rng.normal(size=len(age)) * np.exp(-age/.006))
    return signal


class TestSpectralOnsets(unittest.TestCase):
    def assert_tracks(self, found, expected, tolerance=.065):
        self.assertEqual(len(found), len(expected), (found, expected))
        for actual, target in zip(found, expected):
            self.assertGreaterEqual(actual, target)
            self.assertLessEqual(actual-target, tolerance)

    def test_close_tones_do_not_create_a_four_hz_beat_clock(self):
        time = np.arange(48000*6)/48000
        frames = features(.1*(np.sin(2*np.pi*90*time)+np.sin(2*np.pi*94*time)))
        self.assertGreaterEqual(len(hits(frames, spectral=False)), 20)
        self.assertEqual(hits(frames), [])

    def test_held_tone_vibrato_tremolo_and_slow_fade(self):
        time = np.arange(48000*3)/48000
        signals = [np.sin(2*np.pi*90*time),
                   np.sin(2*np.pi*90*time+1.2*np.sin(2*np.pi*6*time)),
                   np.sin(2*np.pi*90*time)*(.6+.4*np.sin(2*np.pi*4*time)),
                   np.sin(2*np.pi*90*time)*np.minimum(1,time/1.5)]
        for index, signal in enumerate(signals):
            with self.subTest(signal=index):
                self.assertEqual(hits(features(.2*signal)), [])

    def test_kicks_at_varied_rates_pitches_and_levels(self):
        for rate, frequency, amplitude, interval in [
                (48000,45,.25,.5), (44100,75,.25,.375),
                (48000,140,.25,.5), (44100,75,.003,.25),
                (48000,60,.08,.18)]:
            expected = list(np.arange(.5,2.6,interval))
            with self.subTest(rate=rate,frequency=frequency,amplitude=amplitude,interval=interval):
                self.assert_tracks(hits(features(kicks(rate,3,expected,frequency,amplitude),rate)), expected)

    def test_no_second_flash_at_end_of_drum_decay(self):
        expected = [.5, 1.5, 2.5]
        self.assert_tracks(hits(features(kicks(48000,3,expected,click=0))), expected)

    def test_sine_body_kick_without_click_or_pitch_sweep(self):
        time = np.arange(48000*3)/48000
        expected = [.5,1.,1.5,2.,2.5]
        for frequency in (40,80,120):
            signal = np.zeros(len(time))
            for start in expected:
                age = time-start
                selected = (age>=0)&(age<.3)
                signal[selected] += .2*np.sin(2*np.pi*frequency*age[selected])*np.exp(-age[selected]/.08)
            with self.subTest(frequency=frequency):
                self.assert_tracks(hits(features(signal)),expected)

    def test_scheduled_features_reach_bridge_and_diagnostic(self):
        from bridge import Bridge
        from sendspin_source import FrameBuffer
        bridge = Bridge({})
        bridge.diagnostic.start({})
        buffer = FrameBuffer(bridge)
        for frame in features(kicks(48000,1,[.5])):
            due = 10 + frame.timestamp_us/1e6
            self.assertTrue(buffer.add(frame,due,now=due-.1))
            buffer.drain(now=due)
        self.assertEqual(bridge.bass_hits,1)
        decisions = [e for e in bridge.diagnostic.export()['events'] if e['kind']=='bass']
        self.assertTrue(all(e['detector']=='spectral_attack' for e in decisions))
        self.assertEqual(sum(e['hit'] for e in decisions),1)
        self.assertTrue(all(len(e['onset'])==4 for e in decisions))

    def test_treble_transients_without_bass_do_not_flash(self):
        rate = 48000
        time = np.arange(rate*3)/rate
        signal = np.zeros(len(time))
        for start in (.5, 1., 1.5, 2.):
            age = time-start
            selected = (age>=0)&(age<.2)
            signal[selected] = .2*np.sin(2*np.pi*1500*age[selected])*np.exp(-age[selected]/.04)
        self.assertEqual(hits(features(signal)), [])

    def test_bass_kicks_remain_visible_over_held_tone_and_voice(self):
        time = np.arange(48000*3)/48000
        expected = [.5,1.,1.5,2.,2.5]
        signal = kicks(48000,3,expected) + .025*np.sin(2*np.pi*94*time) + .12*np.sin(2*np.pi*850*time)
        self.assert_tracks(hits(features(signal)), expected)

    def test_packet_boundaries_do_not_change_features_or_timestamps(self):
        signal = kicks(44100,2,[.5,1.,1.5])
        regular = features(signal,44100)
        fragmented = features(signal,44100,[17,1323,441,87,2205])
        self.assertEqual([f.timestamp_us for f in regular], [f.timestamp_us for f in fragmented])
        np.testing.assert_allclose([f.onset for f in regular], [f.onset for f in fragmented])
        self.assertEqual(hits(regular),hits(fragmented))

    def test_stream_reset_discards_spectral_history(self):
        analyzer = PcmBass()
        signal = pcm(kicks(48000,1,[.5]))
        analyzer.feed(signal,0,48000,2)
        analyzer.reset()
        silence = analyzer.feed(bytes(48000*4),10_000_000,48000,2)
        self.assertEqual(hits(silence),[])
        self.assertTrue(all(f.onset == (0.,0.,0.,0.) for f in silence))
