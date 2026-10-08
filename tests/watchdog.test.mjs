import { strict as assert } from "node:assert";
import { test } from "node:test";
import { watchdog, validateConfig } from "../src/watchdog.js";
const base={WATCHDOG_ARMED:"yes",RUNPOD_API_KEY:"mock",WATCHDOG_POD_ID:"test-pod",WATCHDOG_DEADLINE_UTC:"2026-10-08T00:00:00Z"};
const before=Date.parse("2026-10-07T23:59:00Z"), after=Date.parse("2026-10-08T00:01:00Z");
test("disarmed by default",async()=>{assert.equal((await watchdog({})).status,"disarmed");});
test("invalid configuration fails closed",()=>{
 assert.throws(()=>validateConfig({...base,RUNPOD_POD_ID:"x",WATCHDOG_POD_ID:"bad id"},after));
 assert.throws(()=>validateConfig({...base,WATCHDOG_DEADLINE_UTC:"bad"},after));
 assert.throws(()=>validateConfig({...base,RUNPOD_API_KEY:""},after));
});
test("before deadline never calls API",async()=>{
 let calls=0; const result=await watchdog(base,before,async()=>{calls++;});
 assert.equal(result.status,"waiting"); assert.equal(calls,0);
});
test("after deadline terminates and verifies",async()=>{
 let present=true,term=0;
 const api=async(_env,query)=>{
  if(query.includes("podTerminate")){present=false;term++;return {};}
  return {myself:{pods:present?[{id:"test-pod",desiredStatus:"RUNNING"}]:[]}};
 };
 assert.equal((await watchdog(base,after,api)).status,"terminated_verified");
 assert.equal(term,1);
 assert.equal((await watchdog(base,after,api)).status,"not_listed");
});
test("API failure propagates for retry",async()=>{
 await assert.rejects(watchdog(base,after,async()=>{throw Error("mock API offline")}),/offline/);
});
test("termination not confirmed fails for retry",async()=>{
 const api=async(_env,query)=>query.includes("podTerminate")?{}:{myself:{pods:[{id:"test-pod"}]}};
 await assert.rejects(watchdog(base,after,api),/still listed/);
});
test("unrelated pod is never terminated",async()=>{
 let terminated=false;
 const api=async(_env,query)=>{
  if(query.includes("podTerminate"))terminated=true;
  return {myself:{pods:[{id:"someone-else"}]}};
 };
 assert.equal((await watchdog(base,after,api)).status,"not_listed");
 assert.equal(terminated,false);
});
