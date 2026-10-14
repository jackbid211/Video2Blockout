"""Local-only server. Browser samples videos; model processing runs in a worker."""
import argparse
import sys
import os
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime-packages'))
os.environ.setdefault('HF_HOME',str(Path(__file__).resolve().parent/'models'/'huggingface'))
from urllib.parse import urlparse
from core import process, detect, decode_frames, blender_script, validate_request

ROOT=Path(__file__).resolve().parent
JOBS={}
LOCK=threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self,data,status=200,kind='application/json'):
        body=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
        self.send_response(status)
        self.send_header('Content-Type',kind+'; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(body)

    def local(self):
        expected=f'127.0.0.1:{self.server.server_port}'
        host=self.headers.get('Host','')
        if host not in (expected,f'localhost:{self.server.server_port}'):
            self.reply({'error':'Only localhost requests allowed'},403); return False
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://'+expected,f'http://localhost:{self.server.server_port}'):
            self.reply({'error':'Cross-origin requests denied'},403); return False
        return True

    def do_GET(self):
        if not self.local(): return
        path=urlparse(self.path).path
        if path in ('/','/index.html'):
            return self.reply((ROOT/'index.html').read_bytes(),kind='text/html')
        if path=='/video-loader.js':
            return self.reply((ROOT/'video-loader.js').read_bytes(),kind='application/javascript')
        if path=='/demo':
            return self.reply(json.loads((ROOT/'examples/demo.json').read_text(encoding='utf-8')))
        if path.startswith('/job/'):
            job=JOBS.get(path.split('/')[-1])
            return self.reply(job if job else {'error':'Job not found'},200 if job else 404)
        if path.startswith('/artifact/'):
            parts=path.split('/')
            if len(parts)!=4 or parts[2] not in JOBS or parts[3]!='depth-and-masks.npz':
                return self.reply({'error':'Not found'},404)
            file=ROOT/'runs'/parts[2]/parts[3]
            if file.exists(): return self.reply(file.read_bytes(),kind='application/octet-stream')
        self.reply({'error':'Not found'},404)

    def do_POST(self):
        if not self.local(): return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=40*1024*1024: raise ValueError('请求上限 40MB')
            data=json.loads(self.rfile.read(size))
            if self.path=='/export':
                if not isinstance(data,dict): raise ValueError('无效项目')
                script=blender_script(data['project'],data['selected'])
                return self.reply({'script':script})
            if self.path not in ('/process','/detect'): return self.reply({'error':'Not found'},404)
            operation=detect if self.path=='/detect' else process
            if operation is detect: decode_frames([data['frame']])
            else: validate_request(data)
            with LOCK:
                if any(j['status']=='running' for j in JOBS.values()):
                    return self.reply({'error':'已有任务正在运行'},409)
                identifier=uuid.uuid4().hex
                JOBS[identifier]={'status':'running','message':'准备处理','progress':0}
            directory=ROOT/'runs'/identifier; directory.mkdir(parents=True)
            def worker():
                def progress(message,value):
                    JOBS[identifier].update(message=message,progress=value)
                try:
                    result=operation(data,directory,progress)
                    result['job_id']=identifier
                    JOBS[identifier].update(status='done',result=result)
                except ImportError:
                    JOBS[identifier].update(status='error',message='缺少依赖：自动识别安装 requirements-detect.txt；深度处理安装 requirements-model.txt。')
                except Exception as exc:
                    JOBS[identifier].update(status='error',message=str(exc))
            threading.Thread(target=worker,daemon=True).start()
            self.reply({'id':identifier})
        except (ValueError,KeyError,TypeError) as exc:
            self.reply({'error':str(exc)},400)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--open-browser',action='store_true')
    parser.add_argument('--ready-file')
    args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    port=server.server_port
    print(f'Video2Blockout: http://127.0.0.1:{port}',flush=True)
    if args.ready_file:
        Path(args.ready_file).write_text(json.dumps({'url':f'http://127.0.0.1:{port}/','pid':os.getpid()}),encoding='utf-8')
    if args.open_browser:
        def open_when_ready():
            import time, urllib.request, webbrowser
            url=f'http://127.0.0.1:{port}/'
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for attempt in range(20):
                try:
                    with opener.open(url,timeout=1) as response:
                        if response.status==200:
                            webbrowser.open(url); return
                except Exception:
                    time.sleep(.5)
            print('Browser was not opened: local server health check failed. Review this window.',flush=True)
        threading.Thread(target=open_when_ready,daemon=True).start()
    server.serve_forever()
