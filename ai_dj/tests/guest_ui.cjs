const {chromium}=require('playwright');
const fs=require('fs'); const assert=require('assert');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
 let modes={library:true,similar:true,ai:true,current_similar:true},lastMode='',added=[];
 const tracks=[{name:'Aftenlys',artists:[{name:'Natteholdet'}],uri:'library://track/1'},{name:'Stjernestøv',artists:[{name:'Natteholdet'}],uri:'library://track/2'}];
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.route('http://party.test/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname;
   if(path==='/guest/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('ai_dj/guest.html','utf8')});
   assert.equal(req.headers().authorization,'Bearer demo-guest-capability');
   let result;
   if(path.endsWith('/config'))result={modes,current:{name:'Aftenlys',uri:tracks[0].uri}};
   else if(path.endsWith('/search')){lastMode=req.postDataJSON().mode;added=[];result={id:'demo'};}
   else if(path.endsWith('/jobs/demo'))result={id:'demo',state:'ready',tracks,added};
   else if(path.endsWith('/queue')){assert.deepEqual(req.postDataJSON(),{id:'demo',indices:[0,1]});added=[0,1];result={queued:2};}
   else throw Error('Unexpected '+path);
   await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
 });
 await page.goto('http://party.test/guest/#token=demo-guest-capability');
 await page.locator('#similar-current').waitFor({state:'visible'});
 assert(!page.url().includes('token='));
 for(const mode of ['library','similar','ai']){
  await page.locator('[data-mode='+mode+']').click();await page.locator('#query').fill('rolig jazz med saxofon');
  await page.locator('#search').click();await page.locator('.track').first().waitFor();assert.equal(lastMode,mode);
 }
 fs.mkdirSync('dist/qa',{recursive:true});await page.screenshot({path:'dist/qa/guest-page-preview.png',fullPage:true});
 await page.locator('#add').click();await page.getByText('2 numre tilføjet til køen',{exact:true}).waitFor();
 assert.equal(await page.locator('input[type=checkbox]:disabled').count(),2);
 await page.locator('#similar-current').click();await page.locator('.track').first().waitFor();assert.equal(lastMode,'current_similar');
 modes={library:false,similar:false,ai:false,current_similar:false};
 await page.locator('form').waitFor({state:'hidden',timeout:18000});
 assert.equal(await page.locator('[data-mode]:visible').count(),0);assert.deepEqual(errors,[]);
 await browser.close();console.log('Guest browser checks passed: three modes, current-track similarity, append, hidden modes, token removal.');
})().catch(e=>{console.error(e);process.exit(1)});
