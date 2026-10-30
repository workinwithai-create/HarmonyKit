# HarmonyKit "sing this part" recording test. Usage: python3 record_test.py <url> [out.json]
# The mic is a mocked getUserMedia stream fed from a second AudioContext. What it "sings" is the app's own export of the written
# harmony lines on the real FluidR3 choir samples (no synthesized test tones): pass 1 = Harmony 1 exactly, pass 2 = the WRONG part
# (Harmony 2's line), pass 3 = Harmony 1 again, stopped half way (partial take kept). Each full pass must become a scored take.
import asyncio, base64, json, sys, os, io, zipfile
from playwright.async_api import async_playwright
URL=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else 'record.json'; F="window.__harmonykit"
MIC="""(()=>{ navigator.mediaDevices.getUserMedia=async()=>{ const c=new AudioContext({sampleRate:48000}); await c.resume(); const d=c.createMediaStreamDestination(); window.__fctx=c; window.__fdest=d; return d.stream; };
 window.__feedAt=async(bytes,delay)=>{ const c=window.__fctx; const buf=await c.decodeAudioData(bytes.buffer.slice(0)); const s=c.createBufferSource(); s.buffer=buf; s.connect(window.__fdest); s.start(c.currentTime+Math.max(0,delay)); return buf.duration; }; })();"""
async def main():
  res={}
  async with async_playwright() as p:
    br=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx=await br.new_context(viewport={'width':1360,'height':1000}); await ctx.add_init_script(MIC); pg=await ctx.new_page(); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: m.type=='error' and errs.append(m.text))
    await pg.goto(URL); await pg.evaluate("()=>{localStorage.clear(); indexedDB.deleteDatabase('harmonykit')}"); await pg.reload()
    await pg.click('#tapBtn'); await pg.wait_for_function(f"{F}.ready()",timeout=90000)
    await pg.click('[data-stack=trio]'); await pg.click('#micBtn'); await pg.wait_for_timeout(1500)
    if await pg.is_checked('#recGuide'): await pg.click('#recGuide')
    # the "singer": the app's own guide-only exports of the written lines (real choir samples)
    await pg.evaluate(f"""async()=>{{ const f={F}; window.__h1=(await f.exportWavBytes({{only:['h1'],guide:true}})).bytes; window.__h2=(await f.exportWavBytes({{only:['h2'],guide:true}})).bytes; }}""")
    L=8*4*60/92
    await pg.click('[data-recpart="0"]')
    await pg.wait_for_function("window.__schedLog.some(e=>e.role===0&&e.step===0)",timeout=10000)
    info=await pg.evaluate(f"""async()=>{{ const f={F}, e=window.__schedLog.find(e=>e.role===0&&e.step===0), L={L}; const d=e.time+f.latencyS()-f.ctx().currentTime;
      await window.__feedAt(window.__h1,d); await window.__feedAt(window.__h2,d+L); await window.__feedAt(window.__h1,d+2*L); return {{t0:e.time,delay:d,lat:f.latencyS(),heard:e.notes}}; }}""")
    await pg.wait_for_timeout(int((info['delay']+2.5*L)*1000)); await pg.click('[data-recpart="0"]'); await pg.wait_for_timeout(1500)
    tk=await pg.evaluate(f"""()=>{{const f={F}; return f.partTakes(0).map(t=>({{id:t.id,name:t.name,src:t.src,partial:t.partial,notes:t.notes.length,secs:f.voiceData[t.id]?+(f.voiceData[t.id].data.length/f.voiceData[t.id].sr).toFixed(3):null,score:f.scoreTake(t)}}))}}""")
    use=await pg.evaluate(f"()=>{F}.state.parts[0].use"); ui=await pg.evaluate("()=>[...document.querySelectorAll('.part')][0].querySelector('.ptakes').innerText")
    full=[t for t in tk if not t['partial']]; part=[t for t in tk if t['partial']]
    res['takes']=[{k:(v if k!='score' else {kk:(round(vv,3) if isinstance(vv,float) else vv) for kk,vv in (v or {}).items()}) for k,v in t.items()} for t in tk]
    res['used_take']=use; res['ui_takes_text']=ui[:600]; res['recording_guide_heard_during_rec']=[n for n in info['heard'] if n.startswith('h1:')]; res['feed']=info
    s1=full[0]['score']['score'] if full else 0; s2=full[1]['score']['score'] if len(full)>1 else 100
    res['checks']={'two_full_takes':len(full)==2,'partial_kept':len(part)==1 and part[0]['notes']>=1,'audio_length_exact':all(abs(t['secs']-round(L,3))<0.01 for t in tk),
      'right_part_scores_high':s1>=80,'wrong_part_scores_lower':s2<=s1-25,'used_is_latest_full':use==(full[-1]['id'] if full else None),'guide_muted_while_recording_with_guide_off':not res['recording_guide_heard_during_rec'],
      'per_bar_scores':bool(full) and len(full[0]['score']['bars'])==8}
    # per-take stems and persistence
    z=await pg.evaluate(f"async()=>{{const r=await {F}.exportStemsBytes(); return r.files.map(x=>x.name)}}"); res['stems']=z
    res['checks']['stems_have_h1_takes']=sum('h1' in n.lower() or 'take-h1' in n.lower() for n in z)>=1 and sum('raw-voice' in n for n in z)>=3
    await pg.reload(); await pg.click('#tapBtn'); await pg.wait_for_function(f"{F}.ready()",timeout=90000); await pg.wait_for_timeout(1000)
    res['after_reload']=await pg.evaluate(f"()=>{{const f={F}; return {{takes:f.partTakes(0).length, audio:f.partTakes(0).filter(t=>f.voiceData[t.id]).length, use:f.state.parts[0].use, score:(f.scoreTake(f.partTakes(0)[0])||{{}}).score}}}}")
    res['checks']['persisted_in_indexeddb']=res['after_reload']['takes']==len(tk) and res['after_reload']['audio']==len(tk) and res['after_reload']['score']==s1
    await pg.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(OUT)),'shot-record.png'),full_page=True)
    res['errors']=errs; res['pass']=all(res['checks'].values()) and not errs; await br.close()
  json.dump(res,open(OUT,'w'),indent=1,default=str); print(json.dumps({'pass':res['pass'],'checks':res['checks'],'scores':[(t['name'],t['score'].get('score') if t['score'] else None) for t in res['takes']]},indent=1))
asyncio.run(main())
