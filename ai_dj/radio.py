"""Small rolling DJ batches. Host-controlled; never restart a stopped player."""
import threading
import time
from collections import deque

OPTIONS={'add','next','play','replace','replace_next'}

class Radio:
    def __init__(self,dj):
        self.dj=dj;self.lock=threading.Lock();self.wake=threading.Event();self.epoch=0
        self.info={'enabled':False,'status':'DJ er stoppet','added':0,'remaining':0}
        self.history=deque(maxlen=500);self.pending=None;self.first=True;self.queue=None;self.after=0;self.requested_state=None
    def status(self):
        with self.lock:return dict(self.info)
    def control(self,data):
        if data.get('action')=='stop':
            with self.lock:
                self.epoch+=1;self.info.update(enabled=False,status='DJ stoppet · køen bevares');self.pending=None
            self.wake.set();return self.status()
        if data.get('action')!='start':raise ValueError('Vælg start eller stop')
        prompt=data.get('prompt','');option=data.get('option','add')
        if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=1000:raise ValueError('Skriv et musikønske på 1–1000 tegn')
        if option not in OPTIONS:raise ValueError('Ukendt køvalg')
        if option=='replace' and data.get('confirm_replace') is not True:raise ValueError('Bekræft at hele den eksisterende kø skal erstattes')
        self.dj.queue_id()  # Validate configured target before arming the DJ.
        with self.lock:
            if self.info['enabled']:raise ValueError('Stop den aktive DJ før du starter med et nyt ønske')
            self.epoch+=1;self.info={'enabled':True,'prompt':prompt.strip(),'option':option,'status':'DJ starter…','added':0,'remaining':0}
            self.pending=None;self.first=True;self.queue=None;self.after=0;self.requested_state=None
        self.wake.set();return self.status()
    def tick(self,now=None):
        now=time.monotonic() if now is None else now
        with self.lock:
            if not self.info['enabled'] or now<self.after:return
            epoch=self.epoch;pending=self.pending;first=self.first;info=dict(self.info)
        try:
            queue_id=self.dj.queue_id()
            queue=self.dj.ma('player_queues/get',{'queue_id':queue_id})
            if not isinstance(queue,dict):raise ValueError('MA-køen blev ikke fundet')
            if self.queue and self.queue!=queue_id:raise ValueError('Den aktive MA-kø er skiftet; stop og start DJ for det nye mål')
            state=queue.get('state','idle');index=queue.get('current_index');total=int(queue.get('items',0))
            remaining=max(0,total-(int(index)+1 if index is not None else 0))
            with self.lock:
                if epoch!=self.epoch or not self.info['enabled']:return
                self.queue=queue_id;self.info['remaining']=remaining
                if state=='paused' or (not first and state!='playing'):
                    self.info['status']='DJ venter · afspilleren er pauset eller stoppet';return
                if pending is None and remaining>3 and (not first or info['option']=='add'):
                    self.first=False
                    self.info['status']=f'DJ aktiv · {remaining} numre foran';return
            if pending is None:
                existing=self.dj.ma('player_queues/items',{'queue_id':queue_id,'offset':max(0,int(index or 0)),'limit':128})
                exclude=list(self.history)
                for item in existing or []:
                    media=item.get('media_item') or {}
                    artists=media.get('artists') or []
                    exclude.append({'uri':media.get('uri',''),'artist':artists[0].get('name','') if artists else '', 'title':media.get('name','')})
                count=8 if first else max(1,min(8,8-remaining))
                result=self.dj.suggest({'prompt':info['prompt'],'count':count},exclude=exclude)
                with self.lock:
                    if epoch!=self.epoch or not self.info['enabled']:return
                    self.pending=result['id'];self.requested_state=state;self.info['status']='DJ finder næste lille portion musik…'
                return
            job=self.dj.job(pending)
            if job['state']=='working':
                with self.lock:
                    if epoch==self.epoch:self.info['status']=job.get('progress','DJ arbejder…')
                return
            if job['state']=='error':raise ValueError(job.get('error','AI-forespørgslen fejlede'))
            if not job['tracks']:raise ValueError('Ingen nye katalogmatches; DJ prøver igen om 2 minutter')
            # Serialize stop/start with the final queue mutation. A stopped or superseded
            # session cannot enqueue the result of an AI request that was in flight.
            with self.lock:
                if epoch!=self.epoch or not self.info['enabled']:return
                option=info['option'] if first else 'add'
                latest=self.dj.ma('player_queues/get',{'queue_id':queue_id})
                if latest.get('state')=='paused' or (latest.get('state')!='playing' and (not first or self.requested_state=='playing')):
                    self.info['status']='DJ venter · afspilleren er pauset eller stoppet';return
                added=self.dj.enqueue({'id':pending,'option':option,'confirm_replace':option=='replace'},target_queue=queue_id)['queued']
                for track in job['tracks']:
                    artists=track.get('artists') or []
                    self.history.append({'uri':track['uri'],'artist':artists[0].get('name','') if artists else '', 'title':track['name']})
                self.first=False;self.pending=None;self.after=now+120
                self.info['added']+=added;self.info['status']=f'DJ tilføjede {added} numre · holder nu køen fyldt'
        except Exception as error:
            with self.lock:
                if epoch==self.epoch:
                    self.pending=None;self.after=now+120;self.info['status']='DJ venter 2 minutter: '+str(error)[:220]
    def run(self):
        while True:
            self.wake.wait(20);self.wake.clear();self.tick()
    def start_worker(self):threading.Thread(target=self.run,daemon=True).start()
