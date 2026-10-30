# Records the HarmonyKit demo: real screen capture of the app + the app's own exported WAV of the same loop (lead + band + harmony stack,
# real FluidR3 choir/oohs + band samples). Captions are added by make_video.sh. No voice-over, no generated audio.
import asyncio, time, json, base64, sys, os
from playwright.async_api import async_playwright
URL=sys.argv[1] if len(sys.argv)>1 else 'https://harmonykit.vercel.app/'; D=os.path.dirname(os.path.abspath(__file__)); RAW=D+'/raw'; os.makedirs(RAW,exist_ok=True)
async def main():
  async with async_playwright() as p:
    br=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx=await br.new_context(viewport={'width':1280,'height':720},record_video_dir=RAW,record_video_size={'width':1280,'height':720}); t_page=time.monotonic(); pg=await ctx.new_page()
    await pg.goto(URL); await pg.evaluate("()=>{localStorage.clear(); indexedDB.deleteDatabase('harmonykit')}"); await pg.reload()
    await pg.click('#tapBtn'); await pg.wait_for_function("window.__harmonykit.ready()",timeout=90000)
    await pg.click('[data-stack=stack]'); await pg.wait_for_function("window.__harmonykit.ready()",timeout=90000)
    await pg.evaluate("()=>window.__harmonykit.setSetting('expLead',true)")
    # the WAV the video plays: exported by the app from exactly this state (demo lead, chords C G C G C G C C, Pop band, full stack, 92 BPM, C major)
    w=await pg.evaluate("""async()=>{const r=await window.__harmonykit.exportWavBytes({}); let s=''; for(let i=0;i<r.bytes.length;i+=32768) s+=String.fromCharCode.apply(null,r.bytes.subarray(i,i+32768)); return {name:r.name,b64:btoa(s)}}""")
    open(D+'/'+w['name'],'wb').write(base64.b64decode(w['b64']))
    await pg.evaluate("()=>document.querySelector('section.song').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(600)
    await pg.click('#play'); t_play=time.monotonic(); marks={'play':t_play-t_page}
    await pg.wait_for_timeout(3400)
    await pg.evaluate("()=>window.scrollTo({top:document.querySelector('section.harmony').offsetTop-8,behavior:'smooth'})"); marks['harmony']=time.monotonic()-t_page; await pg.wait_for_timeout(4200)
    await pg.evaluate("()=>window.scrollBy({top:330,behavior:'smooth'})"); await pg.wait_for_timeout(4200)
    await pg.evaluate("()=>{const e=[...document.querySelectorAll('.part')][0]; window.scrollTo({top:e.offsetTop+e.offsetHeight-260,behavior:'smooth'})}"); await pg.wait_for_timeout(3600)
    await pg.evaluate("()=>document.querySelector('section.export').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(900)
    async with pg.expect_download() as dl: await pg.click('#sheet')
    marks['export']=time.monotonic()-t_page; await pg.wait_for_timeout(2600)
    await pg.evaluate("()=>document.querySelector('header').scrollIntoView({block:'start'})"); await pg.wait_for_timeout(2600)
    marks['end']=time.monotonic()-t_page; await pg.click('#play'); await ctx.close(); vp=await pg.video.path(); await br.close()
    marks['video']=vp; marks['wav']=w['name']; json.dump(marks,open(D+'/marks.json','w'),indent=1); print(marks)
asyncio.run(main())
