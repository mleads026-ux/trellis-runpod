const GRAPHQL_URL = "https://api.runpod.io/graphql";
const INVOKE_URL = "https://api.runpod.ai/v2";
const respond = (status, data) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
const getData = async (query, variables, env) => {
  const response = await fetch(GRAPHQL_URL, { method: "POST", headers: { Authorization: `Bearer ${env.RUNPOD_API_KEY}`, "Content-Type": "application/json" }, body: JSON.stringify({ query, variables }) });
  const data = await response.json();
  if (!response.ok || data.errors) throw new Error(JSON.stringify(data.errors || data));
  return data.data;
};
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return respond(200, { status: "ok", service: "trellis-runpod-api", paidOperations: "locked" });
    if (url.pathname !== "/api/runpod") return respond(404, { error: "Not found" });
    if (!env.RUNPOD_API_KEY || !env.ACTION_API_KEY) return respond(503, { error: "Required secrets not configured" });
    if (request.headers.get("Authorization") !== `Bearer ${env.ACTION_API_KEY}`) return respond(401, { error: "Unauthorized" });
    const body = request.method === "POST" ? await request.json().catch(() => ({})) : {};
    const action = request.method === "GET" ? url.searchParams.get("action") : body.action;
    try {
      if (request.method === "GET" && (action === "gpu_types" || action === "budget_preview")) {
        const data = await getData("query { gpuTypes { id displayName memoryInGb } }", {}, env);
        return respond(200, action === "gpu_types" ? data : { budgetUsd: 2, reserveUsd: 0.5, gpuHourlyLimitUsd: 0.8, pricesVerified: false, warning: "GPU metadata only. Hourly and storage prices are not verified. No GPU started.", gpuTypes: data.gpuTypes });
      }
      if (request.method === "GET" && action === "pods") return respond(200, await getData("query { myself { pods { id name desiredStatus costPerHr gpuCount } } }", {}, env));
      if (request.method === "POST" && ["create_pod", "start_pod", "submit_job"].includes(action)) return respond(423, { error: "Billable actions locked until independent budget protection is implemented" });
      if (request.method === "POST" && action === "terminate_pod") {
        if (typeof body.pod_id !== "string" || !/^[a-zA-Z0-9_-]{1,128}$/.test(body.pod_id)) return respond(400, { error: "Valid pod_id required" });
        return respond(200, await getData("mutation ($id: String!) { podTerminate(input: { podId: $id }) }", { id: body.pod_id }, env));
      }
      if (request.method === "POST" && action === "stop_pod") {
        if (!env.RUNPOD_POD_ID) return respond(400, { error: "RUNPOD_POD_ID not configured" });
        return respond(200, await getData("mutation ($id: String!) { podStop(input: { podId: $id }) { id desiredStatus } }", { id: env.RUNPOD_POD_ID }, env));
      }
      if (request.method === "GET" && action === "job_status") {
        const id = url.searchParams.get("job_id");
        if (!id || !/^[a-zA-Z0-9_-]{1,128}$/.test(id)) return respond(400, { error: "Invalid job_id" });
        if (!env.RUNPOD_ENDPOINT_ID) return respond(503, { error: "RUNPOD_ENDPOINT_ID not configured" });
        const response = await fetch(`${INVOKE_URL}/${encodeURIComponent(env.RUNPOD_ENDPOINT_ID)}/status/${encodeURIComponent(id)}`, { headers: { Authorization: `Bearer ${env.RUNPOD_API_KEY}` } });
        return respond(response.status, await response.json());
      }
      return respond(400, { error: "Unsupported action or method" });
    } catch (error) { return respond(502, { error: "RunPod request failed", detail: String(error.message).slice(0, 700) }); }
  }
};
