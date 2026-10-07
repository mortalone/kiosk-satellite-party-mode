const {chromium}=require('playwright');
const {spawn}=require('child_process');
const assert=require('assert');
(async()=>{
 const server=spawn('python3',['party_guest/tests/web_fixture.py'],{stdio:'inherit'});
 let browser;
 try{
  for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:18102/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));if(i===49)throw Error('Fixture failed to start');}
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  // Simulate an old guest session after addon restart; the plain URL must recover.
  await page.addInitScript(()=>sessionStorage.setItem('party-guest-token','expired-fixture-token'));
  await page.goto('http://127.0.0.1:18102/guest/');
  await page.locator('.queue-row .row-similar').first().waitFor({state:'visible'});
  assert.equal(await page.locator('[data-mode=ai]:visible').count(),0);
  assert.equal(await page.locator('.queue-row').count(),2);
  // A long queue must grow the page rather than create another scroll surface.
  assert(await page.evaluate(()=>{
   const q=document.getElementById('queue');
   for(let i=0;i<12;i++)q.append(q.firstElementChild.cloneNode(true));
   const style=getComputedStyle(q);
   return style.maxHeight==='none' && style.overflowY==='visible' && q.clientHeight===q.scrollHeight;
  }));
  await page.locator('.queue-row').last().scrollIntoViewIfNeeded();
  assert(await page.evaluate(()=>window.scrollY>0));
  await page.reload();await page.locator('.queue-row .row-similar').first().waitFor();
  assert.equal(await page.locator('.queue-row.current').count(),1);
  assert((await page.locator('#help').textContent()).includes('bruger ikke AI'));
  assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).colorScheme),'light');
  assert(!(await page.locator('body').innerText()).includes('Sonic Similarity'));
  for(const mode of ['library','similar']){
   if(mode==='similar')await new Promise(r=>setTimeout(r,2100));
   await page.locator('[data-mode='+mode+']').click();await page.locator('#query').fill('Jazz');
   await page.locator('#search').click();await page.locator('.track').first().waitFor();
  }
  await page.locator('#add').click();await page.getByText('2 numre tilføjet til køen',{exact:true}).waitFor();
  assert.equal(await page.locator('input[type=checkbox]:disabled').count(),2);
  await new Promise(r=>setTimeout(r,2100));
  await page.locator('.queue-row .row-similar').last().click();await page.locator('.track').first().waitFor();
  assert.equal(await page.locator('.track .row-similar').count(),2);
  await new Promise(r=>setTimeout(r,2100));
  await page.locator('.track .row-similar').last().click();await page.locator('.track').first().waitFor();
  assert.equal(await page.locator('#similar-current').count(),0);
  require('fs').mkdirSync('dist/qa',{recursive:true});
  await page.screenshot({path:'dist/qa/party-guest-without-ai.png',fullPage:true});
  const ingress=await browser.newPage();await ingress.goto('http://127.0.0.1:18103/');
  await ingress.locator('#open').waitFor({state:'visible'});
  assert.equal(await ingress.locator('#open').getAttribute('href'),'http://127.0.0.1:18102/guest/');
  assert(!(await ingress.locator('#url').textContent()).includes('secret'));
  assert(await ingress.locator('#kiosk').isVisible());
  assert((await ingress.locator('#ai-status').textContent()).includes('ai_dj_url'));
  assert((await ingress.locator('#kiosk').textContent()).includes('browser-fixture-host-secret'));
  await ingress.locator('#placement').selectOption('next');
  await ingress.locator('#method').selectOption('favorites');
  await ingress.locator('#count').selectOption('1');
  await ingress.locator('#continuous').check();
  await ingress.locator('#save').click();
  await ingress.getByText('Party-indstillingerne er gemt',{exact:true}).waitFor();
  await page.locator('#queue-help').filter({hasText:'som næste'}).waitFor();
  assert((await page.locator('#queue-help').textContent()).includes('fortsætter automatisk'));
  const guestToken=await page.evaluate(()=>sessionStorage.getItem('party-guest-token'));
  const denied=await fetch('http://127.0.0.1:18102/api/party-settings',{method:'POST',headers:{Authorization:'Bearer '+guestToken,'Content-Type':'application/json'},body:JSON.stringify({queue_id:'group',continuous:false})});
  assert.equal(denied.status,403);
  await page.screenshot({path:'dist/qa/party-guest-without-ai.png',fullPage:true});
  await ingress.locator('#method').selectOption('ai');
  await ingress.locator('#prompt').fill('Rolig jazz');
  await ingress.locator('#save').click();
  await ingress.getByText('Party-indstillingerne er gemt',{exact:true}).waitFor();
  await page.locator('[data-mode=ai]').waitFor({state:'visible'});
  assert.equal(await page.locator('[data-mode]:visible').count(),3);
  await page.locator('[data-mode=ai]').click();
  assert((await page.locator('#help').textContent()).includes('AI foreslår'));
  await page.locator('#query').fill('Rolig jazz');await page.locator('#search').click();
  await page.locator('.track').first().waitFor();
  await page.setViewportSize({width:1280,height:900});
  await page.screenshot({path:'dist/qa/party-guest-three-modes.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Independent guest browser checks passed: direct URL, expired-token recovery, no AI, search, similarity, append and ingress link.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
