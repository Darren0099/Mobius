"""Local Ollama AI: JSON only, validated safe intents, never execute shell text."""
import os, json
from urllib import request
from .assistant_core import APP_NAMES, Intent, parse_command
MODEL=os.environ.get('MOBIUS_AI_MODEL','qwen2.5:3b')
OPERATIONS={'pdf_image','image_pdf','pdf_word','word_pdf','merge_pdf','split_pdf','compress_pdf','rotate_pdf','image_convert'}
SYSTEM="""Kamu asisten Windows bernama Mobius. Pahami bahasa Indonesia formal, gaul, typo.
Balas HANYA JSON: {"kind":"...","args":{},"reply":""}.
kind harus salah satu: apps,browser,search,music,media,focus,water,quick,convert,shutdown,cancel_shutdown,chat.
Untuk apps: args={"apps":["notepad"]}; aplikasi hanya dari: """ + ', '.join(sorted(APP_NAMES)) + """
Untuk search: args={"query":"teks pencarian"}.
Untuk convert: args={"operation":"pdf_image","filename":"nama file"}.
Untuk media: args={"action":"pause"} dan action hanya play,pause,toggle,next,previous.
Untuk focus: args={"action":"start","minutes":25}; action start,pause,reset.
Untuk water: args={"ml":250}; nilai boleh kosong bila memakai botol default.
Untuk quick: args={"page":"lyrics"}.
Untuk shutdown: args={"seconds":600}. Untuk chat umum: args={}, isi reply dengan jawaban singkat.
Tidak ada eksekusi terminal, kode, hapus file, atau skill di luar daftar.
Jangan klaim aksi sudah selesai. Jika tidak dapat bertindak, pilih chat dan jelaskan batasan.
Keluarkan JSON saja.
"""
def validate(d):
    if not isinstance(d,dict): return Intent('error','AI mengirim respons salah.')
    k,a=d.get('kind'),d.get('args',{})
    if not isinstance(a,dict):a={}
    if k=='chat':
        r=d.get('reply','')
        return Intent('chat',r[:650] if isinstance(r,str) else 'Aku belum paham.')
    if k=='apps':
        n=a.get('apps',[])
        if isinstance(n,list) and 1<=len(n)<=5 and all(isinstance(i,str) and i.lower().strip() in APP_NAMES for i in n):
            return Intent('apps','Buka aplikasi',{'apps':[i.lower().strip() for i in n]})
    if k=='media':
        action=a.get('action')
        if action in ('play','pause','toggle','next','previous'):
            return Intent('media','Media controls',{'action':action})
    if k=='focus':
        action=a.get('action')
        minutes=a.get('minutes')
        if action in ('start','pause','reset') and (minutes is None or (type(minutes)==int and 5<=minutes<=120)):
            return Intent('focus','Focus timer',{'action':action,'minutes':minutes})
    if k=='water':
        ml=a.get('ml')
        if ml is None or (type(ml)==int and 1<=ml<=5000):
            return Intent('water','Log water',{'ml':ml})
    if k=='quick' and a.get('page')=='lyrics':
        return Intent('quick','Open lyrics',{'page':'lyrics'})
    if k=='browser':return Intent('browser','Buka browser')
    if k=='music':return Intent('music','Putar musik acak')
    if k=='cancel_shutdown':return Intent('cancel_shutdown','Batalkan shutdown')
    if k=='search':
        q=a.get('query','')
        if isinstance(q,str) and 0<len(q.strip())<=180:return Intent('search','Cari di browser',{'query':q.strip()})
    if k=='convert':
        op,name=a.get('operation'),a.get('filename','')
        if op in OPERATIONS and isinstance(name,str) and len(name)<=150:
            return Intent('convert','Konversi dokumen',{'operation':op,'filename':name})
    if k=='shutdown':
        seconds=a.get('seconds')
        if type(seconds)==int and 0<=seconds<=86400:
            return Intent('shutdown',f'Matikan laptop dalam {seconds} detik?',{'seconds':seconds},True)
    return Intent('error','Perintah tidak tersedia atau tidak aman.')
def interpret(phrase):
    parsed=parse_command(phrase)
    if parsed.kind not in ('help','error'):return parsed
    data=json.dumps({'model':MODEL,'prompt':SYSTEM+'\nPermintaan: '+phrase[:550]+'\nJSON:',
        'format':'json','stream':False,'options':{'temperature':0.1,'num_predict':220}}).encode()
    try:
        req=request.Request('http://127.0.0.1:11434/api/generate',data=data,headers={'Content-Type':'application/json'})
        with request.urlopen(req,timeout=28) as resp:
            response=json.loads(resp.read(65536).decode())
        return validate(json.loads(response['response']))
    except Exception:
        return parsed if parsed.kind=='error' else Intent('help','Untuk memahami ucapan bebas, pasang Ollama dan jalankan: ollama pull '+MODEL)
