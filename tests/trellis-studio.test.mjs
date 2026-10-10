import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/trellis-studio-worker.js";
const SITE = "https://studio.example.test";
const POD = "https://89zylb8g34o8o5-8000.proxy.runpod.net";
const ID = "a".repeat(24);
const auth = {Authorization: "Bearer this-is-a-test-secret"};
function req(path, options={}) {
  return new Request(SITE+path,options);
}
function mockFetch(t, handler) {
  t.mock.method(globalThis,"fetch",handler);
}
const parsed = async r => await r.json();
test("public studio loads Arabic upload form with no persistence",async()=>{
  const res=await worker.fetch(req("/"),{});
  assert.equal(res.status,200);
  assert.match(res.headers.get("content-type"),/text\/html/);
  assert.equal(res.headers.get("cache-control"),"no-store");
  assert.equal(res.headers.get("x-frame-options"),"DENY");
  assert.match(await res.text(),/TRELLIS_API_KEY/);
});
test("studio alias and unknown paths",async()=>{
  assert.equal((await worker.fetch(req("/studio"),{})).status,200);
  assert.equal((await worker.fetch(req("/unrelated"),{})).status,404);
});
test("health returns ready GPU diagnostics without requiring secret",async t=>{
  mockFetch(t,(url)=>{assert.equal(url,POD+"/health");return Response.json({status:"ready",gpu:{ready:true,gpu:"NVIDIA RTX A6000"},backup_ready:true});});
  const response=await worker.fetch(req("/api/trellis/health"),{});
  assert.equal(response.status,200);
  assert.equal((await parsed(response)).gpu.gpu,"NVIDIA RTX A6000");
});
test("health propagates GPU not-ready",async t=>{
  mockFetch(t,()=>Response.json({status:"not_ready",gpu:{ready:false,issues:["cuda"]},backup_ready:true},{status:503}));
  assert.equal((await worker.fetch(req("/api/trellis/health"),{})).status,503);
});
test("health fails closed on unreachable pod",async t=>{
  mockFetch(t,()=>{throw new Error("network error");});
  const response=await worker.fetch(req("/api/trellis/health"),{});
  assert.equal(response.status,502);
});
test("health rejects redirect from stale pod",async t=>{
  mockFetch(t,()=>new Response(null,{status:302,headers:{Location:"https://attacker.invalid"}}));
  assert.equal((await worker.fetch(req("/api/trellis/health"),{})).status,502);
});
test("no authentication means no job submission",async()=>{
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST"}),{});
  assert.equal(r.status,401);
});
test("no authentication means no job status lookup",async()=>{
  const r=await worker.fetch(req("/api/trellis/jobs/"+ID),{});
  assert.equal(r.status,401);
});
test("no authentication means no R2 download",async()=>{
  const r=await worker.fetch(req("/api/trellis/download/"+ID),{});
  assert.equal(r.status,401);
});
test("no arbitrary path may be proxied",async()=>{
  const r=await worker.fetch(req("/api/trellis/admin",{headers:auth}),{});
  assert.equal(r.status,404);
});
test("invalid job identifiers never reach Pod",async()=>{
  const r=await worker.fetch(req("/api/trellis/jobs/../../../other",{headers:auth}),{});
  assert.equal(r.status,404);
});
test("reject non-image Content-Type",async()=>{
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST",headers:{...auth,"Content-Type":"application/json"},body:"{}"}),{});
  assert.equal(r.status,415);
});
test("reject oversized declared request before upstream",async()=>{
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST",headers:{...auth,"Content-Type":"image/png","Content-Length":String(15*1024*1024+1)},body:new Uint8Array([1])}),{});
  assert.equal(r.status,413);
});
test("reject oversized actual request regardless of declared bytes",async()=>{
  const body=new Uint8Array(15*1024*1024+1);
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST",headers:{...auth,"Content-Type":"image/png"},body}),{});
  assert.equal(r.status,413);
});
test("valid PNG forwards only to pinned Pod with bearer auth",async t=>{
  mockFetch(t,(url,options)=>{
    assert.equal(url,POD+"/generate");
    assert.equal(options.method,"POST");
    assert.equal(options.headers.Authorization,auth.Authorization);
    assert.equal(options.headers["Content-Type"],"image/png");
    assert.equal(new Uint8Array(options.body).length,3);
    assert.equal(options.redirect,"manual");
    return Response.json({job_id:ID},{status:202});
  });
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST",headers:{...auth,"Content-Type":"image/png"},body:new Uint8Array([1,2,3])}),{});
  assert.equal(r.status,202);assert.equal((await parsed(r)).job_id,ID);
});
test("JPEG is accepted with optional content-type parameters",async t=>{
  mockFetch(t,(_url,options)=>{assert.equal(options.headers["Content-Type"],"image/jpeg");return Response.json({job_id:ID},{status:202});});
  const r=await worker.fetch(req("/api/trellis/generate",{method:"POST",headers:{...auth,"Content-Type":"image/jpeg; charset=binary"},body:new Uint8Array([255,216,255])}),{});
  assert.equal(r.status,202);
});
test("RunPod upstream unauthorized propagates without token in response",async t=>{
  mockFetch(t,()=>Response.json({error:"unauthorized"},{status:401}));
  const r=await worker.fetch(req("/api/trellis/jobs/"+ID,{headers:auth}),{});
  assert.equal(r.status,401);assert.equal((await parsed(r)).error,"unauthorized");
});
test("malformed upstream response is treated as bad gateway",async t=>{
  mockFetch(t,()=>new Response("<html>error</html>",{status:500}));
  const r=await worker.fetch(req("/api/trellis/jobs/"+ID,{headers:auth}),{});
  assert.equal(r.status,502);
});
test("runpod redirect is blocked to protect secret",async t=>{
  mockFetch(t,()=>new Response(null,{status:307,headers:{Location:"https://attacker.invalid"}}));
  const r=await worker.fetch(req("/api/trellis/jobs/"+ID,{headers:auth}),{});
  assert.equal(r.status,502);
});
test("job status calls exactly the pinned path",async t=>{
  mockFetch(t,(url,o)=>{assert.equal(url,POD+"/jobs/"+ID);assert.equal(o.headers.Authorization,auth.Authorization);return Response.json({status:"running",id:ID});});
  const r=await worker.fetch(req("/api/trellis/jobs/"+ID,{headers:auth}),{});
  assert.equal((await parsed(r)).status,"running");
});
test("download requires completed AND verified backup",async t=>{
  mockFetch(t,()=>Response.json({status:"running",id:ID}));
  const r=await worker.fetch(req("/api/trellis/download/"+ID,{headers:auth}),{});
  assert.equal(r.status,409);
});
test("download fails safely if no R2 binding",async t=>{
  mockFetch(t,()=>Response.json({status:"completed",backup:"verified"}));
  const r=await worker.fetch(req("/api/trellis/download/"+ID,{headers:auth}),{});
  assert.equal(r.status,503);
});
test("completed job returns backed up GLB with private binary headers",async t=>{
  mockFetch(t,()=>Response.json({status:"completed",backup:"verified"}));
  const data=new Uint8Array([103,108,84,70,2,0,0,0]);
  const env={TRELLIS_OUTPUTS:{
    async list({prefix,limit}){assert.equal(prefix,"models/"+ID+"-");assert.equal(limit,25);return {objects:[{key:"models/"+ID+"-"+"b".repeat(16)+".glb"}]};},
    async get(key){assert.equal(key,"models/"+ID+"-"+"b".repeat(16)+".glb");return {body:data,size:data.length};}
  }};
  const r=await worker.fetch(req("/api/trellis/download/"+ID,{headers:auth}),env);
  assert.equal(r.status,200);
  assert.equal(r.headers.get("content-type"),"model/gltf-binary");
  assert.match(r.headers.get("content-disposition"),new RegExp(ID));
  assert.deepEqual(new Uint8Array(await r.arrayBuffer()),data);
});
test("download refuses ambiguous R2 models for same job",async t=>{
  mockFetch(t,()=>Response.json({status:"completed",backup:"verified"}));
  const env={TRELLIS_OUTPUTS:{async list(){return {objects:[{key:"models/"+ID+"-"+"a".repeat(16)+".glb"},{key:"models/"+ID+"-"+"b".repeat(16)+".glb"}]};}}};
  const r=await worker.fetch(req("/api/trellis/download/"+ID,{headers:auth}),env);
  assert.equal(r.status,404);
});
test("missing job can't authorize R2 read",async t=>{
  mockFetch(t,()=>Response.json({error:"not found"},{status:404}));
  const r=await worker.fetch(req("/api/trellis/download/"+ID,{headers:auth}),{});
  assert.equal(r.status,404);
});

test("recovery from failed backup authorizes valid local Pod job then reads R2",async t=>{
  mockFetch(t,(url)=>{assert.equal(url,POD+"/jobs/"+ID);return Response.json({status:"failed",id:ID,error:"BACKUP_FAILED: HTTP 403"});});
  const bytes=new Uint8Array([103,108,84,70,2,0,0,0]);
  const env={TRELLIS_OUTPUTS:{
    async list({prefix}){assert.equal(prefix,"models/"+ID+"-");return {objects:[{key:"models/"+ID+"-"+"b".repeat(16)+".glb"}]};},
    async get(){return {body:bytes,size:bytes.length};}
  }};
  const r=await worker.fetch(req("/api/trellis/recover/"+ID,{headers:auth}),env);
  assert.equal(r.status,200);assert.deepEqual(new Uint8Array(await r.arrayBuffer()),bytes);
});
test("recovery must reject an in-progress job",async t=>{
  mockFetch(t,()=>Response.json({status:"running",id:ID}));
  const r=await worker.fetch(req("/api/trellis/recover/"+ID,{headers:auth}),{});
  assert.equal(r.status,409);
});
test("R2 recovery requires Pod bearer token",async()=>{
  assert.equal((await worker.fetch(req("/api/trellis/recover/"+ID),{})).status,401);
});
test("R2 recovery refuses missing file even when job failed",async t=>{
  mockFetch(t,()=>Response.json({status:"failed",id:ID}));
  const env={TRELLIS_OUTPUTS:{async list(){return {objects:[]}}}};
  const r=await worker.fetch(req("/api/trellis/recover/"+ID,{headers:auth}),env);
  assert.equal(r.status,404);
});
