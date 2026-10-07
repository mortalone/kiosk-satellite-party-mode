import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Portal


def track(i):
    return {'uri': f'library://track/{i}', 'name': f'Song {i}', 'artists': [{'name': f'Artist {i}'}]}


class ContinuationTest(unittest.TestCase):
    def setUp(self):
        self.portal = Portal({'queue_id': 'group'})
        self.portal.party_policy.update(continuous=True, auto_method='favorites')
        self.items = [{'queue_item_id': 'q0', 'media_item': track(0)}]
        self.state = 'playing'
        self.calls = []
        self.pool = [track(i) for i in range(1, 8)]
        self.portal.ma = self.ma
        self.fill = self.portal.continuation

    def ma(self, command, args):
        if command == 'player_queues/get':
            return {'state': self.state, 'current_index': 0, 'items': len(self.items), 'current_item': self.items[0]}
        if command == 'player_queues/items': return list(self.items)
        if command in {'music/tracks/library_items', 'music/tracks/similar_tracks'}: return list(self.pool)
        if command == 'player_queues/play_media':
            self.calls.append(args)
            for uri in args['media']:
                self.items.append({'queue_item_id': 'auto-'+str(len(self.calls))+'-'+uri, 'media_item': next(t for t in self.pool if t['uri'] == uri)})
            return
        raise AssertionError(command)

    def test_one_track_default_and_full_guest_queue(self):
        self.fill.tick(100)
        self.assertEqual(len(self.calls[0]['media']), 1)
        self.assertEqual(self.calls[0]['option'], 'add')
        self.items.extend({'queue_item_id': 'guest'+str(i), 'media_item': track(i)} for i in range(10, 13))
        self.fill.guest_added()
        self.fill.tick(120)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.fill.pending)

    def test_pause_stop_disabled_never_start(self):
        for state in ['paused', 'idle', 'stopped']:
            self.state = state
            self.fill.tick(100)
        self.state = 'playing'
        self.portal.party_policy['continuous'] = False
        self.fill.tick(110)
        self.assertEqual(self.calls, [])

    def test_target_five_is_bounded_even_if_more_candidates(self):
        self.portal.party_policy['auto_count'] = 5
        self.fill.tick(100)
        self.assertEqual(len(self.calls[0]['media']), 5)
        self.fill.tick(120)
        self.assertEqual(len(self.calls), 1)

    def test_favorites_repeat_only_after_pool_exhausted(self):
        self.pool = [track(1), track(2)]
        played = []
        for step in range(6):
            self.fill.tick(100+step*20)
            played.append(self.calls[-1]['media'][0])
            self.items = [self.items[-1]]
        self.assertEqual(len(self.calls), 6)
        self.assertTrue(all(a != b for a,b in zip(played, played[1:])))

    def test_favorite_pool_is_not_truncated_to_guest_result_limit(self):
        self.pool = [track(i) for i in range(1, 21)]
        self.fill.history.extend(t['uri'] for t in self.pool[:-1])
        self.fill.tick(100)
        self.assertEqual(self.calls[0]['media'], ['library://track/20'])

    def test_ai_prefetch_cancelled_by_guest_and_policy_changes(self):
        self.portal.party_policy.update(auto_method='ai', auto_prompt='rolig soul')
        self.portal.ai_available = Mock(return_value=True)
        self.portal.suggest = Mock(return_value={'id': 'job'})
        self.portal.job = Mock(return_value={'state': 'working'})
        self.items.append({'queue_item_id': 'q1', 'media_item': track(1)})
        self.fill.tick(100)
        self.assertIsNotNone(self.fill.pending)
        self.assertEqual(self.portal.suggest.call_args.args[0]['exclude'][0]['uri'], 'library://track/0')
        self.fill.guest_added()
        self.assertIsNone(self.fill.pending)
        self.portal.change_policy({'queue_id': 'group', 'continuous': False})
        self.portal.job.return_value = {'state': 'ready', 'tracks': [track(2)]}
        self.fill.tick(120)
        self.assertEqual(self.calls, [])

    def test_external_guest_add_during_lookup_prevents_stale_append(self):
        original = self.portal.ma
        def race(command, args):
            result = original(command, args)
            if command == 'music/tracks/library_items':
                self.items.append({'queue_item_id': 'external', 'media_item': track(9)})
            return result
        self.portal.ma = race
        self.fill.tick(100)
        self.assertEqual(self.calls, [])

    def test_current_track_similarity_and_failure_cooldown(self):
        self.portal.party_policy['auto_method'] = 'similar'
        original = self.portal.ma
        self.portal.ma = Mock(side_effect=original)
        self.fill.tick(100)
        self.portal.ma.assert_any_call('music/tracks/similar_tracks', {'item_id': '0', 'provider_instance_id_or_domain': 'library', 'limit': 25, 'allow_lookup': True})
        self.items = [self.items[-1]]
        self.portal.ma = Mock(side_effect=ValueError('provider unavailable'))
        self.fill.tick(120); self.fill.tick(130)
        self.assertEqual(self.portal.ma.call_count, 1)
        self.assertIn('provider unavailable', self.fill.status()['status'])

    def test_queue_placement_is_host_owned_and_persisted(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/'policy.json'
            portal = Portal({'queue_id': 'group'}, path)
            portal.ma = Mock(return_value={'tracks': [track(1)]})
            portal.change_policy({'queue_id': 'group', 'queue_option': 'next', 'continuous': True, 'auto_method': 'favorites', 'auto_count': 2})
            token = portal.join()['path'].split('=')[1]
            result = portal.guests.search(token, {'mode': 'library', 'query': 'Song'})
            portal.guests.enqueue(token, {'id': result['id'], 'indices': [0], 'option': 'replace'})
            portal.ma.assert_called_with('player_queues/play_media', {'queue_id': 'group', 'media': ['library://track/1'], 'option': 'next'})
            restarted = Portal({'queue_id': 'group'}, path)
            self.assertFalse(restarted.policy()['continuous'])
            self.assertEqual(restarted.policy()['auto_count'], 2)
            self.assertEqual(restarted.policy()['queue_option'], 'next')
            for data in [{'auto_count': 0}, {'auto_count': True}, {'queue_option': 'replace'}, {'auto_method': 'spotify'}, {'continuous': 'on'}]:
                with self.assertRaises(ValueError): portal.change_policy({'queue_id': 'group', **data})
            with self.assertRaises(ValueError): portal.change_policy({'queue_id': 'other', 'continuous': True})

    def test_ha_controls_override_saved_policy(self):
        self.portal.options.update(continuous_entity='switch.party', auto_method_entity='input_select.method', auto_count_entity='input_number.count')
        values = {'states/switch.party': 'on', 'states/input_select.method': 'favorites', 'states/input_number.count': '2.0'}
        self.portal.ha_get = lambda path: {'state': values[path]}
        self.assertEqual(self.portal.policy()['auto_count'], 2)
        self.assertTrue(self.portal.policy()['continuous'])
        values['states/switch.party'] = 'off'
        self.assertFalse(self.portal.policy()['continuous'])
        values['states/input_select.method'] = 'unavailable'
        self.assertFalse(self.portal.policy()['continuous'])


if __name__ == '__main__': unittest.main()
