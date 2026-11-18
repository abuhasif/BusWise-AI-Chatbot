import os,unittest
os.environ['BUSWISE_MOBILE_TOKEN']='a'*32
from server import request_allowed

class AccessControlTest(unittest.TestCase):
    def test_loopback_is_allowed_without_a_token(self):
        self.assertTrue(request_allowed('127.0.0.1',''))
        self.assertTrue(request_allowed('::1',''))
    def test_remote_client_cannot_spoof_local_access(self):
        self.assertFalse(request_allowed('192.168.1.50',''))
        self.assertFalse(request_allowed('192.168.1.50','wrong-token'))
    def test_paired_remote_client_is_allowed(self):
        self.assertTrue(request_allowed('192.168.1.50','a'*32))
    def test_invalid_client_address_is_denied(self):
        self.assertFalse(request_allowed('not-an-ip','a'*32))
if __name__=='__main__':unittest.main()