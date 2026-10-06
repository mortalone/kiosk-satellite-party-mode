import json
import sys
import time
import unittest
import threading
import tempfile
from unittest.mock import Mock
import requests
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dj import DJ, candidates_from, match_track, handler

def track(artist,title,uri='library://track/1',**kwargs):return {'name':title,'uri':uri,'artists':[{'name':artist}],**kwargs}
class TestDJ(unittest.TestCase):
    def test_matching_does_not_accept_wrong_artist_live_or_missing(self):
        c={'artist':'Queen','title':'We Will Rock You'}
        self.assertIsNone(match_track(c,[track('Other','We Will Rock You')]))
        self.assertIsNone(match_track(c,[track('Queen','We Will Rock You - Live')]))
        self.assertIsNone(match_track(c,[track('Queen','We Will Rock You',available=False)]))
        self.assertIsNotNone(match_track(c,[track('Queen','We Will Rock You - 2011 Remastered')]))
    def test_candidates_bounds_dates_and_duplicates(self):
        data={'tracks':[{'artist':'A','title':'B','year':1997},{'artist':'A','title':'B','year':1997},{'artist':'C','title':'D','year':2001}]}
        self.assertEqual(len(candidates_from(data,12,'1997')),1)
        with self.assertRaises(ValueError):candidates_from({'tracks':[]},12,'blandet')
    def test_openai_catalog_skip_and_queue_uses_only_resolved_uris(self):
        calls=[]
        def transport(url,token,data,timeout):
            calls.append(data)
            if url.endswith('chat/completions'):
                return {'choices':[{'message':{'content':json.dumps({'tracks':[{'artist':'A','title':'Real','year':1997},{'artist':'B','title':'Missing','year':1997},{'artist':'C','title':'Other','year':1997}]})}}]}
            if data['command']=='music/search':
                query=data['args']['search_query']
                return {'tracks':[track('A','Real')] if query=='A Real' else [track('C','Other','spotify://track/2')] if query=='C Other' else [track('Wrong','Missing')]}
            return None
        dj=DJ({'ai_engine':'openai_compatible','openai_base_url':'https://test/v1','openai_model':'test','music_assistant_url':'http://ma','queue_id':'group'},transport)
        key=dj.suggest({'prompt':'blandet 1997','count':3})['id']
        deadline=time.monotonic()+3
        while dj.job(key)['state']=='working' and time.monotonic()<deadline:time.sleep(.02)
        job=dj.job(key);self.assertEqual(job['state'],'ready');self.assertEqual(len(job['tracks']),2);self.assertEqual(len(job['skipped']),1)
        dj.enqueue({'id':key,'indices':[0,1],'option':'next'})
        self.assertEqual(calls[-1]['args'],{'queue_id':'group','media':['library://track/1','spotify://track/2'],'option':'next'})
        with self.assertRaises(ValueError):dj.enqueue({'id':key})
        dj.worker.shutdown()
    def test_ha_ai_task_response(self):
        def transport(url,token,data,timeout):
            self.assertIn('return_response',url);self.assertEqual(data['entity_id'],'ai_task.example')
            return {'service_response':{'data':'{"tracks":[{"artist":"A","title":"B","year":1997}]}'}}
        dj=DJ({'ai_task_entity':'ai_task.example'},transport)
        self.assertEqual(dj.generate('1997',1)[0]['title'],'B');dj.worker.shutdown()

    def test_guest_api_requires_capability_and_ingress_rejects_direct_clients(self):
        dj=DJ({'api_token':'a'*32})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(dj))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            self.assertEqual(requests.get(base+'/health',timeout=2).status_code,200)
            self.assertEqual(requests.post(base+'/api/suggest',json={'prompt':'jazz'},timeout=2).status_code,401)
            self.assertEqual(requests.get(base+'/api/jobs/missing',headers={'Authorization':'Bearer '+'a'*32},timeout=2).status_code,400)
            self.assertEqual(requests.get(base+'/api/admin/ai',headers={'Authorization':'Bearer '+'a'*32},timeout=2).status_code,403)
            self.assertEqual(requests.post(base+'/api/admin/ai',json={'entity_id':'ai_task.example'},headers={'Authorization':'Bearer '+'a'*32},timeout=2).status_code,403)
        finally:server.shutdown();server.server_close()
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(dj,True))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:self.assertEqual(requests.get('http://127.0.0.1:'+str(server.server_port)+'/',timeout=2).status_code,401)
        finally:server.shutdown();server.server_close();dj.worker.shutdown()

    def test_ai_selection_filters_capability_and_persists(self):
        states=[{'entity_id':'ai_task.google_ai_task','state':'unknown','attributes':{'friendly_name':'Google AI','supported_features':1}},
                {'entity_id':'ai_task.images','attributes':{'supported_features':2}},
                {'entity_id':'ai_task.offline','state':'unavailable','attributes':{'supported_features':1}},
                {'entity_id':'conversation.example','attributes':{'supported_features':1}}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'selection.json';dj=DJ({},selection_path=path);dj.ha_get=Mock(return_value=states)
            self.assertEqual(len(dj.ai_choices()['entities']),2)
            with self.assertRaises(ValueError):dj.select_ai({'entity_id':'ai_task.offline'})
            dj.select_ai({'entity_id':'ai_task.google_ai_task'})
            restored=DJ({},selection_path=path)
            self.assertEqual(restored.options['ai_task_entity'],'ai_task.google_ai_task')
            self.assertEqual(restored.options['ai_engine'],'ha_task')
            dj.worker.shutdown();restored.worker.shutdown()
    def test_empty_ai_entity_is_actionable_without_calling_ha(self):
        transport=Mock();dj=DJ({},transport)
        with self.assertRaisesRegex(ValueError,'Vælg din HA AI Task'):dj.generate('jazz',2)
        transport.assert_not_called();dj.worker.shutdown()
    def test_ha_player_resolves_active_queue(self):
        transport=Mock(return_value=None);dj=DJ({'queue_id':'media_player.stueetagen_visualizer','music_assistant_url':'http://ma'},transport)
        dj.ha_get=Mock(return_value={'attributes':{'active_queue':'ugp_existing'}})
        dj.jobs['test']={'id':'test','created':time.monotonic(),'state':'ready','queued':False,'tracks':[track('A','B')]}
        dj.enqueue({'id':'test','option':'add'})
        dj.ha_get.assert_called_once_with('states/media_player.stueetagen_visualizer')
        self.assertEqual(transport.call_args.args[2]['args']['queue_id'],'ugp_existing')
        dj.worker.shutdown()
