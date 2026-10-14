import unittest,threading,urllib.request,json
from http.server import ThreadingHTTPServer
from app import Handler

class ServerTest(unittest.TestCase):
    def test_local_health_without_proxy(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url=f'http://127.0.0.1:{server.server_port}'
            with opener.open(url+'/',timeout=5) as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'Video2Blockout',response.read())
            with opener.open(url+'/video-loader.js',timeout=5) as response:
                self.assertIn(b'loadVideo',response.read())
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
