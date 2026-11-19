"""Local synthetic recipient. Receives payloads; does not calculate or approve reports."""
import argparse,hashlib,json,pathlib,sqlite3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=0);p.add_argument('--state',required=True);p.add_argument('--drop-first-response',action='store_true');a=p.parse_args()
    state=pathlib.Path(a.state);state.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(state);c.execute('create table if not exists receipts(id text primary key,enterprise text,digest text,body text)');c.commit();c.close()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def answer(self,status,obj):
            raw=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            rid=self.path.removeprefix('/deliveries/');c=sqlite3.connect(state);row=c.execute('select id,enterprise,digest from receipts where id=?',(rid,)).fetchone();c.close();self.answer(200 if row else 404,dict(zip(['id','enterprise','content_sha256'],row)) if row else {'error':'not_received'})
        def do_POST(self):
            if self.path!='/deliveries':self.answer(404,{'error':'path'});return
            try:
                d=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));raw=d['body'].encode();assert hashlib.sha256(raw).hexdigest()==d['content_sha256']
                c=sqlite3.connect(state);c.execute('begin immediate');old=c.execute('select enterprise,digest from receipts where id=?',(d['id'],)).fetchone()
                if old and tuple(old)!=(d['enterprise'],d['content_sha256']):c.rollback();c.close();self.answer(409,{'error':'id_content_conflict'});return
                fresh=not old
                if fresh:c.execute('insert into receipts values(?,?,?,?)',(d['id'],d['enterprise'],d['content_sha256'],d['body']))
                c.commit();c.close()
                if fresh and a.drop_first_response:self.close_connection=True;return
                self.answer(200,{'id':d['id'],'enterprise':d['enterprise'],'content_sha256':d['content_sha256'],'accepted':True})
            except (ValueError,KeyError,AssertionError):self.answer(400,{'error':'invalid_payload'})
    s=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);print(json.dumps({'port':s.server_port}),flush=True);s.serve_forever()

if __name__=='__main__':main()
