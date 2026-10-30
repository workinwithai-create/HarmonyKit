# HarmonyKit export acceptance on WebKit (iPhone 13 emulation) + Chromium. Usage: python3 export_test.py <url> [out.json]
# WAV / MIDI / harmony sheet / stems ZIP via the real buttons (downloads), exact lengths, 92 BPM 8 bars = 1,001,739 frames,
# a voice-memo import (WAV) exported with the raw voice, gate behaviour when configured, iOS share-sheet path (navigator.share stub).
import asyncio, json, sys, os, io, wave, zipfile, numpy as np, mido
from playwright.async_api import async_playwright
URL=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else 'export.json'; OD=os.path.join(os.path.dirname(os.path.abspath(OUT)),'out-export'); os.makedirs(OD,exist_ok=True)
QD=os.path.dirname(os.path.abspath(__file__)); F="window.__harmonykit"
def frames(b): w=wave.open(io.BytesIO(b)); return w.getnframes(), w.getframerate(), w.getsampwidth(), w.getnchannels()
def rms(b):
  w=wave.open(io.BytesIO(b)); raw=np.frombuffer(w.readframes(w.getnframes()),np.uint8).reshape(-1,3); v=(raw[:,0].astype(np.int32)|(raw[:,1].astype(np.int32)<<8)|(raw[:,2].astype(np.int32)<<16)); v[v>=1<<23]-=1<<24; return float(np.sqrt(np.mean((v/8388607.)**2)))
async def dl(pg,sel,timeout=240000):
  await pg.evaluate("()=>document.activeElement&&document.activeElement.blur()"); await pg.locator(sel).scroll_into_view_if_needed()
  async with pg.expect_download(timeout=timeout) as d: await pg.click(sel)
  d=await d.value; fp=OD+'/'+pg.__tag+'-'+d.suggested_filename; await d.save_as(fp); return d.suggested_filename, open(fp,'rb').read()
async def run(p, tag, R):
  ok=lambda k,c,**d: R.__setitem__(tag+':'+k,dict(d,**{'pass':bool(c)}))
  if tag=='webkit-iphone': br=await p.webkit.launch(); ctx=await br.new_context(**p.devices['iPhone 13'],accept_downloads=True)
  else: br=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required']); ctx=await br.new_context(viewport={'width':1360,'height':1000},accept_downloads=True)
  pg=await ctx.new_page(); pg.__tag=tag; errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto(URL); await pg.evaluate("()=>{localStorage.clear(); indexedDB.deleteDatabase('harmonykit')}"); await pg.reload(); errs.clear()
  await pg.click('#tapBtn'); await pg.wait_for_function(f"{F}.ready()",timeout=120000)
  st=await pg.evaluate(f"()=>({{bars:{F}.state.bars,bpm:{F}.state.bpm,ios:!document.getElementById('ios').hidden,note:document.getElementById('expNote').textContent,wav:document.getElementById('wav').textContent,gated:{F}.gated()}})")
  ok('free_while_checkout_unconfigured',not st['gated'] and 'free until checkout opens' in st['note'].lower() and 'unlock' not in st['wav'],**st)
  n,b=await dl(pg,'#wav'); f=frames(b); ok('wav_92bpm_8bar',n=='harmonykit-trio-92bpm-C.wav' and f[0]==1001739 and f[1:]==(48000,3,2) and rms(b)>1e-3,file=n,frames=f[0],fmt=f[1:])
  n,b=await dl(pg,'#mid'); m=mido.MidiFile(file=io.BytesIO(b)); tpb=m.ticks_per_beat; L=max(sum(x.time for x in t) for t in m.tracks)
  ok('midi',n=='harmonykit-trio-92bpm-C.mid' and L==8*4*tpb and sum('Harmony' in t.name for t in m.tracks)>=2,file=n,ticks=L,expected=8*4*tpb,tracks=[t.name for t in m.tracks])
  n,b=await dl(pg,'#sheet'); t=b.decode(); ok('harmony_sheet',n=='harmonykit-trio-sheet-92bpm-C.txt' and 'Bar 8' in t and 'H1 3rd up' in t,file=n,head=t[:300])
  n,b=await dl(pg,'#stems'); z=zipfile.ZipFile(io.BytesIO(b)); names=z.namelist(); wl=[frames(z.read(x))[0] for x in names if x.endswith('.wav')]
  ok('stems_zip',len(wl)>=5 and all(x==1001739 for x in wl) and any(x.endswith('.mid') for x in names) and any(x.endswith('.txt') for x in names) and z.testzip() is None,file=n,files=names)
  await pg.evaluate(f"()=>{F}.setSetting('bars',16)"); n,b=await dl(pg,'#wav'); ok('wav_16bar_free',frames(b)[0]==round(16*4*60/92*48000),file=n,frames=frames(b)[0])
  # voice memo import through the real file input -> transcribed melody + raw voice stem
  await pg.evaluate(f"()=>{F}.setSetting('bars',8)"); nt0=await pg.evaluate(f"()=>{F}.state.takes.length")
  await pg.set_input_files('#impFile',QD+'/fixtures/ode-flute-92bpm-C-mono16.wav'); await pg.wait_for_function(f"{F}.state.takes.length>{nt0}",timeout=60000); await pg.wait_for_timeout(300)
  ch=await pg.evaluate(f"()=>[{F}.partLine(0).length,{F}.partStats(0).rubs]")
  await pg.select_option('#melSrc','voice'); n,b=await dl(pg,'#wav'); n2,b2=await dl(pg,'#stems'); z=zipfile.ZipFile(io.BytesIO(b2)); vn=[x for x in z.namelist() if 'raw-voice' in x]
  ok('voice_memo_import_export',frames(b)[0]==1001739 and rms(b)>1e-3 and len(vn)==1 and frames(z.read(vn[0]))[0]==1001739 and rms(z.read(vn[0]))>1e-3 and ch[0]>=8 and ch[1]==0,h1_notes_rubs=ch,wav=n,voice_stems=vn)
  await pg.select_option('#melSrc','inst')
  # store configured (in memory only): 16 bars + stems lock, 8-bar WAV still free
  await pg.evaluate(f"()=>{{{F}.LEMON.storeId=1;{F}.LEMON.productId=1;{F}.paintAll()}}"); await pg.click('#stems'); await pg.wait_for_timeout(300); g=await pg.text_content('#expMsg')
  n,b=await dl(pg,'#wav'); ok('gate_when_configured','unlock' in g.lower() and frames(b)[0]==1001739,msg=g[:160],free_file=n)
  await pg.evaluate(f"()=>{{{F}.LEMON.storeId=null;{F}.LEMON.productId=null;{F}.paintAll()}}")
  if tag=='webkit-iphone':
    ok('ios_note_shown',st['ios'])
    await pg.evaluate("()=>{window.__shared=[]; navigator.canShare=d=>!!(d&&d.files&&d.files.length); navigator.share=async d=>{window.__shared.push(d.files.map(f=>({name:f.name,type:f.type,size:f.size})))}}")
    await pg.click('#mid'); await pg.wait_for_timeout(800); sh=await pg.evaluate("()=>window.__shared"); msg=await pg.text_content('#expMsg')
    await pg.click('#wav'); await pg.wait_for_timeout(3000); sh2=await pg.evaluate("()=>window.__shared")
    await pg.evaluate("()=>{navigator.share=async()=>{throw new DOMException('no gesture','NotAllowedError')}}"); await pg.click('#mid'); await pg.wait_for_timeout(500); m2=await pg.text_content('#expMsg'); btn=await pg.is_visible('#saveBtn')
    ok('ios_share_sheet',len(sh)==1 and sh[0][0]['name'].endswith('.mid') and sh[0][0]['size']>0 and len(sh2)==2 and sh2[1][0]['name'].endswith('.wav') and sh2[1][0]['size']==6010478 and 'shared' in msg.lower() and btn and 'tap' in m2.lower(),shared=sh2,msg=msg,no_gesture_msg=m2,save_button=btn)
    await pg.locator('section.export').screenshot(path=OD+'/export-iphone.png'); await pg.screenshot(path=OD+'/iphone-top.png')
  ok('no_page_errors',not errs,errors=errs[:5]); await br.close()
async def main():
  R={}
  async with async_playwright() as p:
    for tag in ['webkit-iphone','chromium']:
      try: await run(p,tag,R)
      except Exception as e: R[tag+':crash']={'pass':False,'error':repr(e)[:600]}
  json.dump(R,open(OUT,'w'),indent=1); bad=[k for k,v in R.items() if not v['pass']]
  for k,v in R.items(): print(('PASS ' if v['pass'] else 'FAIL ')+k, json.dumps({a:b for a,b in v.items() if a!='pass'})[:300])
  print('ALL PASS' if not bad else 'FAILED: '+', '.join(bad)); sys.exit(1 if bad else 0)
asyncio.run(main())
