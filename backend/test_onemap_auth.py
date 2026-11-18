import base64,json,os,time,unittest,urllib.error
from unittest.mock import patch,MagicMock
import onemap

def jwt(exp):
    part=base64.urlsafe_b64encode(json.dumps({'exp':exp}).encode()).decode().rstrip('=')
    return f'h.{part}.s'
def response(payload):
    r=MagicMock();r.__enter__.return_value.read.return_value=json.dumps(payload).encode();return r
def http_error(code):return urllib.error.HTTPError('https://www.onemap.gov.sg/api/x',code,'denied',{},None)
CREDS={'ONEMAP_EMAIL':'rider@example.com','ONEMAP_PASSWORD':'p@ss word!'}

class OneMapAuthTest(unittest.TestCase):
    def setUp(self):onemap._cache.update(token='',expires=0.0)
    def test_signs_in_once_and_reuses_the_token(self):
        fresh=jwt(time.time()+3*86400)
        with patch.dict(os.environ,CREDS),patch('urllib.request.urlopen',return_value=response({'access_token':fresh,'expiry_timestamp':str(int(time.time()+3*86400))})) as opened:
            self.assertEqual(onemap.token(),fresh);self.assertEqual(onemap.token(),fresh)
        self.assertEqual(opened.call_count,1)
        req=opened.call_args.args[0]
        self.assertEqual(req.get_method(),'POST');self.assertEqual(req.full_url,onemap.AUTH_URL)
        self.assertEqual(json.loads(req.data),{'email':'rider@example.com','password':'p@ss word!'})
        self.assertNotIn('p%40ss',req.full_url)
    def test_renews_before_expiry(self):
        onemap._cache.update(token='old',expires=time.time()+60)
        with patch.dict(os.environ,CREDS),patch('urllib.request.urlopen',return_value=response({'access_token':'new'})):
            self.assertEqual(onemap.token(),'new')
    def test_rejected_token_is_renewed_and_request_retried_once(self):
        onemap._cache.update(token='stale',expires=time.time()+86400)
        calls=[http_error(401),response({'access_token':'renewed'}),response({'plan':{}})]
        with patch.dict(os.environ,CREDS),patch('urllib.request.urlopen',side_effect=calls) as opened:
            self.assertEqual(onemap.request('public/routingsvc/route',{}),{'plan':{}})
        self.assertEqual(opened.call_args.args[0].get_header('Authorization'),'renewed')
    def test_bad_credentials_give_a_safe_message(self):
        with patch.dict(os.environ,CREDS),patch('urllib.request.urlopen',side_effect=http_error(401)):
            with self.assertRaises(onemap.Unavailable) as caught:onemap.token()
        self.assertIn('ONEMAP_EMAIL',str(caught.exception))
        self.assertNotIn('p@ss',str(caught.exception))
    def test_expired_static_token_is_reported_with_its_date(self):
        env={'ONEMAP_TOKEN':jwt(1788954594),'ONEMAP_EMAIL':'','ONEMAP_PASSWORD':''}
        with patch.dict(os.environ,env),patch('urllib.request.urlopen') as opened:
            with self.assertRaises(onemap.Unavailable) as caught:onemap.token()
        self.assertIn('expired on 9 September 2026',str(caught.exception))
        opened.assert_not_called()
    def test_static_token_still_works_without_credentials(self):
        key=jwt(time.time()+3600)
        with patch.dict(os.environ,{'ONEMAP_TOKEN':key,'ONEMAP_EMAIL':'','ONEMAP_PASSWORD':''}):
            self.assertEqual(onemap.token(),key)
if __name__=='__main__':unittest.main()
