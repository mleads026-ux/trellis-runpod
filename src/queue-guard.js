// Automatic protection for a uniquely named RunPod auto-deploy Pod.
// Deliberately disabled unless WATCHDOG_AUTO_ARM=yes. This is NOT a hard billing cap.
// Only a single exact-name candidate in an otherwise empty Pod account is eligible.
// KV persists immutable pod ID and the first-observed deadline across cron invocations.
const ID=/^[A-Za-z0-9_-]{1,128}$/;
const GQL="https://api.runpod.io/graphql";
export async function queueGuard(env,now=Date.now(),api=async(query,variables={})=>{
 const r=await fetch(GQL,{method:"POST",headers:{Authorization:`Bearer ${env.RUNPOD_API_KEY}`,"Content-Type":"application/json"},body:JSON.stringify({query,variables}),signal:AbortSignal.timeout(12000)});
 const j=await r.json();if(!r.ok||j.errors||!j.data)throw Error("RunPod GraphQL failure");return j.data;
}){
 if(env.WATCHDOG_AUTO_ARM!=="yes")return {status:"disabled"};
 if(!env.RUNPOD_API_KEY||!env.WATCHDOG_STATE||env.WATCHDOG_EXPECTED_POD_NAME!=="outdoor_silver_sparrow")throw Error("Auto protection configuration invalid");
 const q="query { myself { pods { id name desiredStatus } } }";
 const data=await api(q);const pods=data?.myself?.pods;
 if(!Array.isArray(pods))throw Error("Invalid Pod list");
 const key="protected-pod-v1";let saved=await env.WATCHDOG_STATE.get(key,"json");
 if(!saved){
  if(pods.length===0)return {status:"waiting_for_pod"};
  if(pods.length!==1||pods[0]?.desiredStatus==="EXITED"||pods[0]?.name!=="outdoor_silver_sparrow"||!ID.test(pods[0]?.id||""))return {status:"identity_ambiguous"};
  saved={podId:pods[0].id,firstObserved:now,deadline:now+5*60*1000};
  await env.WATCHDOG_STATE.put(key,JSON.stringify(saved));
  const persisted=await env.WATCHDOG_STATE.get(key,"json");
  if(persisted?.podId!==saved.podId)throw Error("State persistence failed");
  return {status:"protected_timer_started"};
 }
 if(!ID.test(saved.podId||"")||!Number.isFinite(saved.deadline))throw Error("Invalid persisted protection state");
 const target=pods.find(p=>p.id===saved.podId);
 if(!target)return {status:"pod_absent"};
 if(target.name!=="outdoor_silver_sparrow")throw Error("Protected Pod identity changed");
 if(target.desiredStatus==="EXITED")return {status:"already_stopped"};
 if(now<saved.deadline)return {status:"protected_waiting"};
 const mutation=await api("mutation ($id: String!) { podStop(input: { podId: $id }) }",{id:saved.podId});
 if(mutation?.podStop!==true)throw Error("RunPod rejected stop");
 const after=await api(q);
 const stopped=after?.myself?.pods?.find(p=>p.id===saved.podId);
 if(!Array.isArray(after?.myself?.pods)||!stopped||stopped.desiredStatus!=="EXITED")throw Error("Stop unverified; retry");
 return {status:"stopped_verified"};
}
