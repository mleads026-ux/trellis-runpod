// Read-only Pod discovery for queued launches. Never terminates or starts a Pod.
// Exact-name matching is NOT proof of queue ownership. Never arm termination based
// solely on this discovery; confirm immutable Pod ID and independent safety first.
const GRAPHQL = "https://api.runpod.io/graphql";
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$/;

export function selectCandidate(pods, expectedName) {
  if (!SAFE_NAME.test(expectedName || "")) return {status:"invalid_name"};
  if (!Array.isArray(pods)) return {status:"invalid_response"};
  const matches = pods.filter(p => p && p.name === expectedName && typeof p.id === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(p.id));
  if (matches.length === 0) return {status:"not_found"};
  if (matches.length > 1) return {status:"ambiguous",count:matches.length};
  return {status:"candidate_unverified",podId:matches[0].id,name:expectedName,desiredStatus:matches[0].desiredStatus || null};
}

export async function discover(env, fetchImpl=fetch) {
  if (env.WATCHDOG_DISCOVERY_ENABLED !== "yes") return {status:"disabled"};
  if (!env.RUNPOD_API_KEY) return {status:"missing_runpod_secret"};
  if (!SAFE_NAME.test(env.WATCHDOG_EXPECTED_POD_NAME || "")) return {status:"invalid_name"};
  const response = await fetchImpl(GRAPHQL,{
    method:"POST",
    headers:{"Authorization":`Bearer ${env.RUNPOD_API_KEY}`,"Content-Type":"application/json"},
    body:JSON.stringify({query:"query { myself { pods { id name desiredStatus } } }"}),
    signal:AbortSignal.timeout(12000)
  });
  if(!response.ok) throw Error("RunPod discovery failed HTTP "+response.status);
  const json=await response.json();
  if(json.errors || !json.data?.myself) throw Error("RunPod discovery GraphQL failed");
  return selectCandidate(json.data.myself.pods,env.WATCHDOG_EXPECTED_POD_NAME);
}
