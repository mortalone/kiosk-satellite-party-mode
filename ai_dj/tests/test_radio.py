import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radio import Radio

class FakeDJ:
    def __init__(self):
        self.queue={'state':'playing','current_index':0,'items':1};self.requests=[];self.enqueues=[];self.jobs={};self.counter=0
    def queue_id(self):return 'existing-group'
    def ma(self,command,args):
        if command=='player_queues/get':return dict(self.queue)
        if command=='player_queues/items':return []
        raise AssertionError(command)
    def suggest(self,data,exclude=None):
        self.requests.append((data,exclude));key=str(len(self.requests));tracks=[]
        for i in range(data['count']):
            self.counter+=1;tracks.append({'name':'Song '+str(self.counter),'uri':'test://track/'+str(self.counter),'artists':[{'name':'Artist'}]})
        self.jobs[key]={'state':'ready','tracks':tracks,'id':key};return {'id':key}
    def job(self,key):return self.jobs[key]
    def enqueue(self,data,target_queue=None):
        assert target_queue=='existing-group'
        self.enqueues.append(data);count=len(self.jobs[data['id']]['tracks']);self.queue['items']+=count;return {'queued':count}

class RadioTest(unittest.TestCase):
    def test_fills_for_a_full_day_in_small_batches(self):
        dj=FakeDJ();radio=Radio(dj);radio.control({'action':'start','prompt':'Varieret jazz','option':'play'})
        for now in range(0,86400,20):
            if now and now%180==0:dj.queue['current_index']+=1
            radio.tick(now)
            self.assertGreater(dj.queue['items']-dj.queue['current_index'],0)
        self.assertGreater(len(dj.requests),60)
        self.assertTrue(all(data['count']<=8 for data,exclude in dj.requests))
        self.assertEqual(dj.enqueues[0]['option'],'play')
        self.assertTrue(all(e['option']=='add' for e in dj.enqueues[1:]))
        self.assertGreater(len(dj.requests[-1][1]),400)
        self.assertLessEqual(len(radio.history),500)
    def test_stop_while_ai_pending_never_enqueues(self):
        dj=FakeDJ();radio=Radio(dj);radio.control({'action':'start','prompt':'Jazz'})
        radio.tick(0);radio.control({'action':'stop'});radio.tick(20)
        self.assertEqual(dj.enqueues,[])
    def test_pause_and_player_stop_suspend_refilling(self):
        dj=FakeDJ();radio=Radio(dj);radio.control({'action':'start','prompt':'Jazz'})
        radio.tick(0);dj.queue['state']='paused';radio.tick(20)
        self.assertEqual(dj.enqueues,[])
        dj.queue['state']='playing';radio.tick(40);self.assertEqual(len(dj.enqueues),1)
        dj.queue.update(state='idle',current_index=dj.queue['items']-1);radio.tick(200)
        self.assertEqual(len(dj.requests),1);self.assertTrue(radio.status()['enabled'])
    def test_full_existing_queue_waits_and_replace_requires_confirmation(self):
        dj=FakeDJ();dj.queue['items']=200;radio=Radio(dj)
        with self.assertRaises(ValueError):radio.control({'action':'start','prompt':'Jazz','option':'replace'})
        radio.control({'action':'start','prompt':'Jazz','option':'add'});radio.tick(0)
        self.assertEqual(dj.requests,[])
    def test_retries_are_bounded(self):
        dj=FakeDJ();radio=Radio(dj);radio.control({'action':'start','prompt':'Jazz'})
        def fail(*args,**kwargs):dj.requests.append('error');raise ValueError('Quota')
        dj.suggest=fail
        radio.tick(0);radio.tick(20);radio.tick(119);self.assertEqual(len(dj.requests),1)
        radio.tick(120);self.assertEqual(len(dj.requests),2)

    def test_stop_player_while_first_ai_batch_pending_does_not_restart_it(self):
        dj=FakeDJ();radio=Radio(dj);radio.control({'action':'start','prompt':'Jazz','option':'play'})
        radio.tick(0);dj.queue['state']='idle';radio.tick(20)
        self.assertEqual(dj.enqueues,[])
