import json,threading,unittest,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
from server import Handler

class HttpHeadersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=f'http://127.0.0.1:{cls.server.server_address[1]}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def test_responses_hide_versions_and_disable_sniffing_and_caching(self):
        with urllib.request.urlopen(self.base+'/api/map/stops') as r:
            self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
            self.assertEqual(r.headers['Cache-Control'],'no-store')
            self.assertNotIn('Python',r.headers['Server'])
    def test_oversized_and_invalid_bodies_are_rejected(self):
        for body,status in [(b'x'*9000,413),(b'not json',400),(b'[1]',400)]:
            req=urllib.request.Request(self.base+'/api/chat',data=body,headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(req)
            self.assertEqual(caught.exception.code,status)
    def test_unknown_paths_return_json_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(self.base+'/data/bus.db')
        self.assertEqual(caught.exception.code,404)
        self.assertEqual(json.loads(caught.exception.read()),{'error':'Not found'})
if __name__=='__main__':unittest.main()
