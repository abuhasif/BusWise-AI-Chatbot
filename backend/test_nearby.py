import math,unittest
from server import nearby,distance_m,connect,search_stops
class NearbyTest(unittest.TestCase):
    def test_search_name(self):self.assertTrue(search_stops('Serangoon')['stops'])
    def test_search_code(self):self.assertEqual(search_stops('66009')['stops'][0]['code'],'66009')
    def test_search_no_match(self):self.assertEqual(search_stops('Atlantisxyz')['stops'],[])
    def test_search_no_distance(self):self.assertNotIn('distance_m',search_stops('Serangoon')['stops'][0])
    def test_search_validation(self):
        for q in [None,'','s','x'*101]:
            with self.assertRaises(ValueError):search_stops(q)
    def test_zero_distance(self):self.assertEqual(distance_m(1.3,103.8,1.3,103.8),0)
    def test_known_distance(self):self.assertAlmostEqual(distance_m(0,0,0,1),111195,delta=5)
    def test_stop_location(self):
        with connect() as c:r=c.execute("SELECT lat,lon FROM stops WHERE code='66009'").fetchone()
        result=nearby(*r)['stops'];self.assertEqual(result[0]['code'],'66009');self.assertEqual(result[0]['distance_m'],0)
        self.assertEqual(len(result),5);self.assertTrue(all(x['services'] for x in result))
        self.assertEqual([x['distance_m'] for x in result],sorted(x['distance_m'] for x in result))
    def test_outside_coverage(self):self.assertEqual(nearby(0,0)['stops'],[])
    def test_invalid(self):
        for lat,lon in [(91,0),(0,181),(math.nan,103),(True,103),('1.3',103),(None,None),(1,math.inf)]:
            with self.subTest(lat=lat,lon=lon),self.assertRaises(ValueError):nearby(lat,lon)
    def test_leading_zero(self):
        with connect() as c:r=c.execute("SELECT lat,lon FROM stops WHERE code='01012'").fetchone()
        self.assertEqual(nearby(*r)['stops'][0]['code'],'01012')
if __name__=='__main__':unittest.main()
