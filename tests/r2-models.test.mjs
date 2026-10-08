import { test } from "node:test";
import { strict as assert } from "node:assert";
import worker from "../src/worker.js";

function setup() {
 const objects=new Map();
 const bucket={
   head:async key=>objects.get(key)?{size:objects.get(key).byteLength}:null,
   get:async key=>objects.get(key)?{body:objects.get(key),size:objects.get(key).byteLength}:null,
   put:async(key,body)=>{if(objects.has(key))return null;const data=new Uint8Array(await new Response(body).arrayBuffer());objects.set(key,data);return {size:data.byteLength,httpEtag:'"mock"'};}
 };
 return {env:{ACTION_API_KEY:"test-secret",TRELLIS_OUTPUTS:bucket},objects};
}
function req(path,method="GET",headers={},body){return new Request("https://example.test"+path,{method,headers,body,duplex:body?"half":undefined});}
test("private GLB storage rejects unauthenticated requests",async()=>{
 const {env}=setup();
 for(const method of ["GET","PUT","HEAD"]){const r=await worker.fetch(req("/api/models/test.glb",method),env);assert.equal(r.status,401);}
});
test("private GLB upload download and HEAD round trip",async()=>{
 const {env}=setup();const path="/api/models/model-1.glb";
 const headers={Authorization:"Bearer test-secret","Content-Type":"model/gltf-binary","Content-Length":"4"};
 const uploaded=await worker.fetch(req(path,"PUT",headers,new Uint8Array([1,2,3,4])),env);
 assert.equal(uploaded.status,201);
 const head=await worker.fetch(req(path,"HEAD",{Authorization:"Bearer test-secret"}),env);
 assert.equal(head.status,200);assert.equal(head.headers.get("Content-Length"),"4");
 const downloaded=await worker.fetch(req(path,"GET",{Authorization:"Bearer test-secret"}),env);
 assert.equal(downloaded.status,200);
 assert.deepEqual([...new Uint8Array(await downloaded.arrayBuffer())],[1,2,3,4]);
 assert.equal((await worker.fetch(req(path,"PUT",headers,new Uint8Array([5,6,7,8])),env)).status,409);
});
test("private GLB storage blocks traversal, oversized and incorrect media",async()=>{
 const {env}=setup();
 for(const name of ["bad.txt","..evil.glb","evil..glb"]){
  const r=await worker.fetch(req("/api/models/"+name,"GET",{Authorization:"Bearer test-secret"}),env);
  assert.equal(r.status,400);
 }
 const base={Authorization:"Bearer test-secret","Content-Type":"model/gltf-binary"};
 assert.equal((await worker.fetch(req("/api/models/ok.glb","PUT",{...base,"Content-Length":String(101*1024*1024)},new Uint8Array([1])),env)).status,413);
 assert.equal((await worker.fetch(req("/api/models/ok.glb","PUT",{...base,"Content-Type":"application/json","Content-Length":"1"},new Uint8Array([1])),env)).status,415);
});
