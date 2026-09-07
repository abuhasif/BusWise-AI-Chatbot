import unittest
from server import answer,connect,resolve,rule_intent
class RoutesTest(unittest.TestCase):
    def test_hougang_interchange_aliases(self):
        with connect() as c:
            for term in ['Hougang Int','Hougang Interchange','Hougang Ctrl Int','Hougang Central Interchange']:
                with self.subTest(term=term):
                    self.assertEqual(resolve(c,term,'alight'),['64009','64541'])
                    self.assertEqual(resolve(c,term,'board'),['64009','64541'])
    def test_interchange_to_interchange(self):
        d=answer('how to get from woodlands int to hougang int',use_model=False)
        self.assertTrue(any(card['Service']=='161' for card in d['cards']))
        self.assertTrue(all(card['Alight'].startswith('64009') for card in d['cards']))
    def test_woodlands_to_hougang(self):
        d=answer('how to get from woodlands to hougang',use_model=False)
        self.assertTrue(d['cards'])
        self.assertTrue(all('Woodlands Int' in card['Board'] for card in d['cards']))
        self.assertIn('specific stops',d['answer'])
    def test_town_matches_only_its_interchange(self):
        with connect() as c:
            self.assertEqual(resolve(c,'woodlands','board'),resolve(c,'Woodlands Int','board'))
            self.assertFalse(resolve(c,'wood','board'))
            self.assertFalse(resolve(c,'Atlantis','board'))
    def test_station_direct(self):
        d=answer('from Serangoon to Bartley',use_model=False)
        self.assertTrue(any(c['Service']=='158' for c in d['cards']))
    def test_codes_remain_strings(self):
        with connect() as c:self.assertEqual(resolve(c,'01012','board'),['01012'])
    def test_stop_prefix(self):
        with connect() as c:self.assertEqual(resolve(c,'stop 01012','board'),['01012'])
    def test_unknown_stop(self):self.assertFalse(answer('buses at 99999',use_model=False)['cards'])
    def test_stop_services(self):self.assertIn('100',answer('buses at 66009',use_model=False)['cards'][0]['Services'])
    def test_sunday_times(self):
        d=answer('last bus for service 100 at stop 66009 on Sunday',use_model=False)
        self.assertTrue(d['cards']);self.assertIn('Sunday',d['answer'])
    def test_missing_timetable_input(self):self.assertIn('Tell me',answer('last bus',use_model=False)['answer'])
    def test_reverse(self):
        d=rule_intent('opposite direction',{'intent':'route','origin':'Serangoon','destination':'Bartley'})
        self.assertEqual(d['origin'],'Bartley');self.assertEqual(d['destination'],'Serangoon')
    def test_followup_destination(self):
        d=rule_intent('What about Aljunied?',{'intent':'route','origin':'Serangoon','destination':'Bartley'})
        self.assertEqual(d['destination'],'Aljunied')
    def test_live_refused(self):self.assertIn('cannot confirm live',answer('when does the bus arrive?',use_model=False)['answer'])
    def test_free_boarding_refused(self):self.assertFalse(answer('is free boarding active?',use_model=False)['cards'])
    def test_sql_like_input(self):self.assertFalse(answer("from ' OR 1=1 -- to nowhere",use_model=False)['cards'])
    def test_direction_and_order(self):
        with connect() as c:
            rows=c.execute('SELECT seq FROM routes WHERE service=? AND direction=1 ORDER BY seq',('100',)).fetchall()
            self.assertTrue(rows)
        d=answer('from Serangoon to Bartley',use_model=False)
        self.assertTrue(all(x['Stops along route']>0 for x in d['cards']))
    def test_ambiguous_direction_flagged(self):
        with connect() as c:self.assertGreater(c.execute("SELECT count(*) FROM routes WHERE service='382' AND direction=2 AND ambiguous=1").fetchone()[0],0)
    def test_same_stop(self):self.assertIn('same location',answer('from 66009 to 66009',use_model=False)['answer'])
if __name__=='__main__':unittest.main()
