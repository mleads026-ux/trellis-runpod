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
    if (url.pathname === "/api/storage-health" && request.method === "GET") {
      if (!env.TRELLIS_OUTPUTS) return respond(503, { status: "unconfigured", service: "trellis-r2" });
      try {
        const marker = await env.TRELLIS_OUTPUTS.head("_healthcheck/connection-probe");
        return respond(200, { status: "connected", service: "trellis-r2", bucket: "trellis-3d-outputs", probeObjectPresent: Boolean(marker) });
      } catch (_error) {
        return respond(503, { status: "storage_error", service: "trellis-r2" });
      }
    }
    // Private binary model transfer. Reuses ACTION_API_KEY; never exposes R2 publicly.
    if (url.pathname.startsWith("/api/models/")) {
      if (!env.ACTION_API_KEY || request.headers.get("Authorization") !== `Bearer ${env.ACTION_API_KEY}`) return respond(401, { error: "Unauthorized" });
      if (!env.TRELLIS_OUTPUTS) return respond(503, { error: "R2 not configured" });
      const name = url.pathname.slice("/api/models/".length);
      if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}[.]glb$/.test(name) || name.includes("..")) return respond(400, { error: "Invalid GLB filename" });
      const key = `models/${name}`;
      if (request.method === "PUT") {
        const length = Number(request.headers.get("Content-Length"));
        if (!Number.isSafeInteger(length) || length < 1 || length > 100 * 1024 * 1024) return respond(413, { error: "GLB upload requires Content-Length of 1 to 100 MiB" });
        if (request.headers.get("Content-Type") !== "model/gltf-binary") return respond(415, { error: "Content-Type must be model/gltf-binary" });
        if (await env.TRELLIS_OUTPUTS.head(key)) return respond(409, { error: "Model already exists; refusing overwrite" });
        const result = await env.TRELLIS_OUTPUTS.put(key, request.body, { httpMetadata: { contentType: "model/gltf-binary" }, onlyIf: { etagDoesNotMatch: "*" } });
        if (!result) return respond(409, { error: "Model already exists" });
        return respond(201, { status: "stored", filename: name, size: result.size, etag: result.httpEtag });
      }
      if (request.method === "GET") {
        const object = await env.TRELLIS_OUTPUTS.get(key);
        if (!object) return respond(404, { error: "Model not found" });
        return new Response(object.body, { status: 200, headers: { "Content-Type": "model/gltf-binary", "Content-Length": String(object.size), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
      }
      if (request.method === "HEAD") {
        const object = await env.TRELLIS_OUTPUTS.head(key);
        if (!object) return new Response(null, { status: 404 });
        return new Response(null, { status: 200, headers: { "Content-Length": String(object.size), "Cache-Control": "private, no-store" } });
      }
      return respond(405, { error: "Method not allowed" });
    }
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
      if (request.method === "POST" && action === "terminate_pod") return respond(423, { error: "Pod termination disabled by owner preference; use stop_pod instead" });
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
