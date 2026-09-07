import unittest
from unittest.mock import patch
from server import answer,map_journey,rule_intent
import onemap

class PreferencesTest(unittest.TestCase):
 def test_future_departure(self):
  p=rule_intent('From Woodlands to Hougang tomorrow at 8am',{})
  self.assertEqual(p['destination'],'Hougang');self.assertIn('T08:00:00',p['departure'])
 def test_preference_followup(self):
  p=rule_intent('Less walking please',{'intent':'route','origin':'Woodlands','destination':'Hougang','direct_only':'true'})
  self.assertEqual(p['less_walking'],'true');self.assertEqual(p['direct_only'],'true')
 def test_direct_fallback(self):
  with patch('onemap.token',return_value=''):
   r=map_journey('Woodlands','Pasir Ris',{'direct_only':'true'})
  self.assertFalse(r['routes'])
 def test_options_reach_onemap_and_filter(self):
  def leg(mode,distance=0):return {'mode':mode,'distance':distance}
  data={'plan':{'itineraries':[{'legs':[leg('WALK',d)]+[leg('BUS')]*b} for d,b in [(400,1),(100,2),(200,1)]]}}
  with patch('onemap.request',return_value=data) as call:
   r=onemap.route([1.3,103.8],[1.4,103.9],{'direct_only':'true','less_walking':'true','departure':'2026-09-07T08:00:00+08:00'})
  self.assertEqual([x['walk_m'] for x in r],[200,400])
  self.assertEqual(call.call_args.args[1]['time'],'08:00:00')
  self.assertEqual(call.call_args.args[1]['date'],'09-07-2026')
  self.assertEqual(call.call_args.args[1]['maxWalkDistance'],500)
 def test_same_location(self):
  with patch('onemap.route') as route:r=map_journey('Woodlands Int','Woodlands Int')
  route.assert_not_called();self.assertIn('same starting point',r['notice'])
 def test_ambiguous_place(self):
  with patch('onemap.token',return_value='test'),patch('onemap.request',return_value={'results':[{'SEARCHVAL':'ATLANTIS @ 531'}]}):
   with self.assertRaisesRegex(ValueError,'Possible matches'):map_journey('Woodlands','Atlantis')
 def test_nearby_guidance(self):
  r=answer('Where is the nearest stop?',use_model=False)
  self.assertIn('Use my location',r['answer'])
 def test_preferences_survive_answer_context(self):
  r=answer('What about Pasir Ris?',{'intent':'route','origin':'Woodlands','destination':'Hougang','direct_only':'true'},use_model=False)
  self.assertEqual(r['context']['direct_only'],'true')
