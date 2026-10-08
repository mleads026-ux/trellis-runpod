import { strict as assert } from "node:assert";
import { test } from "node:test";
import { discover, selectCandidate } from "../src/pod-discovery.js";

test("disabled by default; no RunPod request", async () => {
 let calls=0;
 assert.deepEqual(await discover({},async()=>{calls++;throw Error("network used")}),{status:"disabled"});
 assert.equal(calls,0);
});
test("missing secret fails closed", async()=>{
 assert.equal((await discover({WATCHDOG_DISCOVERY_ENABLED:"yes",WATCHDOG_EXPECTED_POD_NAME:"trellis-a5000"})).status,"missing_runpod_secret");
});
test("invalid name and missing Pod fail closed",()=>{
 assert.equal(selectCandidate([],""),"invalid_name");
});
test("unique exact match is unverified candidate, not authorization",()=>{
 const result=selectCandidate([{id:"a1",name:"trellis-a5000",desiredStatus:"RUNNING"},{id:"b2",name:"other"}],"trellis-a5000");
 assert.equal(result.status,"candidate_unverified");
 assert.equal(result.podId,"a1");
});
test("ambiguous name never selects a Pod",()=>{
 const result=selectCandidate([{id:"a1",name:"trellis-a5000"},{id:"a2",name:"trellis-a5000"}],"trellis-a5000");
 assert.equal(result.status,"ambiguous");
 assert.equal(result.podId,undefined);
});
test("read-only query; no mutation",async()=>{
 let query="";
 const result=await discover({WATCHDOG_DISCOVERY_ENABLED:"yes",WATCHDOG_EXPECTED_POD_NAME:"trellis-a5000",RUNPOD_API_KEY:"mock"},async(_url,opts)=>{
   query=JSON.parse(opts.body).query;
   return {ok:true,json:async()=>({data:{myself:{pods:[{id:"abc",name:"trellis-a5000"}]}}})};
 });
 assert.equal(result.status,"candidate_unverified");
 assert.match(query,/^query /);
 assert.doesNotMatch(query,/mutation|podTerminate|podCreate/i);
});
test("GraphQL errors are rejected",async()=>{
 await assert.rejects(discover({WATCHDOG_DISCOVERY_ENABLED:"yes",WATCHDOG_EXPECTED_POD_NAME:"trellis-a5000",RUNPOD_API_KEY:"mock"},async()=>({ok:true,json:async()=>({errors:[{message:"fail"}]})})),/GraphQL/);
});
