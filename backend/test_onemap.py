import unittest,json
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
import onemap
from server import map_journey,map_stops

class OneMapTest(unittest.TestCase):
    def test_woodlands_pasir_ris_transfer(self):
        with patch('onemap.token',return_value=''):
            result=map_journey('woodlands','pasir ris')
        self.assertTrue(result['routes'])
        for route in result['routes']:
            self.assertEqual(len(route['legs']),2)
            self.assertEqual(route['legs'][0]['to'],route['legs'][1]['from'])
            self.assertNotEqual(route['legs'][0]['service'],route['legs'][1]['service'])
        self.assertIn('connection times are not checked',result['notice'])
    def test_bus_only_filter(self):
        def leg(mode):return {'mode':mode,'route':'161','from':{'name':'A'},'to':{'name':'B'}}
        data={'plan':{'itineraries':[{'duration':600,'legs':[leg(m) for m in modes]} for modes in [('WALK','BUS'),('BUS','SUBWAY'),('BUS','FERRY'),('WALK',),('BUS','UNKNOWN'),()]]}}
        routes=onemap.itineraries(data)
        self.assertEqual(len(routes),1)
        self.assertEqual(routes[0]['minutes'],10)
    def test_geometry(self):
        self.assertEqual(onemap.decode('_p~iF~ps|U_ulLnnqC_mqNvxq`@'),[[38.5,-120.2],[40.7,-120.95],[43.252,-126.453]])
        with self.assertRaises(ValueError):onemap.decode('_')
    def test_invalid_coordinates(self):
        for point in [[True,103.8],[float('nan'),103.8],[52,1],None]:
            with self.subTest(point=point),self.assertRaises(ValueError):onemap.coordinates(point)
    def test_request_is_bus_only(self):
        with patch('onemap.request',return_value={'plan':{'itineraries':[]}}) as request:
            self.assertEqual(onemap.route([1.3,103.8],[1.4,103.9]),[])
            params=request.call_args.args[1]
            self.assertEqual(params['mode'],'bus')
            self.assertEqual(params['routeType'],'pt')
            self.assertEqual(params['numItineraries'],3)
    def test_fallback_is_labelled(self):
        with patch('onemap.token',return_value=''):
            result=map_journey('woodlands int','hougang int')
        self.assertEqual(result['source'],'January 2026 database')
        self.assertIn('not road',result['notice'])
        self.assertTrue(result['routes'])
        self.assertGreater(len(result['routes'][0]['legs'][0]['points']),2)
    def test_upstream_success_does_not_mix_snapshot(self):
        with patch('onemap.route',return_value=[]):result=map_journey('woodlands int','hougang int')
        self.assertEqual(result['source'],'OneMap')
        self.assertEqual(result['routes'],[])
    def test_stops_have_coordinates(self):
        stops=map_stops()['stops']
        self.assertTrue(any(s['code']=='46009' for s in stops))
        self.assertTrue(all(isinstance(s['lat'],float) for s in stops))
    def test_token_never_in_url(self):
        with patch('onemap.token',return_value='private-test-token'),patch('urllib.request.urlopen') as opened:
            opened.return_value.__enter__.return_value.read.return_value=b'{}'
            onemap.request('public/routingsvc/route',{'mode':'bus'})
            req=opened.call_args.args[0]
            self.assertNotIn('private-test-token',req.full_url)
            self.assertEqual(req.get_header('Authorization'),'private-test-token')

if __name__=='__main__':unittest.main()
