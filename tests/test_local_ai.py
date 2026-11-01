import unittest
from mobius.local_ai import validate, interpret
from mobius.desktop_visibility import should_show
class TestAmbient(unittest.TestCase):
    def test_rules(self):
        self.assertTrue(should_show('Progman'))
        self.assertFalse(should_show('Chrome_WidgetWin_1'))
        self.assertEqual(validate({'kind':'shell'}).kind,'error')
        self.assertEqual(validate({'kind':'apps','args':{'apps':['notepad']}}).kind,'apps')
        self.assertTrue(validate({'kind':'shutdown','args':{'seconds':600}}).dangerous)
        self.assertEqual(interpret('Mobius buka kalkulator').kind,'apps')
