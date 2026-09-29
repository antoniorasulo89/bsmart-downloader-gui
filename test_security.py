"""Regressioni offline dell’audit, con soli dati sintetici."""
import base64
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import pymupdf as fitz
import requests
import vault
from library import Library
from platforms import hub, sanoma, mylim, zanichelli
from platforms.common import checked_zip, save_pdf, svg_pdf, safe_error
from platforms.network import Operation, Cancelled, scope, check
from storage import atomic_write


def pdf():
    with fitz.open() as doc:
        doc.new_page()
        return doc.tobytes()

class Response:
    def __init__(self, content=b'', data=None, status=200):
        self.content, self.data, self.status_code = content, data, status
        self.headers = {}
    @property
    def text(self): return self.content.decode()
    @property
    def ok(self): return self.status_code < 400
    def json(self): return self.data
    def raise_for_status(self):
        if not self.ok: raise requests.HTTPError('synthetic transport error')

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_atomic_failure_preserves_previous(self):
        f = self.root / 'vault.dat'; f.write_bytes(b'OLD')
        with patch('storage.os.replace', side_effect=OSError('synthetic')):
            with self.assertRaises(OSError): atomic_write(f, b'NEW')
        self.assertEqual(f.read_bytes(), b'OLD')
        self.assertEqual(len(list(self.root.iterdir())), 1)
    def test_dpapi_failure_preserves_previous(self):
        f = self.root / 'vault.dat'; f.write_bytes(b'OLD')
        with patch.object(vault.sys, 'platform', 'win32'), patch.object(vault, '_vault_path', return_value=str(f)), patch.object(vault, '_win_protect', side_effect=OSError('synthetic')):
            with self.assertRaises(OSError): vault._store_blob(b'NEW')
        self.assertEqual(f.read_bytes(), b'OLD')
    def test_unreadable_vault_never_saved(self):
        with patch.object(vault, '_vault_path', return_value=str(self.root/'vault.dat')), patch.object(vault, '_load_blob', side_effect=OSError('synthetic')), patch.object(vault, '_store_blob') as store:
            with self.assertRaises(OSError): vault.set_account('new', {'password':'SYNTHETIC'})
            store.assert_not_called()
    def test_keychain_updates_without_delete(self):
        with patch.object(vault.sys, 'platform', 'darwin'), patch.object(vault.shutil, 'which', return_value='security'), patch.object(vault.subprocess, 'run') as run:
            vault._store_blob(b'{}')
            args = run.call_args.args[0]
            self.assertIn('-U', args)
            self.assertNotIn('delete-generic-password', args)
            self.assertEqual(run.call_count, 1)
    def test_linux_legacy_requires_explicit_delete(self):
        f = self.root/'vault.dat'; f.write_text('{"old":{"password":"SYNTHETIC"}}')
        with patch.object(vault.sys, 'platform', 'linux'), patch.object(vault, '_vault_path', return_value=str(f)), patch.object(vault.shutil, 'which', return_value=None):
            with self.assertRaises(OSError): vault.del_creds('old')
            self.assertTrue(f.exists())
            vault.remove_legacy()
            self.assertFalse(f.exists())
    def test_pymupdf_document_can_be_saved(self):
        with fitz.open(stream=pdf(),filetype='pdf') as doc:
            self.assertTrue(Path(save_pdf(doc,self.root,'document')).is_file())
    def test_redirect_strips_cross_origin_secrets(self):
        from platforms.network import Session
        from requests.adapters import BaseAdapter
        from urllib3.response import HTTPResponse
        seen=[]
        class Adapter(BaseAdapter):
            def send(self, prepared, **kwargs):
                seen.append(dict(prepared.headers))
                response=requests.Response()
                response.request=prepared;response.url=prepared.url
                response.status_code=302 if len(seen)==1 else 200
                response.raw=HTTPResponse(body=io.BytesIO(b'ok'),preload_content=False)
                if len(seen)==1: response.headers['Location']='https://second.invalid/end'
                return response
            def close(self):pass
        with Session() as session:
            session.mount('https://',Adapter())
            response=session.get('https://first.invalid/start',headers={'Token-Session':'SECRET','auth_token':'SECRET','Cookie':'SECRET'})
            self.assertEqual(response.content,b'ok')
            self.assertEqual(len(response.history),1)
            self.assertFalse(any(k.lower() in ('token-session','auth_token','cookie') for k in seen[-1]))
    def test_transient_get_retries_but_post_does_not(self):
        from platforms.network import Session
        session=Session()
        failed=Response(status=503)
        good=Response(status=200)
        with patch('requests.Session.request',side_effect=[failed,failed,good]) as call,patch('platforms.network.time.sleep'):
            self.assertIs(session.get('https://invalid'),good)
            self.assertEqual(call.call_count,3)
        with patch('requests.Session.request',return_value=failed) as call:
            self.assertIs(session.post('https://invalid'),failed)
            self.assertEqual(call.call_count,1)
        session.close()
    def test_sensitive_transport_error(self):
        message = safe_error(requests.ConnectionError('https://invalid/?username=SECRET&password=SECRET&token=SECRET'))
        self.assertNotIn('SECRET', message)
        self.assertNotIn('invalid', message)
    def test_unlabelled_secret_is_redacted(self):
        self.assertNotIn("SYNTHETIC", safe_error(RuntimeError("Server: SYNTHETIC non valido"), ["SYNTHETIC"]))
    def test_sensitive_runtime_error(self):
        self.assertNotIn('SECRET', safe_error(RuntimeError('token=SECRET https://invalid/?password=SECRET')))
    def test_zip_traversal_and_absolute_rejected(self):
        for name in ('book/pages/../../escape', '../escape', '/escape', 'C:/escape', 'pages\\..\\escape'):
            data = io.BytesIO()
            with zipfile.ZipFile(data,'w') as z: z.writestr(name,b'bad')
            with zipfile.ZipFile(data) as z:
                with self.assertRaises(RuntimeError): checked_zip(z)
    def test_zip_symlink_rejected(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            info=zipfile.ZipInfo('link'); info.create_system=3; info.external_attr=(0o120777<<16)
            z.writestr(info,'outside')
        with zipfile.ZipFile(data) as z:
            with self.assertRaises(RuntimeError): checked_zip(z)
    def test_pdf_collision_retains_both(self):
        first=save_pdf(pdf(),self.root,'same'); second=save_pdf(pdf(),self.root,'same')
        self.assertNotEqual(first,second)
        self.assertTrue(Path(first).exists() and Path(second).exists())
    def test_failed_serialization_keeps_existing_pdf(self):
        original=save_pdf(pdf(),self.root,'same'); content=Path(original).read_bytes()
        class Broken:
            def write(self, f): f.write(b'partial'); raise OSError('synthetic')
        with self.assertRaises(OSError): save_pdf(Broken(),self.root,'same')
        self.assertEqual(Path(original).read_bytes(),content)
        self.assertEqual(len(list(self.root.glob('*.pdf'))),1)
    def test_html_rejected_and_not_indexed(self):
        f=self.root/'invalid.pdf';f.write_bytes(b'<html>login</html>')
        with self.assertRaises(RuntimeError): save_pdf(f.read_bytes(),self.root,'bad')
        self.assertFalse(Library(self.root/'index.json').add(f))
        with patch.object(mylim.requests,'get',side_effect=[Response(data={'url':'https://invalid/file'}),Response(f.read_bytes())]):
            with self.assertRaises(RuntimeError): mylim.download({'token':'synthetic','sommari':[]},'fake',str(self.root),{},lambda *a:None)
    def test_corrupt_index_preserved(self):
        f=self.root/'index.json';f.write_bytes(b'{broken')
        store=Library(f)
        self.assertTrue(store.warning)
        backups=list(self.root.glob('index.json.corrupt.*'))
        self.assertEqual(backups[0].read_bytes(),b'{broken')
        document=self.root/'book.pdf';document.write_bytes(pdf());store.add(document)
        self.assertEqual(backups[0].read_bytes(),b'{broken')
    def test_corrupt_readonly_index_preserved_without_startup_crash(self):
        index=self.root/'index.json';index.write_bytes(b'{broken')
        document=self.root/'book.pdf';document.write_bytes(pdf())
        with patch('library.atomic_write',side_effect=OSError('synthetic permission failure')):
            store=Library(index)
            self.assertTrue(store.error)
            with self.assertRaises(OSError):store.add(document)
        self.assertEqual(index.read_bytes(),b'{broken')
    def test_bad_metadata_recovers_and_instances_merge(self):
        one=self.root/'one.pdf';one.write_bytes(pdf())
        two=self.root/'two.pdf';two.write_bytes(pdf())
        f=self.root/'index.json';f.write_text(json.dumps([{'path':str(one),'title':17}]))
        a,b=Library(f),Library(f)
        self.assertEqual(a.available()[0]['title'],'one')
        a.add(two);b.add(one,'changed')
        self.assertEqual(len(Library(f).available()),2)
    def test_svg_jpg_image_survives(self):
        source=fitz.open();page=source.new_page(width=20,height=20);page.draw_rect(page.rect,color=(1,0,0),fill=(1,0,0))
        image=page.get_pixmap().tobytes('jpeg');source.close()
        data=base64.b64encode(image).decode()
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><image width="20" height="20" href="data:image/jpg;base64,{data}"/></svg>'.encode()
        with fitz.open(stream=svg_pdf(svg),filetype='pdf') as doc:
            self.assertTrue(doc[0].get_images())
            pixels=doc[0].get_pixmap()
            self.assertGreater(pixels.pixel(10,10)[0],200)
            self.assertLess(pixels.pixel(10,10)[1],60)
    def test_svg_missing_external_resource_rejected(self):
        svg=b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://invalid/image.jpg"/></svg>'
        with self.assertRaises(RuntimeError): svg_pdf(svg)
    def test_cancel_prevents_publication(self):
        event=threading.Event();event.set()
        with scope(Operation(event)):
            with self.assertRaises(Cancelled): save_pdf(pdf(),self.root,'cancelled')
        self.assertFalse(list(self.root.glob('*.pdf')))
    def test_operation_limits(self):
        operation=Operation(threading.Event());operation.deadline=0
        with self.assertRaises(RuntimeError): operation.check()
        operation=Operation(threading.Event())
        with self.assertRaises(RuntimeError): operation.consume(2*1024**3+1)
    def test_booktab_missing_unit_rejected(self):
        spine=b'<response><unit btbid="U1"/><unit btbid="U2"/></response>'
        cfg=b'<config><content>page</content></config>'
        with patch.object(zanichelli.requests,'post',return_value=Response(data={'session':'synthetic'})), patch.object(zanichelli.requests,'get',side_effect=[Response(spine),Response(cfg),Response(pdf()),Response(status=503)]):
            with self.assertRaises(RuntimeError): zanichelli._download_booktab('synthetic','synthetic',lambda *a:None)
    def test_hub_missing_chapter_rejected(self):
        database=self.root/'publication.db'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE offline_tbl (offline_path TEXT, offline_value TEXT)')
            db.execute('INSERT INTO offline_tbl VALUES (?,?)',('meyoung/publication/1',json.dumps({'indexContents':{'chapters':[{'chapterId':'c1'},{'chapterId':'c2'}]}})))
        db.close()
        package,chapter=io.BytesIO(),io.BytesIO()
        with zipfile.ZipFile(package,'w') as z: z.writestr('publication.db',database.read_bytes())
        with zipfile.ZipFile(chapter,'w') as z: z.writestr('p1.pdf',pdf())
        with patch.object(hub,'list_books',return_value=[{'id':'1','title':'synthetic'}]), patch.object(hub.requests,'get',side_effect=[Response(package.getvalue()),Response(chapter.getvalue()),Response(status=503)]):
            with self.assertRaises(RuntimeError): hub.download({'token':'synthetic','sections':{'1':'young'}},'1',str(self.root),{},lambda *a:None)
        self.assertFalse(list(self.root.glob('*.pdf')))
    def test_digibook_password_not_sent_to_bsmart(self):
        from platforms import digibook24, bsmart
        with patch.object(bsmart, 'login_with_credentials') as login:
            with self.assertRaises(RuntimeError): digibook24.login({'email':'synthetic','password':'SYNTHETIC'})
            login.assert_not_called()
            state=digibook24.login({'cookie':'SYNTHETIC'})
            self.assertEqual(state['base'],'web.digibook24.com')
            login.assert_not_called()
    def test_saved_consent_survives_navigation(self):
        import app_gui
        with patch('vault.get_creds',return_value={'email':'synthetic@example.test','password':'SYNTHETIC'}),patch('vault.set_account'),patch('vault.del_creds') as delete,patch('library.index_path',return_value=self.root/'gui.json'):
            app=app_gui.App()
            try:
                self.assertTrue(app.remember_var.get())
                app._select_platform('sanoma');app._select_platform('bsmart')
                app._save_account()
                delete.assert_not_called()
                app.remember_var.set(False);app._save_account()
                app._select_platform('sanoma');app._select_platform('bsmart')
                self.assertFalse(app.remember_var.get())
                delete.assert_called_once_with('bsmart')
            finally:app.destroy()
    def test_close_waits_for_worker_cancellation(self):
        import app_gui
        import time
        from platforms import bsmart
        started=threading.Event()
        def login(creds):
            started.set()
            while not app.cancel_event.wait(.01): check()
            check()
        with patch('vault.get_creds',return_value={}),patch('library.index_path',return_value=self.root/'gui.json'),patch.object(bsmart,'login',side_effect=login),patch.object(app_gui.messagebox,'showinfo') as popup:
            app=app_gui.App()
            app.auth_vars['email'].set('synthetic@example.test');app.auth_vars['password'].set('SYNTHETIC')
            app._load_books_thread();self.assertTrue(started.wait(1))
            app._close_requested()
            self.assertTrue(app.closing)
            deadline=time.monotonic()+3
            while app.busy and time.monotonic()<deadline:
                app.update();time.sleep(.01)
            self.assertFalse(app.busy)
            popup.assert_not_called()
            # La coda ha chiuso automaticamente la finestra.
    def test_non_operation_callback_cannot_unlock_active_worker(self):
        import app_gui
        with patch('vault.get_creds',return_value={}),patch('library.index_path',return_value=self.root/'gui.json'),patch.object(app_gui.messagebox,'showinfo'):
            app=app_gui.App()
            try:
                app._start_operation()
                app.events.put(lambda:1/0)
                app._drain_events()
                self.assertTrue(app.busy)
                app._post_result(lambda:1/0)
                app._drain_events()
                self.assertFalse(app.busy)
            finally:app.destroy()
    def test_queue_continues_after_callback_failure(self):
        import app_gui
        with patch('vault.get_creds',return_value={}),patch('library.index_path',return_value=self.root/'gui.json'),patch.object(app_gui.messagebox,'showinfo'):
            app=app_gui.App()
            try:
                result=[]
                app.events.put(lambda: 1/0)
                app.events.put(lambda: result.append(True))
                app._drain_events()
                self.assertEqual(result,[True])
                self.assertIn(app._event_timer,app.tk.call('after','info'))
            finally:app.destroy()

if __name__ == '__main__': unittest.main(verbosity=2)
