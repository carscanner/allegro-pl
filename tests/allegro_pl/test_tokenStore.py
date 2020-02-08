import datetime
from unittest import TestCase

from allegro_pl import TokenStore
from allegro_pl.oauth import _KEY_TIMESTAMP, _ACCESS_TOKEN, _REFRESH_TOKEN


class TestTokenStore(TestCase):
    def test_init(self):
        timestamp = datetime.datetime.utcnow()
        ts = TokenStore('a', 'b', timestamp)
        self.assertEqual('a', ts.access_token)
        self.assertEqual('b', ts.refresh_token)
        self.assertEqual(timestamp, ts._timestamp)

    def test_from_dict_ok(self):
        timestamp = datetime.datetime.utcnow()
        ts = TokenStore.from_dict({_ACCESS_TOKEN: 'a', _REFRESH_TOKEN: 'b', _KEY_TIMESTAMP: timestamp})
        self.assertEqual('a', ts.access_token)
        self.assertEqual('b', ts.refresh_token)
        self.assertEqual(timestamp, ts._timestamp)

    def test_from_dict_None(self):
        with self.assertRaises(ValueError):
            TokenStore.from_dict(None)

    def test_from_dict_empty(self):
        ts = TokenStore.from_dict({})
        self.assertIsNone(ts.access_token)
        self.assertIsNone(ts.refresh_token)
        self.assertIsNone(ts._timestamp)

    def test_from_dict_invalid(self):
        ts = TokenStore.from_dict({'invalid_key': 'value'})
        self.assertIsNone(ts.access_token)
        self.assertIsNone(ts.refresh_token)
        self.assertIsNone(ts._timestamp)

    def test_set_access_token_updates_ts(self):
        ts = TokenStore()
        ts.access_token = 'a'
        self.assertIsNotNone(ts._timestamp)

    def test_set_refresh_token_updates_ts(self):
        ts = TokenStore()
        ts.refresh_token = 'a'
        self.assertIsNotNone(ts._timestamp)

    def test_to_dict_empty(self):
        ts = TokenStore()
        self.assertDictEqual({}, ts.to_dict())

    def test_to_dict_access_tkn(self):
        ts = TokenStore()
        ts.access_token = 'a'
        dic = ts.to_dict()
        self.assertEqual('a', dic.get(_ACCESS_TOKEN))
        self.assertIn(_KEY_TIMESTAMP, dic.keys())

    def test_to_dict_refresh_tkn(self):
        ts = TokenStore()
        ts.refresh_token = 'a'
        dic = ts.to_dict()
        self.assertEqual('a', dic.get(_REFRESH_TOKEN))
        self.assertIn(_KEY_TIMESTAMP, dic.keys())
