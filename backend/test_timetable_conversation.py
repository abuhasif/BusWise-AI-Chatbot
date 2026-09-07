import unittest
from server import answer,connect,resolve
class TimetableConversationTest(unittest.TestCase):
    def test_exact_reported_conversation(self):
        first=answer('last bus 168',use_model=False)
        self.assertEqual(first['context']['service'],'168')
        self.assertIn('Where are you boarding service 168',first['answer'])
        second=answer('168 woodlands int',first['context'],use_model=False)
        self.assertTrue(second['cards'],second)
        self.assertTrue(all(c['Service']=='168' for c in second['cards']))
        self.assertEqual(len(second['cards']),1)
        self.assertEqual(second['cards'][0]['Last bus'],'23:30')
        self.assertNotEqual(second['cards'][0]['Towards'],'Woodlands Int')
        with connect() as c:
            rows=c.execute("SELECT s.code,s.name,r.wd_last FROM routes r JOIN stops s ON s.code=r.stop WHERE r.service='168' AND lower(s.name) LIKE '%int%'").fetchall()
            self.assertTrue(rows)
    def test_name_only_followup(self):
        r=answer('Woodlands interchange',{'intent':'times','service':'168'},use_model=False)
        self.assertTrue(r['cards'])
    def test_one_turn_named_stop(self):
        r=answer('last bus 168 at woodlands int on Sunday',use_model=False)
        self.assertTrue(r['cards']);self.assertIn('Sunday',r['answer'])
    def test_day_followup_keeps_stop(self):
        r=answer('what about Saturday?',{'intent':'times','service':'168','stop':'woodlands int'},use_model=False)
        self.assertTrue(r['cards']);self.assertEqual(r['context']['stop'],'woodlands int')
    def test_stop_code_followup(self):
        r=answer('46009',{'intent':'times','service':'168'},use_model=False)
        self.assertEqual(r['context']['intent'],'times');self.assertEqual(r['context']['stop'],'46009')
    def test_unsupported_name_does_not_guess(self):
        r=answer('168 Atlantis',{'intent':'times','service':'168'},use_model=False)
        self.assertFalse(r['cards']);self.assertIn('could not match',r['answer'])
    def test_switch_to_stop_services(self):
        r=answer('which buses serve stop 66009',{'intent':'times','service':'168'},use_model=False)
        self.assertEqual(r['context']['intent'],'stop')
if __name__=='__main__':unittest.main()
