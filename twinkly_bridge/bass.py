"""Timestamped 45–160 Hz PCM envelope; no FFT, audio device or retained audio."""
import math
import struct
from dataclasses import dataclass

@dataclass
class BassFrame:
    timestamp_us: int
    bass_rms: float
    spectrum: object = None
    loudness: object = None
    peak_strength: object = None

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
    def feed(self,data,timestamp_us,rate,channels,bits=16):
        if rate not in (44100,48000) or channels!=2 or bits!=16 or len(data)>1048576 or len(data)%4: return []
        if self.format!=(rate,channels,bits) or (self.expected is not None and abs(timestamp_us-self.expected)>100000):
            self.reset();self.format=(rate,channels,bits);self.high=Biquad(rate,45,True);self.low=Biquad(rate,160)
        count=len(data)//4;self.expected=timestamp_us+round(count*1000000/rate);window=round(rate*.02);result=[]
        for index,(left,right) in enumerate(struct.iter_unpack('<hh',data)):
            value=self.low.sample(self.high.sample((left+right)/65536));self.power+=value*value;self.samples+=1
            if self.samples>=window:
                result.append(BassFrame(timestamp_us+round((index+1)*1000000/rate), math.sqrt(self.power/self.samples)))
                self.samples=0;self.power=0.
        return result

class BassEnvelope:
    """Inspect every scheduled PCM window; retain hits until the LED renderer samples."""
    def __init__(self):
        self.previous=None;self.baseline=None;self.last_at=None;self.hit_at=None;self.strength=0.
    def feed(self,rms,at):
        if self.last_at is not None and (at<self.last_at or at-self.last_at>.3):self.__init__()
        dt=.02 if self.last_at is None else max(.001,min(.25,at-self.last_at))
        hit=False
        if self.previous is not None:
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
