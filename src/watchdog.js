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
  const termination=await api(env,"mutation ($id: String!) { podTerminate(input: { podId: $id }) }",{id:cfg.podId});
  if (termination?.podTerminate === false || termination?.podTerminate === null) throw new Error("RunPod termination was not accepted; retry next cron");
  const after=await api(env,"query { myself { pods { id desiredStatus } } }");
  const stillListed=after?.myself?.pods?.some(p=>p.id===cfg.podId);
  if (stillListed) throw new Error("Pod still listed; retry on next cron invocation");
  return {status:"terminated_verified", podId:cfg.podId};
}
export default {
  async scheduled(_event,env,ctx) {
    ctx.waitUntil(Promise.allSettled([watchdog(env), discover(env)]).then(([w,d])=>{
      if (w.status==="fulfilled") console.log("Watchdog:",w.value.status);
      else console.error("WATCHDOG FAILED:",String(w.reason));
      if (d.status==="fulfilled") console.log("Discovery:",d.value.status);
      else console.error("DISCOVERY FAILED:",String(d.reason));
      if (w.status==="rejected") throw w.reason;
    }));
  },
  async fetch(request,env) {
    const url=new URL(request.url);
    if (request.method !== "GET" || url.pathname !== "/health") return new Response("Not found",{status:404});
    // Public probe: safe aggregated status only; no Pod IDs, names, credentials, or API error details.
    // Rate limiting and cache-control should be added before making this widely accessible.
    const armed=env.WATCHDOG_ARMED==="yes";
    try {
      const d=await discover(env);
      return new Response(JSON.stringify({service:"trellis-runpod-watchdog",discovery:d.status,runpodConnection:d.status==="disabled"||d.status==="missing_runpod_secret"||d.status==="invalid_name"?"not_tested":d.status==="invalid_response"?"failed":"ok",terminationArmed:armed,automaticQueueProtection:false}),{status:200,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
    } catch (_error) {
      return new Response(JSON.stringify({service:"trellis-runpod-watchdog",discovery:"error",runpodConnection:"failed",terminationArmed:armed,automaticQueueProtection:false}),{status:503,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
    }
  }
};
