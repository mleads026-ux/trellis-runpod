import { discover } from "./pod-discovery.js";
// Standalone Cloudflare scheduled watchdog. NOT ARMED by default.
// Deploy as a separate Worker only after mock tests and explicit authorization.
// Required runtime secrets: RUNPOD_API_KEY, WATCHDOG_POD_ID, WATCHDOG_DEADLINE_UTC,
// WATCHDOG_ARMED='yes'. Never use a secret or Pod ID in source control.
const GRAPHQL = "https://api.runpod.io/graphql";
const ID = /^[A-Za-z0-9_-]{1,128}$/;
async function gql(env, query, variables={}) {
  const res = await fetch(GRAPHQL, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RUNPOD_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({query, variables}),
    signal: AbortSignal.timeout(12000)
  });
  const payload = await res.json();
  if (!res.ok || payload.errors) throw new Error("RunPod API failed: "+res.status);
  return payload.data;
}
export function validateConfig(env, now=Date.now()) {
  if (env.WATCHDOG_ARMED !== "yes") return {armed:false, reason:"not armed"};
  if (!env.RUNPOD_API_KEY || !ID.test(env.WATCHDOG_POD_ID || "")) throw new Error("Invalid watchdog secrets or pod ID");
  const deadline = Date.parse(env.WATCHDOG_DEADLINE_UTC || "");
  if (!Number.isFinite(deadline) || !/Z$/.test(env.WATCHDOG_DEADLINE_UTC || "")) throw new Error("Invalid UTC deadline");
  // Only a hard deadline, never a GPT-supplied cost estimate.
  return {armed:true, expired:now>=deadline, podId:env.WATCHDOG_POD_ID};
}
export async function watchdog(env, now=Date.now(), api=gql) {
  const cfg=validateConfig(env,now);
  if (!cfg.armed) return {status:"disarmed"};
  if (!cfg.expired) return {status:"waiting"};
  // At/after deadline always try termination, including on repeat invocations.
  // Do not merely stop: stopped Pods can still incur storage charges.
  const before=await api(env,"query { myself { pods { id desiredStatus } } }");
  const pod=before?.myself?.pods?.find(p=>p.id===cfg.podId);
  if (!pod) return {status:"not_listed", podId:cfg.podId};
  await api(env,"mutation ($id: String!) { podTerminate(input: { podId: $id }) }",{id:cfg.podId});
  const after=await api(env,"query { myself { pods { id desiredStatus } } }");
  const stillListed=after?.myself?.pods?.some(p=>p.id===cfg.podId);
  if (stillListed) throw new Error("Pod still listed; retry on next cron invocation");
  return {status:"terminated_verified", podId:cfg.podId};
}
export default {
  async scheduled(_event,env,ctx) {
    ctx.waitUntil(Promise.all([watchdog(env), discover(env)]).then(([w,d])=>console.log("Watchdog:",w.status,"Discovery:",d.status)).catch(e=>{
      console.error("WATCHDOG FAILED:",String(e));
      throw e;
    }));
  },
  async fetch() {return new Response(JSON.stringify({status:"watchdog",armedByDefault:false}),{
    status:200,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}
  });}
};
