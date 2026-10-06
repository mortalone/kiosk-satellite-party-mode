"""Bounded PCM bass/attack features, scheduled against Sendspin playback time."""
import math
import struct
from collections import deque
from dataclasses import dataclass
import numpy as np

@dataclass
class BassFrame:
    timestamp_us: int
    bass_rms: float
    spectrum: object = None
    loudness: object = None
    peak_strength: object = None
    onset: object = None


class SpectralAttack:
    """Causal maximum-filter spectral flux, inspired by SuperFlux.

    This is a bass-focused adaptation, not the original SuperFlux algorithm or
    a drum separator. Hann-windowed spectra and a three-bin maximum reference
    suppress small pitch movements. A simultaneous broadband attack rejects
    slow tonal beating. The rolling history is 2048 mono samples and one spectrum,
    plus the partial 20 ms PCM window in PcmBass; no recording is kept.
    Reference: https://librosa.org/doc/0.11.0/auto_examples/plot_superflux.html
    """
    size = 2048

    def __init__(self, rate):
        self.audio = np.zeros(self.size)
        self.window = np.hanning(self.size)
        self.previous = None
        frequencies = np.fft.rfftfreq(self.size, 1 / rate)
        self.low = (frequencies >= 35) & (frequencies <= 180)
        self.attack = (frequencies >= 180) & (frequencies <= 2500)

    def feed(self, samples):
        count = len(samples)
        if count >= self.size:
            self.audio[:] = samples[-self.size:]
        else:
            self.audio[:-count] = self.audio[count:]
            self.audio[-count:] = samples
        magnitude = np.abs(np.fft.rfft(self.audio * self.window)) / (self.size / 2)
        logged = np.log1p(magnitude / .00002)
        if self.previous is None:
            self.previous = magnitude
            return (0., 0., 0., 0.)
        reference = np.maximum.reduce((self.previous,
            np.r_[self.previous[0], self.previous[:-1]],
            np.r_[self.previous[1:], self.previous[-1]]))
        flux = np.maximum(0, logged - np.log1p(reference / .00002))
        change = np.maximum(0, magnitude - reference)
        power = float(np.sum(change[self.low] ** 2))
        attack_power = float(np.sum(change[self.attack] ** 2))
        bass_power = float(np.sum(magnitude[self.low] ** 2))
        wide_power = float(np.sum(magnitude[self.attack] ** 2))
        self.previous = magnitude
        return (float(np.mean(flux[self.low])),
                float(np.mean(flux[self.attack])),
                attack_power / max(1e-12, power + attack_power),
                bass_power / max(1e-12, bass_power + wide_power))

class Biquad:
    def __init__(self, rate, cutoff, highpass=False):
        w=2*math.pi*cutoff/rate; c=math.cos(w); a=math.sin(w)/(2*math.sqrt(.5))
        if highpass: b0,b1,b2=(1+c)/2,-(1+c),(1+c)/2
        else: b0,b1,b2=(1-c)/2,1-c,(1-c)/2
        self.b0,self.b1,self.b2=b0/(1+a),b1/(1+a),b2/(1+a)
        self.a1,self.a2=-2*c/(1+a),(1-a)/(1+a);self.z1=self.z2=0.
    def sample(self,x):
        y=self.b0*x+self.z1;self.z1=self.b1*x-self.a1*y+self.z2;self.z2=self.b2*x-self.a2*y;return y

class PcmBass:
    def __init__(self): self.reset()
    def reset(self):
        self.format=None;self.high=self.low=None;self.power=0.;self.samples=0;self.expected=None
        self.attack=None;self.mono=[]
    def feed(self,data,timestamp_us,rate,channels,bits=16):
        if rate not in (44100,48000) or channels!=2 or bits!=16 or len(data)>1048576 or len(data)%4: return []
        if self.format!=(rate,channels,bits) or (self.expected is not None and abs(timestamp_us-self.expected)>100000):
            self.reset();self.format=(rate,channels,bits);self.high=Biquad(rate,45,True);self.low=Biquad(rate,160)
            self.attack=SpectralAttack(rate)
        count=len(data)//4;self.expected=timestamp_us+round(count*1000000/rate);window=round(rate*.02);result=[]
        for index,(left,right) in enumerate(struct.iter_unpack('<hh',data)):
            mono=(left+right)/65536;self.mono.append(mono)
            value=self.low.sample(self.high.sample(mono));self.power+=value*value;self.samples+=1
            if self.samples>=window:
                result.append(BassFrame(timestamp_us+round((index+1)*1000000/rate), math.sqrt(self.power/self.samples),
                                        onset=self.attack.feed(self.mono)))
                self.samples=0;self.power=0.;self.mono=[]
        return result

class BassEnvelope:
    """Inspect every scheduled PCM window; retain hits until the LED renderer samples."""
    def __init__(self):
        self.previous=None;self.baseline=None;self.last_at=None;self.hit_at=None;self.strength=0.
        self.flux_history=deque(maxlen=50);self.onset_threshold=0.
        self.attack_at=None
    def feed(self,rms,at,onset=None):
        if self.last_at is not None and (at<self.last_at or at-self.last_at>.3):self.__init__()
        dt=.02 if self.last_at is None else max(.001,min(.25,at-self.last_at))
        hit=False
        if onset is not None:
            low_flux,attack_flux,attack_fraction,bass_fraction=onset
            history=np.asarray(self.flux_history)
            median=float(np.median(history)) if len(history) else 0.
            deviation=float(np.median(np.abs(history-median))) if len(history) else 0.
            self.onset_threshold=max(.12,median+3*deviation)
            ready=self.hit_at is None or at-self.hit_at>=.12
            if attack_flux>.025 and attack_fraction>.003:
                self.attack_at=at
            sharp=self.attack_at is not None and at-self.attack_at<=.06
            # Require a new bass rise AND a sharp attack outside the bass band.
            # No tempo oscillator: silence, held notes and spectral decay cannot
            # generate a pulse merely because the refractory interval elapsed.
            rising=self.previous is not None and rms>self.previous*1.03
            if (ready and rising and rms>max(.00001,(self.baseline or 0)*1.15)
                    and bass_fraction>.25 and low_flux>self.onset_threshold and sharp):
                self.strength=min(1.,max(.55,low_flux/max(.12,self.onset_threshold)*.55))
                self.hit_at=at;hit=True
            self.flux_history.append(low_flux)
        elif self.previous is not None:
            rising=rms>self.previous*1.12
            ready=self.hit_at is None or at-self.hit_at>=.16
            base=self.baseline or 0
            if rising and ready and rms>max(.00001,base*1.2):
                self.strength=min(1.,max(.55,(rms-base)/max(.00001,base or rms)*1.5))
                self.hit_at=at;hit=True
        self.baseline=rms if self.baseline is None else self.baseline+(rms-self.baseline)*(1-math.exp(-dt/.35))
        self.previous=rms;self.last_at=at
        return hit
    def pulse(self,now,punch):
        if self.hit_at is None:return 0.
        return self.strength*math.exp(-max(0,now-self.hit_at)/(.4-.3*punch/100))
    def level(self,rms):
        return min(1.,rms/max(.0001,(self.baseline or 0)*2))
