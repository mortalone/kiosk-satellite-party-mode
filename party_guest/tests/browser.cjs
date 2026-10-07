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
  await page.locator('#similar-current').waitFor({state:'visible'});
  assert.equal(await page.locator('[data-mode=ai]:visible').count(),0);
  for(const mode of ['library','similar']){
   if(mode==='similar')await new Promise(r=>setTimeout(r,2100));
   await page.locator('[data-mode='+mode+']').click();await page.locator('#query').fill('Jazz');
   await page.locator('#search').click();await page.locator('.track').first().waitFor();
  }
  await page.locator('#add').click();await page.getByText('2 numre tilføjet til køen',{exact:true}).waitFor();
  assert.equal(await page.locator('input[type=checkbox]:disabled').count(),2);
  await new Promise(r=>setTimeout(r,2100));
  await page.locator('#similar-current').click();await page.locator('.track').first().waitFor();
  require('fs').mkdirSync('dist/qa',{recursive:true});
  await page.screenshot({path:'dist/qa/party-guest-without-ai.png',fullPage:true});
  const ingress=await browser.newPage();await ingress.goto('http://127.0.0.1:18103/');
  await ingress.locator('#open').waitFor({state:'visible'});
  assert.equal(await ingress.locator('#open').getAttribute('href'),'http://127.0.0.1:18102/guest/');
  assert(!(await ingress.locator('#url').textContent()).includes('secret'));
  assert((await ingress.locator('#kiosk').textContent()).includes('browser-fixture-host-secret'));
  assert.deepEqual(errors,[]);
  console.log('Independent guest browser checks passed: direct URL, expired-token recovery, no AI, search, similarity, append and ingress link.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
