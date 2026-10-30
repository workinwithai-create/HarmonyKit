# HarmonyKit AUDIO-ENGINE-RULES section 9 acceptance run (+ product checks). Usage: python3 s9.py <url> [out.json]
import asyncio, base64, json, sys, re, io, wave, os, zipfile, numpy as np, mido
from playwright.async_api import async_playwright
URL=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else 's9.json'; OD=os.path.join(os.path.dirname(os.path.abspath(OUT)),'out'); os.makedirs(OD,exist_ok=True)
QD=os.path.dirname(os.path.abspath(__file__)); F="window.__harmonykit"; FIX=QD+'/fixtures/ode-flute-92bpm-C-mono16.wav'
HELP="""()=>{ const f=window.__harmonykit; const b64=b=>{let s=''; for(let i=0;i<b.length;i+=32768) s+=String.fromCharCode.apply(null,b.subarray(i,i+32768)); return btoa(s);};
 window.__qa={ b64, wav: async o=>{ const r=await f.exportWavBytes(o||{}); return {name:r.name,b64:b64(r.bytes),frames:r.frames,gain:r.gain}; },
  mid: ()=>{ const r=f.exportMidBytes(); return {name:r.name,b64:b64(r.bytes)}; }, sheet: ()=>{ const r=f.exportSheetBytes(); return {name:r.name,text:new TextDecoder().decode(r.bytes)}; } }; }"""
MOCK="""(()=>{ const sent=[]; window.__midiSent=sent; const inp={id:'in1',name:'Mock Keys 49',type:'input',state:'connected',onmidimessage:null}; const out={id:'out1',name:'Mock Synth Out',type:'output',state:'connected',send:(d,t)=>sent.push({d:[...d],t})};
 const acc={inputs:new Map([['in1',inp]]),outputs:new Map([['out1',out]]),onstatechange:null}; window.__mockIn=inp; navigator.requestMIDIAccess=()=>Promise.resolve(acc); })();"""
ARGS=['--autoplay-policy=no-user-gesture-required','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+FIX]
def load(b):
  w=wave.open(io.BytesIO(b)); n=w.getnframes(); raw=np.frombuffer(w.readframes(n),dtype=np.uint8).reshape(-1,3)
  v=(raw[:,0].astype(np.int32)|(raw[:,1].astype(np.int32)<<8)|(raw[:,2].astype(np.int32)<<16)); v[v>=1<<23]-=1<<24
  return w.getframerate(),w.getsampwidth(),n,(v/8388607.0).reshape(-1,w.getnchannels()),w.getnchannels()
async def wav(pg,o=None):
  r=await pg.evaluate("o=>window.__qa.wav(o)",o or {}); return r['name'],base64.b64decode(r['b64'])
def midinfo(fn):
  mf=mido.MidiFile(fn); t0=mf.tracks[0]
  return {'type':mf.type,'tracks':[t.name for t in mf.tracks],'tempo_bpm':round(mido.tempo2bpm([e for e in t0 if e.type=='set_tempo'][0].tempo),3),'timesig':[f"{e.numerator}/{e.denominator}" for e in t0 if e.type=='time_signature'],
    'markers':[e.text for t in mf.tracks for e in t if e.type=='marker'],'length_s':round(mf.length,4),'notes_per_track':[sum(1 for e in t if e.type=='note_on' and e.velocity>0) for t in mf.tracks],
    'channels':sorted({e.channel+1 for t in mf.tracks for e in t if e.type=='note_on'})}
async def boot(pg):
  await pg.click('#tapBtn'); await pg.wait_for_function("document.getElementById('tap').classList.contains('hide')"); await pg.evaluate(HELP)
  await pg.wait_for_function(f"{F}.ready()",timeout=90000)
async def setv(pg,k,v): return await pg.evaluate(f"([k,v])=>{F}.setSetting(k,v)",[k,v])
NN="n=>['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'][n%12]+(Math.floor(n/12)-1)"
async def lines(pg): return await pg.evaluate(f"()=>{{const nn={NN}; return [0,1,2].map(s=>{F}.partLine(s).map(n=>nn(n.n)).join(' '))}}")
async def sel(pg,id,v): await pg.evaluate("([i,v])=>{const e=document.getElementById(i); e.value=v; e.dispatchEvent(new Event('change'))}",[id,str(v)])
rms=lambda a: float(np.sqrt((np.asarray(a,dtype=np.float64)**2).mean()))
async def main():
  res={}
  async with async_playwright() as p:
    br=await p.chromium.launch(args=ARGS)
    ctx=await br.new_context(viewport={'width':1360,'height':1000},accept_downloads=True); await ctx.add_init_script(MOCK); pg=await ctx.new_page(); errs=[]; reqs=[]
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: m.type=='error' and errs.append(m.text)); pg.on('request',lambda r: reqs.append(r.url))
    await pg.goto(URL); await pg.evaluate("()=>{localStorage.clear(); indexedDB.deleteDatabase('harmonykit')}"); await pg.reload(); await pg.screenshot(path=OD+'/shot-tap.png')
    await boot(pg)
    res['live_ctx']=await pg.evaluate(f"()=>({{sampleRate:{F}.ctx().sampleRate,state:{F}.ctx().state,load:document.getElementById('load').textContent}})")
    # ---- product (held ooh pads may clash with at most 2 passing lead notes on a beat; moving parts must have zero rubs): the demo lead (Ode to Joy, C major, chords C G C G C G C C) gets singable harmony parts in every stack
    H={}
    for st in ['duet','trio','country','oohs','stack']:
      await pg.click(f'[data-stack={st}]'); H[st]=await pg.evaluate(f"""()=>{{const f={F}, nn={NN}; return {{stackKey:f.stackKey(), parts:[0,1,2].map(s=>({{type:f.state.parts[s].type, line:f.partLine(s).map(n=>nn(n.n)).join(' '), stats:f.partStats(s)}})).filter(p=>p.type!=='off')}}}}""")
    await pg.click('[data-stack=trio]')
    ks=await pg.evaluate(f"()=>{F}.detectKey({F}.melody())"); sug=await pg.evaluate(f"()=>{F}.suggestChords()")
    # parallel perfect 5ths/octaves between the lead and each part, and between parts (python check on the written lines)
    par=await pg.evaluate(f"""()=>{{const f={F}, L=f.melody(), at=(ln,s)=>{{const n=ln.find(x=>s>=x.s&&s<x.s+x.d); return n?n.n:null}}; let bad=[];
      const lines=[L].concat([0,1,2].filter(s=>f.state.parts[s].type!=='off'&&f.state.parts[s].type!=='oohs').map(s=>f.partLine(s)));
      const on=[...new Set(lines.flatMap(l=>l.map(n=>n.s)))].sort((a,b)=>a-b);
      for(let i=0;i<lines.length;i++) for(let j=i+1;j<lines.length;j++) for(let k=1;k<on.length;k++){{ const a0=at(lines[i],on[k-1]),b0=at(lines[j],on[k-1]),a1=at(lines[i],on[k]),b1=at(lines[j],on[k]); if([a0,b0,a1,b1].includes(null)) continue;
        const iv0=((a0-b0)%12+12)%12, iv1=((a1-b1)%12+12)%12; if((iv0===7&&iv1===7||iv0===0&&iv1===0) && a0!==a1 && b0!==b1 && Math.sign(a1-a0)===Math.sign(b1-b0)) bad.push([i,j,on[k]]); }}
      return bad}}""")
    allp=[p for k in H for p in H[k]['parts']]
    res['harmony']={'lead':'Ode to Joy (8 bars, C major), chords C G C G C G C C','stacks':H,'key_suggestion':ks,'chord_suggestion_from_lead':sug,'parallel_5ths_8ves_trio':par,
      'pass':ks['keyRoot']==0 and ks['mode']=='major' and sug.split()[0]=='C' and sug.split()[-1]=='C' and all((p['stats']['rubs']==0 or (p['type']=='oohs' and p['stats']['rubs']<=2)) and p['stats']['leap']<=7 and p['stats']['chordTones']>=0.75 and p['stats']['notes']>0 for p in allp) and not par and all(H[k]['stackKey']==k for k in H)}
    # ---- c1 exact length, downbeat at 0, peak
    name,b=await wav(pg); open(OD+'/'+name,'wb').write(b); sr,sw,n,x,nc=load(b); m=np.abs(x).max(1); pk=np.abs(x).max(); exp=round(8*4*60/92*48000); fi=int(np.argmax(m>0.01*pk))
    _,bk=await wav(pg,{'only':['drums']}); xk1=load(bk)[3]; mk=np.abs(xk1).max(1); fk=int(np.argmax(mk>0.05*mk.max()))
    res['c1']={'file':name,'sr':sr,'bits':sw*8,'ch':nc,'frames':n,'expected':exp,'peak_dBFS':round(20*np.log10(pk),3),'first_sample_over_1pct_peak':fi,'first_transient_ms':round(fi/48,3),'drums_only_first_onset_5pct_ms':round(fk/48,3)}
    res['c1']['pass']=n==exp==1001739 and sr==48000 and sw==3 and nc==2 and res['c1']['peak_dBFS']<=-1.0 and fi/48<=1.0 and fk/48<=1.0
    other={}
    for bpm,bars in [(60,4),(137,8),(180,16)]:
      await setv(pg,'bpm',bpm); await setv(pg,'bars',bars); _,bb=await wav(pg); s_=load(bb); other[f'{bpm}bpm_{bars}bars']={'frames':s_[2],'expected':round(bars*4*60/bpm*48000),'peak_dBFS':round(20*np.log10(np.abs(s_[3]).max()),3)}
    await setv(pg,'bpm',92); await setv(pg,'bars',8)
    res['c1_other_lengths']=other; res['c1_other_pass']=all(v['frames']==v['expected'] and v['peak_dBFS']<=-1 for v in other.values())
    # ---- c2 4x loop: drift, seam, tail fold == continuous playback
    x2=load((await wav(pg))[1])[3]; t=np.tile(x,(4,1)); N=len(x); bar=48000*4*60/92; xk=np.tile(xk1[:,0],4); pkk=np.abs(xk).max(); dev=[]
    for k in range(32):
      e=int(round(k*bar)); w=np.abs(xk[max(0,e-200):e+200]); dev.append(int(np.argmax(w>0.05*pkk))+max(0,e-200)-e)
    a8=load((await wav(pg,{'only':['drums'],'gain':0.25}))[1])[3]; await setv(pg,'bars',16); a16=load((await wav(pg,{'only':['drums'],'gain':0.25}))[1])[3]; await setv(pg,'bars',8)
    pk8=np.abs(a8).max(); near=np.abs(a16[N-480:N+480]-np.vstack([a8[-480:],a8[:480]]))
    d=np.abs(np.diff(t[:,0])); typ=float(np.percentile(d,99.99)); sp=max(max(dev[i::4])-min(dev[i::4]) for i in range(4)); tr=float(np.polyfit(range(32),dev,1)[0]*32)
    res['c2']={'total_frames_4x':len(t),'expected_4x':4*exp,'drift_samples':len(t)-4*exp,'kick_downbeat_onsets_32bars_samples':sorted(set(dev)),'onset_spread_same_bar_position':sp,'onset_trend_samples_over_32_bars':round(tr,3),
      'tail_fold_vs_continuous_16bar_render_seam_maxdiff_rel':float(near.max()/pk8),'seam_abs_sample_step':[round(float(d[k*N-1]),5) for k in (1,2,3)],'sample_step_p99.99_in_file':round(typ,5)}
    res['c2']['pass']=res['c2']['drift_samples']==0 and sp<=5 and abs(tr)<1 and near.max()/pk8<0.01 and max(res['c2']['seam_abs_sample_step'])<=max(typ,1e-3)
    rd=float(np.abs(x-x2).max()); res['determinism']={'repeat_render_maxdiff':rd,'pass':rd<=10**(-120/20)}
    # ---- c6 longest held note at the slowest preset tempo: Ballad 68 BPM, the ooh pad (voice oohs, looped sustain) holds a full bar
    await pg.click('[data-stack=stack]'); await sel(pg,'recipe','ballad'); await setv(pg,'bpm',68); await pg.wait_for_function(f"{F}.ready()",timeout=90000)
    pl=await pg.evaluate(f"()=>{F}.partLine(2).map(n=>[n.n,n.s,n.d])")
    s6=load((await wav(pg,{'only':['h3']}))[1])[3].mean(1); bn=int(round(48000*4*60/68)); seg=s6[bn:2*bn]; mid=rms(seg[int(bn*.3):int(bn*.5)]); end=rms(seg[int(bn*.92):int(bn*.97)])
    res['c6']={'recipe':'ballad','bpm':68,'note_s':round(4*60/68,3),'part':'Harmony 3 · Ooh pad (voice oohs, FluidR3, looped sustain)','pad_notes_steps':pl[:3],'rms_30-50%':round(mid,4),'rms_92-97%':round(end,4),'end/mid':round(end/mid,3)}
    s6b=load((await wav(pg,{'only':['pad']}))[1])[3].mean(1); seg=s6b[bn:2*bn]; res['c6']['strings_pad_end/mid']=round(rms(seg[int(bn*.92):int(bn*.97)])/rms(seg[int(bn*.3):int(bn*.5)]),3)
    res['c6']['pass']=end/mid>0.8 and pl[1][2]>=15.5 and res['c6']['strings_pad_end/mid']>0.8; await sel(pg,'recipe','pop'); await setv(pg,'bpm',92); await pg.click('[data-stack=trio]'); await pg.wait_for_function(f"{F}.ready()",timeout=90000)
    # ---- c4 live changes while playing: heard within one bar, no restart; MIDI out mirrors the band
    await sel(pg,'midiOut','out1'); await pg.click('#play'); await pg.wait_for_timeout(2500); live={}
    acts=[('mute_drums',"()=>document.querySelector('[data-m=drums]').click()",lambda e,v:e['ver']>v and e['step']%4==0 and not any(n.startswith('drums:') for n in e['notes']),92),
          ('stack_country',"()=>document.querySelector('[data-stack=country]').click()",lambda e,v:e['stack']=='country',92),
          ('edit_next_bar_note',"()=>{const L=window.__schedLog, st=L[L.length-1].step, k=(Math.floor(st/16)+1)%8, f=window.__harmonykit; const n=f.partLine(0).find(x=>Math.floor(x.s/16)===k); document.querySelector('[data-slot=\"0\"][data-note=\"'+n.key+'\"]').dispatchEvent(new MouseEvent('click',{bubbles:true})); document.querySelector('[data-nudge=\"1\"]').click(); const m=f.partLine(0).find(x=>x.s===n.s); window.__lk={k,s:n.s,from:n.n,to:m.n,edited:m.edited}; }",lambda e,v:e['ver']>v and LK and e['step']==LK['s'] and ('h1:%d'%LK['to']) in e['notes'],92),
          ('learn_solo_h2',"()=>document.querySelector('[data-learn=\"1\"]').click()",lambda e,v:e['learn']==1 and e['step']%16==0 and any(n.startswith('h2:') and n.endswith('g') for n in e['notes']) and not any(n.startswith(('h1:','h3:')) for n in e['notes']),92),
          ('learn_off',"()=>document.querySelector('[data-learn=\"1\"]').click()",lambda e,v:e['learn']==-1 and any(n.startswith('h1:') for n in e['notes']),92),
          ('recipe_folk',"()=>{const e=document.getElementById('recipe');e.value='folk';e.dispatchEvent(new Event('change'))}",lambda e,v:e['recipe']=='folk',92),
          ('ab_A_thin',"()=>document.getElementById('abA').click()",lambda e,v:e['listen']=='A',92),
          ('ab_B_need',"()=>document.getElementById('abB').click()",lambda e,v:e['listen']=='B',92),
          ('key_D',"()=>{const e=document.getElementById('key');e.value='2';e.dispatchEvent(new Event('change'))}",lambda e,v:e['keyRoot']==2,92),
          ('bpm_120',"()=>{const e=document.getElementById('bpm');e.value=120;e.dispatchEvent(new Event('change'))}",lambda e,v:e['bpm']==120,92)]
    LK=None
    for nm,act,ok,bpm0 in acts:
      t0=await pg.evaluate(f"()=>{F}.ctx().currentTime"); v=await pg.evaluate("()=>Math.max(...window.__schedLog.map(e=>e.ver))"); await pg.evaluate(act)
      await pg.wait_for_timeout(3000); log=await pg.evaluate("()=>window.__schedLog"); LK=await pg.evaluate("()=>window.__lk||null")
      if nm.startswith('edit'): live['edit']=LK
      hit=[e for e in log if e['time']>t0 and ok(e,v)]; barS=4*60/bpm0
      live[nm]={'heard_at_s_after_change':round(hit[0]['time']-t0,3) if hit else None,'one_bar_s':round(barS,3),'pass':bool(hit) and (hit[0]['time']-t0<=barS or (nm.startswith(('edit','learn')) and hit[0]['time']-t0<=2*barS))}  # an edit on the NEXT bar is heard when that bar starts (<= 2 bars from the click)
    live['lines_after']=await lines(pg); live['still_playing_no_restart']=await pg.evaluate(f"()=>{F}.playing()"); live['ab']=await pg.evaluate("()=>window.__ab")
    res['c4']=live; res['c4']['pass']=all(v['pass'] for v in live.values() if isinstance(v,dict) and 'pass' in v) and live['still_playing_no_restart']
    res['midi_out']={'msgs_sent_while_playing':await pg.evaluate("()=>window.__midiSent.length"),'channels':sorted(await pg.evaluate("()=>[...new Set(window.__midiSent.filter(m=>(m.d[0]&0xF0)==0x90).map(m=>(m.d[0]&15)+1))]"))}
    res['midi_out']['pass']=res['midi_out']['msgs_sent_while_playing']>20 and len(res['midi_out']['channels'])>=3
    await pg.wait_for_timeout(300); res['stop']=await pg.evaluate(f"()=>{F}.measureStopSilence()")
    res['stop']['active_after']=await pg.evaluate(f"()=>{F}.active()"); res['stop']['all_notes_off_channels']=await pg.evaluate("()=>new Set(window.__midiSent.filter(m=>(m.d[0]&0xF0)==0xB0&&m.d[1]==123).map(m=>m.d[0]&15)).size")
    res['stop']['pass']=res['stop']['ms'] is not None and res['stop']['ms']<=50 and res['stop']['all_notes_off_channels']==16 and res['stop']['active_after']==0
    await pg.click('[data-m=drums]'); await sel(pg,'recipe','pop'); await setv(pg,'keyRoot',0); await setv(pg,'bpm',92); await setv(pg,'edits',[{},{},{}]); await pg.click('[data-stack=trio]'); await pg.wait_for_function(f"{F}.ready()",timeout=90000)
    # ---- c3 hidden tab 30 s while recording (MIDI keyboard armed)
    await sel(pg,'midiIn','in1'); n0t=await pg.evaluate(f"()=>{F}.state.takes.length")
    await pg.click('#rec'); await pg.wait_for_timeout(1500)
    oth=await ctx.new_page(); await oth.goto('about:blank'); await oth.bring_to_front()
    n0=await pg.evaluate("()=>{Object.defineProperty(document,'visibilityState',{value:'hidden',configurable:true});document.dispatchEvent(new Event('visibilitychange'));return window.__schedLog.length}")
    await pg.wait_for_timeout(30000); await pg.bring_to_front()
    await pg.evaluate("()=>{Object.defineProperty(document,'visibilityState',{value:'visible',configurable:true});document.dispatchEvent(new Event('visibilitychange'))}"); await pg.wait_for_timeout(1500)
    res['c3']={'hidden_s':30,'was_recording':True,'playing_on_return':await pg.evaluate(f"()=>{F}.playing()"),'recording_on_return':await pg.evaluate(f"()=>{F}.recording()"),'steps_scheduled_while_hidden_and_after':await pg.evaluate("()=>window.__schedLog.length")-n0,
      'active_voices_after':await pg.evaluate(f"()=>{F}.active()"),'takes_added_by_partial_pass':await pg.evaluate(f"()=>{F}.state.takes.length")-n0t,'status':await pg.text_content('#status')}
    res['c3']['pass']=not res['c3']['playing_on_return'] and not res['c3']['recording_on_return'] and res['c3']['steps_scheduled_while_hidden_and_after']==0 and res['c3']['active_voices_after']==0 and res['c3']['takes_added_by_partial_pass']==0; await oth.close()
    # ---- recording a melody on the (mock) MIDI keyboard: A minor-ish line, 4 bars at 120, each full pass -> a Keys take, harmonized
    await setv(pg,'bpm',120); await setv(pg,'bars',4); await sel(pg,'mode','minor'); await sel(pg,'key','9'); await setv(pg,'chords','Am Dm C E'); nt0=await pg.evaluate(f"()=>{F}.state.takes.length")
    await pg.click('#rec'); await pg.wait_for_function(f"{F}.playing()")
    await pg.evaluate("""()=>{ const I=window.__mockIn, mel=[69,72,76,72, 74,77,81,77, 72,76,79,76, 71,74,76,68]; const f=window.__harmonykit, sd=60/120/4;
      const t0=f.ctx().currentTime; let i=0; const go=()=>{ const n=mel[i%16]; I.onmidimessage({data:new Uint8Array([0x90,n,70+(i%3)*20])}); setTimeout(()=>I.onmidimessage({data:new Uint8Array([0x80,n,0])}),420); i++; }; window.__feed=setInterval(go,500); go(); }""")
    await pg.wait_for_timeout(17500); await pg.evaluate("()=>clearInterval(window.__feed)"); await pg.click('#play'); await pg.wait_for_timeout(500)
    rc=await pg.evaluate(f"""()=>{{const f={F}; return {{takes:f.state.takes.slice({nt0}).map(t=>({{name:t.name,src:t.src,notes:t.notes.length,vels:[...new Set(t.notes.map(n=>Math.round(n.v*127)))].sort((a,b)=>a-b),bars:t.bars,bpm:t.bpm}})), active:f.state.active, active_name:(f.state.takes.find(t=>t.id===f.state.active)||{{}}).name, roles:[...new Set(f.state.takes.slice({nt0}).map(t=>t.role))], sug:f.suggestChords(), h1:f.partLine(0).length, status:document.getElementById('status').textContent}}}}""")
    rc['partial_kept']=any('(partial)' in t['name'] and t['notes']>=1 for t in rc['takes']); rc['pass']=rc['partial_kept'] and len([t for t in rc['takes'] if '(partial)' not in t['name']])>=1 and all(t['src']=='keys' and t['notes']>=12 for t in rc['takes'] if '(partial)' not in t['name']) and rc['roles']==['lead'] and rc['h1']>=12 and '(partial)' not in rc['active_name']
    res['recording_midi']=rc
    # ---- recording with the mic (Chromium fake mic plays a real sampled flute recording of the melody)
    await setv(pg,'bpm',92); await setv(pg,'bars',8); await sel(pg,'key','0'); await sel(pg,'mode','major'); await setv(pg,'chords','C G C G C G C C')
    await pg.click('#micBtn'); await pg.wait_for_timeout(2500); mm=[]
    for _ in range(15): mm.append(await pg.evaluate("()=>parseFloat(document.getElementById('meterBar').style.width)||0")); await pg.wait_for_timeout(100)
    await sel(pg,'midiIn',''); nt1=await pg.evaluate(f"()=>{F}.state.takes.length"); await pg.click('#rec'); await pg.wait_for_timeout(int(8*4*60/92*1000*2+2500)); await pg.click('#play'); await pg.wait_for_timeout(800)
    vr=await pg.evaluate(f"""()=>{{const f={F}; return {{takes:f.state.takes.slice({nt1}).map(t=>({{name:t.name,src:t.src,notes:t.notes.length,secs:f.voiceData[t.id]?+(f.voiceData[t.id].data.length/f.voiceData[t.id].sr).toFixed(3):null}})), mic:document.getElementById('micState').textContent, latency_s:f.latencyS()}}}}""")
    vr['meter_max_pct']=max(mm); vr['loop_s']=round(8*4*60/92,3); vr['pass']=len([t for t in vr['takes'] if '(partial)' not in t['name']])>=1 and all(t['src']=='voice' and abs(t['secs']-vr['loop_s'])<0.01 and (t['notes']>=8 or '(partial)' in t['name']) for t in vr['takes']) and vr['meter_max_pct']>0
    res['recording_mic']=vr
    # ---- import: a real recording (sampled flute playing Ode to Joy, 92 BPM) -> transcribed -> same chords as the demo notes
    b64=base64.b64encode(open(FIX,'rb').read()).decode(); await pg.evaluate("async b=>await window.__harmonykit.importBytes(b,'ode-memo.wav','audio/wav')",b64)
    im=await pg.evaluate(f"""()=>{{const f={F}, t=f.state.takes.find(x=>x.id===f.state.active); return {{take:t.name,src:t.src,notes:t.notes.map(n=>[n.n,Math.round(n.s*4)/4,Math.round(n.d*4)/4]),sug:f.suggestChords(), h1:f.partLine(0).length, h1stats:f.partStats(0)}}}}""")
    ode=[[76,0,4],[76,4,4],[77,8,4],[79,12,4],[79,16,4],[77,20,4],[76,24,4],[74,28,4],[72,32,4],[72,36,4],[74,40,4],[76,44,4],[76,48,6],[74,54,2],[74,56,8]]
    col=lambda seq:[a for i,a in enumerate(seq) if i==0 or seq[i-1]!=a]; ode8=[n for n,_,_ in ode]+[76,76,77,79,79,77,76,74,72,72,74,76,74,72,72]
    got=set((a,b_) for a,b_,_ in im['notes']); hit=sum(1 for a,b_,_ in ode if (a,b_) in got)
    im['onsets_recovered_bars1-4']=f"{hit}/{len(ode)} (legato repeated notes on the sampled flute merge into one held note)"; im['pitch_contour_matches']=col([n[0] for n in im['notes']])==col(ode8)
    im['demo_chord_suggestion']=sug; im['pass']=im['pitch_contour_matches'] and im['src']=='audiofile' and im['h1']>=8 and im['h1stats']['rubs']==0
    res['import_audio']=im
    mm_=await pg.evaluate("()=>window.__qa.mid()"); fn=OD+'/'+mm_['name']; open(fn,'wb').write(base64.b64decode(mm_['b64']))
    await pg.evaluate("async b=>await window.__harmonykit.importBytes(b,'export.mid','audio/midi')",mm_['b64'])
    res['import_midi']=await pg.evaluate(f"()=>{{const f={F}, t=f.state.takes.find(x=>x.id===f.state.active); return {{take:t.name,src:t.src,notes:t.notes.length}}}}"); res['import_midi']['pass']=res['import_midi']['src']=='midifile' and res['import_midi']['notes']>=20
    # ---- MIDI file content
    await pg.click('[data-take="demo"]') if await pg.query_selector('[data-take="demo"]') else await setv(pg,'active','demo')
    mm_=await pg.evaluate("()=>window.__qa.mid()"); fn=OD+'/'+mm_['name']; open(fn,'wb').write(base64.b64decode(mm_['b64'])); mi=midinfo(fn); mi['file']=mm_['name']; mi['expected_s']=round(8*4*60/92,4)
    mi['pass']=mi['type']==1 and mi['tempo_bpm']==92 and mi['timesig'][:1]==['4/4'] and abs(mi['length_s']-mi['expected_s'])<0.02 and len(mi['markers'])>=8 and 10 in mi['channels'] and sum('Harmony' in t for t in mi['tracks'])>=2 and mm_['name']=='harmonykit-trio-92bpm-C.mid'
    res['midi_file']=mi; ch=await pg.evaluate("()=>window.__qa.sheet()"); open(OD+'/'+ch['name'],'w').write(ch['text']); res['harmony_sheet']={'file':ch['name'],'head':ch['text'][:600],'pass':ch['name']=='harmonykit-trio-sheet-92bpm-C.txt' and 'Bar 8' in ch['text'] and 'H1' in ch['text']}
    # ---- MIDI in: velocity, sustain, never starts the transport
    await sel(pg,'midiIn','in1')
    mi2=await pg.evaluate(f"""async()=>{{const f={F}, I=window.__mockIn, snd=d=>I.onmidimessage({{data:new Uint8Array(d)}}); window.__liveLog.length=0;
      snd([0x90,52,30]); snd([0x80,52,0]); snd([0x90,67,120]); snd([0x80,67,0]); await new Promise(r=>setTimeout(r,60)); const afterOffNoPedal=f.liveVoices();
      snd([0x90,64,100]); snd([0xB0,64,127]); snd([0x80,64,0]); await new Promise(r=>setTimeout(r,300)); const heldAfterOff=f.liveVoices(), sus=f.sustainOn(); snd([0xB0,64,0]); await new Promise(r=>setTimeout(r,100)); snd([0xFA]); snd([0xF8]);
      return {{vels:window.__liveLog.map(e=>[e.note,Math.round(e.vel*127)]), voices_after_noteoff_no_pedal:afterOffNoPedal, held_after_noteoff_with_pedal:heldAfterOff, sustain_flag:sus, after_pedal_up:f.liveVoices(), playing_after_notes_and_0xFA:f.playing(),
        inputs:[...document.getElementById('midiIn').options].map(o=>o.text), outputs:[...document.getElementById('midiOut').options].map(o=>o.text), note:document.getElementById('midiNote').textContent}}}}""")
    mi2['pass']=mi2['vels']==[[52,30],[67,120],[64,100]] and mi2['voices_after_noteoff_no_pedal']==0 and mi2['held_after_noteoff_with_pedal']==1 and mi2['sustain_flag'] and mi2['after_pedal_up']==0 and not mi2['playing_after_notes_and_0xFA']
    res['midi_in']=mi2
    await pg.evaluate("()=>document.querySelector('.kbdwrap').open=true"); await pg.mouse.click(5,5); await pg.keyboard.press('a'); await pg.keyboard.press('j'); await pg.click('.kbd .wk >> nth=2')
    res['keys']={'log':await pg.evaluate("()=>window.__liveLog.slice(-3).map(e=>[e.note,e.src])"),'playing_after':await pg.evaluate(f"()=>{F}.playing()")}
    res['keys']['pass']=len(res['keys']['log'])==3 and not res['keys']['playing_after']
    # ---- A/B matched loudness: A = lead + band, no harmonies (Thin), B = lead + band + harmony stack (Need)
    await setv(pg,'expLead',True); mk_=await pg.evaluate(f"()=>{F}.makeupAB()"); ra=rms(load((await wav(pg,{'only':['drums','bass','keys','pad','lead','voice'],'gain':0.5}))[1])[3]); rb=rms(load((await wav(pg,{'gain':0.5}))[1])[3])
    res['ab']={'A':'Thin: lead + band, harmonies muted','B':'Need: lead + band + harmony stack','makeup_gain_A':round(mk_,4),'A_rms_dB_raw':round(20*np.log10(ra),2),'B_rms_dB':round(20*np.log10(rb),2),'A_after_makeup_minus_B_dB':round(20*np.log10(ra*mk_/rb),3)}
    res['ab']['pass']=bool(abs(res['ab']['A_after_makeup_minus_B_dB'])<0.5)
    # ---- audio I/O
    res['audio_io']={'inputs':await pg.evaluate("()=>[...document.getElementById('audioIn').options].map(o=>o.text)"),'outputs':await pg.evaluate("()=>[...document.getElementById('audioOut').options].map(o=>o.text)"),
      'setSinkId_supported':await pg.evaluate("()=>typeof AudioContext.prototype.setSinkId==='function'"),'mic_state':await pg.text_content('#micState')}
    await pg.evaluate("()=>{const s=document.getElementById('audioOut'); if(s.options.length>1){ s.value=s.options[1].value; s.dispatchEvent(new Event('change')); }}"); await pg.wait_for_timeout(500)
    res['audio_io']['sink_after_select']=await pg.evaluate(f"()=>{F}.ctx().sinkId"); res['audio_io']['out_note']=await pg.text_content('#audioOutNote')
    res['audio_io']['pass']=len(res['audio_io']['inputs'])>=1 and len(res['audio_io']['outputs'])>=1
    # ---- stems ZIP
    z=await pg.evaluate(f"async()=>{{const r=await {F}.exportStemsBytes(); return {{name:r.name,b64:window.__qa.b64(r.zip)}}}}")
    zb=base64.b64decode(z['b64']); open(OD+'/'+z['name'],'wb').write(zb); zf=zipfile.ZipFile(io.BytesIO(zb)); names=zf.namelist(); fr={nn:load(zf.read(nn))[2] for nn in names if nn.endswith('.wav')}
    res['stems']={'zip':z['name'],'files':names,'wav_frames':sorted(set(fr.values())),'pass':len(set(fr.values()))==1 and list(fr.values())[0]==exp and any(nn.endswith('.mid') for nn in names) and any(nn.endswith('sheet-92bpm-C.txt') for nn in names) and any('raw-voice' in nn for nn in names) and sum(nn.startswith('harmonykit-trio-h') for nn in names)>=2}
    # ---- persistence (settings in localStorage, recorded audio in IndexedDB)
    await setv(pg,'bpm',96); l0=await lines(pg); nt=await pg.evaluate(f"()=>{F}.state.takes.length")
    before=await pg.evaluate(f"()=>JSON.stringify({F}.state)"); await pg.reload(); await pg.wait_for_timeout(1500); after=await pg.evaluate(f"()=>JSON.stringify({F}.state)")
    await boot(pg); await pg.wait_for_timeout(1500)
    res['persist']={'settings_equal_after_reload':before==after,'takes_before':nt,'takes_after':await pg.evaluate(f"()=>{F}.state.takes.length"),'voice_audio_restored':await pg.evaluate(f"()=>Object.keys({F}.voiceData).length"),'bpm_field':await pg.evaluate("()=>document.getElementById('bpm').value"),'lines_equal':(await lines(pg))==l0}
    res['persist']['pass']=res['persist']['settings_equal_after_reload'] and res['persist']['takes_after']==nt and res['persist']['voice_audio_restored']>=1 and res['persist']['bpm_field']=='96' and res['persist']['lines_equal']
    await setv(pg,'bpm',92); await setv(pg,'active','demo')
    # ---- license gate
    res['license']={'buy':await pg.text_content('#buy'),'config':await pg.evaluate(f"()=>{F}.LEMON")}
    await pg.fill('#licKey','TEST-KEY'); await pg.click('#licBtn'); await pg.wait_for_timeout(300); res['license']['activate_msg']=await pg.text_content('#licState'); res['license']['note']=await pg.text_content('#expNote')
    await setv(pg,'bars',16)
    async with pg.expect_download() as dl: await pg.click('#wav')
    d16=await dl.value; fp=OD+'/'+d16.suggested_filename; await d16.save_as(fp); res['license']['free_16bar']={'file':d16.suggested_filename,'frames':load(open(fp,'rb').read())[2]}
    async with pg.expect_download(timeout=180000) as dl: await pg.click('#stems')
    dz=await dl.value; await dz.save_as(OD+'/free-'+dz.suggested_filename); res['license']['free_stems']={'file':dz.suggested_filename,'n':len(zipfile.ZipFile(OD+'/free-'+dz.suggested_filename).namelist())}
    await pg.evaluate(f"()=>{{ {F}.LEMON.storeId=1; {F}.LEMON.productId=1; {F}.paintAll(); }}")
    await pg.click('#stems'); await pg.wait_for_timeout(200); res['license']['stems_gate']=await pg.text_content('#expMsg')
    await pg.click('#wav'); await pg.wait_for_timeout(200); res['license']['16bar_gate']=await pg.text_content('#expMsg'); await setv(pg,'bars',8)
    async with pg.expect_download() as dl: await pg.click('#wav')
    d0=await dl.value; fp=OD+'/'+d0.suggested_filename; await d0.save_as(fp); res['license']['free_download']={'file':d0.suggested_filename,'frames':load(open(fp,'rb').read())[2]}
    async with pg.expect_download() as dl: await pg.click('#mid')
    d1=await dl.value; await d1.save_as(OD+'/'+d1.suggested_filename); res['license']['free_midi']=d1.suggested_filename
    async with pg.expect_download() as dl: await pg.click('#sheet')
    d2=await dl.value; await d2.save_as(OD+'/'+d2.suggested_filename); res['license']['free_sheet']=d2.suggested_filename
    await pg.evaluate(f"()=>{{ {F}.LEMON.storeId=null; {F}.LEMON.productId=null; {F}.paintAll(); }}")
    L=res['license']; exp16=round(16*4*60/92*48000)
    L['pass']='opening soon' in L['buy'].lower() and 'opening soon' in L['activate_msg'].lower() and 'free until checkout opens' in L['note'].lower() and L['free_16bar']['frames']==exp16 and L['free_stems']['n']>=3 and 'unlock' in L['stems_gate'].lower() and 'unlock' in L['16bar_gate'].lower() and d0.suggested_filename=='harmonykit-trio-92bpm-C.wav' and L['free_download']['frames']==1001739 and d1.suggested_filename=='harmonykit-trio-92bpm-C.mid' and d2.suggested_filename=='harmonykit-trio-sheet-92bpm-C.txt'
    await pg.click('#play'); await pg.wait_for_timeout(3000); await pg.screenshot(path=OD+'/shot-desk.png',full_page=True); await pg.screenshot(path=OD+'/shot-top.png'); await pg.click('#play')
    host=URL.split('/')[2]; ext=sorted(set(u.split('/')[2] for u in reqs if host not in u and not u.startswith(('data:','blob:'))))
    res['c5']={'external_hosts':ext,'sample_urls_pinned':all(re.search(r'@[0-9a-f]{40}/|/[0-9a-f]{40}/',u) for u in reqs if 'midi-js-soundfonts' in u),'sample_requests':sum(1 for u in reqs if 'midi-js-soundfonts' in u),'bundled_kit_requests':sum(1 for u in reqs if '/samples/drums/' in u)}
    src=await pg.evaluate("()=>fetch('app.js').then(r=>r.text())"); html=await pg.evaluate("()=>fetch('index.html').then(r=>r.text())")
    exp_path=src[src.index('// ---------- export'):src.index('// ---------- Lemon')]
    res['c7']={'@main/@gh-pages':len(re.findall(r'@main|@gh-pages|/main/|/gh-pages/',src+html)),'FluidR3_pinned_sha':re.findall(r'SF_SHA = "([0-9a-f]+)"',src),'Math.random_total':src.count('Math.random'),'Math.random_export_path':exp_path.count('Math.random'),
      'setTimeout_used_for_notes':len(re.findall(r'setTimeout\([^)]*(playEvent|liveOn|scheduleStep|scheduleVoiceBar)',src)),'compressor_in_export_path':exp_path.count('DynamicsCompressor'),'MAX_SHIFT':re.findall(r'MAX_SHIFT = (\d+)',src),
      'LOOKAHEAD_MS=25':'LOOKAHEAD_MS = 25' in src,'SCHEDULE_AHEAD=0.12':'SCHEDULE_AHEAD = 0.12' in src,'auth_or_db':len(re.findall(r'supabase|firebase|firestore|signIn|/api/auth',src+html,re.I)),'ios_silent_note':'silent' in html.lower(),'stop_release_s':re.findall(r'FAST_RELEASE = ([0-9.]+)',src)}
    vm=await pg.evaluate(f"()=>({{inst:Object.entries({F}.INST).map(([k,v])=>[k,v.dir,v.label]), kit:Object.entries({F}.KIT).map(([k,v])=>[k,v.file,v.label])}})")
    bad=[r for r in vm['inst'] if not any(tok in r[2].lower() for tok in r[1].split('_') if len(tok)>2)]+[r for r in vm['kit'] if not (r[0] in ('kick','snare','rim') and r[0] in r[2].lower() or r[0] in ('ghost','hat','ohat'))]
    used=sorted({u.split('/FluidR3_GM/')[1].split('-mp3')[0] for u in reqs if '/FluidR3_GM/' in u}); res['c7']['voice_name_mismatches']=bad; res['c7']['voices']=vm; res['c7']['fluid_dirs_requested']=used
    res['c7']['requested_dirs_all_declared']=all(any(dd==r[1] for r in vm['inst']) for dd in used)
    res['c7']['pass']=res['c7']['@main/@gh-pages']==0 and len(res['c7']['FluidR3_pinned_sha'][0])==40 and res['c7']['Math.random_total']==0 and res['c7']['setTimeout_used_for_notes']==0 and res['c7']['compressor_in_export_path']==0 and res['c7']['LOOKAHEAD_MS=25'] and res['c7']['SCHEDULE_AHEAD=0.12'] and res['c7']['auth_or_db']==0 and res['c7']['ios_silent_note'] and not bad and res['c7']['requested_dirs_all_declared'] and int(res['c7']['MAX_SHIFT'][0])<=4
    res['errors']=errs; await ctx.close()
    # ---- c5 blocked sample host: names the missing instruments
    bc=await br.new_context(viewport={'width':1360,'height':1000}); bp=await bc.new_page(); berr=[]; bp.on('pageerror',lambda e:berr.append(str(e)))
    await bc.route(re.compile(r'.*(cdn\.jsdelivr\.net|raw\.githubusercontent\.com).*'),lambda r: r.abort())
    await bp.goto(URL); await bp.click('#tapBtn'); await bp.wait_for_function("!document.getElementById('load').textContent.includes('Loading')",timeout=60000); ls=await bp.text_content('#load')
    await bp.click('#play'); await bp.wait_for_timeout(2500); stt=await bp.text_content('#status')
    ex=await bp.evaluate(f"async()=>{{try{{await {F}.exportWavBytes(); return 'no error'}}catch(e){{return e.message}}}}"); await bp.screenshot(path=OD+'/shot-blocked.png')
    res['c5']['blocked_host']={'load':ls,'play_status':stt,'export_error':ex,'playing':await bp.evaluate(f"()=>{F}.playing()"),'errors':berr}
    res['c5']['pass']=res['c5']['sample_urls_pinned'] and 'Piano' in ls and 'hoir' in ls and 'issing' in ex and 'hoir' in stt and not res['c5']['blocked_host']['playing']; await bc.close()
    await br.close()
  keys=['harmony','c1','c1_other_pass','c2','determinism','c3','c4','c5','c6','c7','midi_out','stop','recording_midi','recording_mic','import_audio','import_midi','midi_file','harmony_sheet','midi_in','keys','ab','audio_io','stems','persist','license']
  res['summary']={k:(res[k]['pass'] if isinstance(res.get(k),dict) else res.get(k)) for k in keys}; res['summary']['errors']=len(res['errors'])
  json.dump(res,open(OUT,'w'),indent=1,default=str); print(json.dumps(res['summary'],indent=1,default=str))
asyncio.run(main())
