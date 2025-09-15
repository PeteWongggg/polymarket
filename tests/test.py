"""
% python test/test.py 
...
----------------------------------------------------------------------
Ran 3 tests in 0.000s

OK
"""

import unittest
from agents.polymarket.polymarket import Polymarket


class TestStringMethods(unittest.TestCase):
    def test_upper(self):
        self.assertEqual("foo".upper(), "FOO")

    def test_isupper(self):
        self.assertTrue("FOO".isupper())
        self.assertFalse("Foo".isupper())

    def test_split(self):
        s = "hello world"
        self.assertEqual(s.split(), ["hello", "world"])
        # check that s.split fails when the separator is not a string
        with self.assertRaises(TypeError):
            s.split(2)


class TestPolymarketOrderBook(unittest.TestCase):
    def test_get_order_book_compact(self):
        pm = Polymarket()
        token_id = "81104637750588840860328515305303028259865221573278091453716127842023614249200"
        ob = pm.get_order_book_compact(token_id)
        # 允许网络失败返回 None，但如果有返回则做结构断言
        if ob is not None:
            self.assertIn("bids", ob)
            self.assertIn("asks", ob)
            self.assertIn("tick_size", ob)
            self.assertIn("min_order_size", ob)
            self.assertIsInstance(ob["bids"], list)
            self.assertIsInstance(ob["asks"], list)
            # 条目应包含 price/size
            if len(ob["bids"]) > 0:
                self.assertIn("price", ob["bids"][0])
                self.assertIn("size", ob["bids"][0])
            if len(ob["asks"]) > 0:
                self.assertIn("price", ob["asks"][0])
                self.assertIn("size", ob["asks"][0])

if __name__ == "__main__":
    unittest.main()
