const GRAPHQL_URL = "https://api.runpod.io/graphql";
const INVOKE_URL = "https://api.runpod.ai/v2";
const MAX_TOTAL_BUDGET_USD = 2;
const MAX_GPU_HOURLY_USD = 0.8;
const RESERVED_COST_USD = 0.5; // conservative storage/setup allowance; not a provider quote

function reply(res, status, value) {
  res.status(status).setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(value));
}
async function graphql(query, variables = {}) {
  const response = await fetch(GRAPHQL_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RUNPOD_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, variables })
  });
  const body = await response.json();
  if (!response.ok || body.errors) throw new Error(JSON.stringify(body.errors || body));
  return body.data;
}
async function serverless(path, method = "GET", input) {
  const endpoint = process.env.RUNPOD_ENDPOINT_ID;
  if (!endpoint) throw new Error("RUNPOD_ENDPOINT_ID is not configured");
  const response = await fetch(`${INVOKE_URL}/${encodeURIComponent(endpoint)}/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${process.env.RUNPOD_API_KEY}`,
      "Content-Type": "application/json"
    },
    ...(method === "POST" ? { body: JSON.stringify({ input }) } : {})
  });
  const body = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(body));
  return body;
}
export default async function handler(req, res) {
  if (!process.env.RUNPOD_API_KEY || !process.env.ACTION_API_KEY) {
    return reply(res, 503, { error: "Required server environment variables are missing" });
  }
  if (req.headers.authorization !== `Bearer ${process.env.ACTION_API_KEY}`) {
    return reply(res, 401, { error: "Unauthorized" });
  }
  const action = req.method === "GET" ? req.query.action : req.body?.action;
  const podId = process.env.RUNPOD_POD_ID;
  try {
    if (req.method === "GET" && (action === "gpu_types" || action === "budget_preview")) {
      const data = await graphql("query { gpuTypes { id displayName memoryInGb secureCloud communityCloud lowestPrice(input: { gpuCount: 1 }) { minimumBidPrice uninterruptablePrice } } }");
      if (action === "budget_preview") {
        return reply(res, 200, {
          budgetUsd: MAX_TOTAL_BUDGET_USD,
          reserveUsd: RESERVED_COST_USD,
          gpuHourlyLimitUsd: MAX_GPU_HOURLY_USD,
          warning: "Prices are indicative RunPod API values; availability, storage and actual billed cost are not guaranteed. No GPU is started.",
          gpuTypes: data.gpuTypes
        });
      }
      return reply(res, 200, data);
    }
    if (req.method === "GET" && action === "pods") {
      const data = await graphql("query { myself { pods { id name desiredStatus costPerHr gpuCount } } }");
      return reply(res, 200, data);
    }
    if (req.method === "POST" && action === "create_pod") {
      return reply(res, 423, { error: "Paid Pod creation locked until an independently verified automatic termination guard and preflight quote are installed. Use budget_preview." });
    }
    if (false && req.method === "POST" && action === "legacy_create_pod_disabled") {
      const gpuTypeId = req.body?.gpu_type_id;
      const cloudType = req.body?.cloud_type === "SECURE" ? "SECURE" : "COMMUNITY";
      const maxCostPerHr = Number(req.body?.max_cost_per_hr ?? 0.8);
      if (typeof gpuTypeId !== "string" || !gpuTypeId) return reply(res, 400, { error: "gpu_type_id is required" });
      const types = await graphql("query { gpuTypes { id displayName memoryInGb } }");
      const selected = types?.gpuTypes?.find(g => g.id === gpuTypeId);
      if (!selected) return reply(res, 400, { error: "Unknown gpu_type_id" });
      if (Number(selected.memoryInGb) < 24) return reply(res, 400, { error: "GPU rejected: TRELLIS asset factory requires at least 24GB VRAM", gpu: selected });
      if (!Number.isFinite(maxCostPerHr) || maxCostPerHr <= 0 || maxCostPerHr > 1) return reply(res, 400, { error: "max_cost_per_hr must be > 0 and <= 1" });
      const query = `mutation ($input: PodFindAndDeployOnDemandInput!) {
        podFindAndDeployOnDemand(input: $input) { id name desiredStatus costPerHr gpuCount machine { podHostId } }
      }`;
      const input = {
        name: "trellis-asset-factory",
        cloudType,
        gpuTypeId,
        gpuCount: 1,
        volumeInGb: 40,
        containerDiskInGb: 50,
        minVcpuCount: 4,
        minMemoryInGb: 16,
        imageName: "runpod/pytorch:2.4.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
        dockerArgs: "",
        ports: "22/tcp",
        volumeMountPath: "/workspace",
        env: []
      };
      const data = await graphql(query, { input });
      const pod = data?.podFindAndDeployOnDemand;
      if (pod?.costPerHr > maxCostPerHr) {
        try { await graphql("mutation ($id: String!) { podTerminate(input: { podId: $id }) }", { id: pod.id }); } catch {}
        return reply(res, 409, { error: "Created offer exceeded max_cost_per_hr and was terminated", quotedCostPerHr: pod.costPerHr });
      }
      return reply(res, 200, data);
    }
    if (req.method === "POST" && action === "terminate_pod") {
      const id = req.body?.pod_id;
      if (typeof id !== "string" || !id) return reply(res, 400, { error: "pod_id is required" });
      const data = await graphql("mutation ($id: String!) { podTerminate(input: { podId: $id }) }", { id });
      return reply(res, 200, data);
    }
    if (req.method === "POST" && action === "start_pod") {
      return reply(res, 423, { error: "Paid Pod resume locked until an independent timeout guard is installed." });
    }
    if (req.method === "POST" && action === "stop_pod") {
      if (!podId) return reply(res, 400, { error: "RUNPOD_POD_ID is not configured" });
      const mutation = "mutation ($id: String!) { podStop(input: { podId: $id }) { id desiredStatus } }";
      const data = await graphql(mutation, { id: podId });
      return reply(res, 200, data);
    }
    if (req.method === "POST" && action === "submit_job") {
      return reply(res, 423, { error: "Billable Serverless submissions locked pending budget guard." });
    }
    if (false && req.method === "POST" && action === "legacy_submit_job_disabled") {
      if (!req.body?.input || typeof req.body.input !== "object" || Array.isArray(req.body.input)) {
        return reply(res, 400, { error: "input must be a JSON object" });
      }
      return reply(res, 200, await serverless("run", "POST", req.body.input));
    }
    if (req.method === "GET" && action === "job_status") {
      const id = req.query.job_id;
      if (typeof id !== "string" || !/^[a-zA-Z0-9_-]{1,128}$/.test(id)) return reply(res, 400, { error: "Invalid job_id" });
      return reply(res, 200, await serverless(`status/${encodeURIComponent(id)}`));
    }
    return reply(res, 400, { error: "Unsupported action or method" });
  } catch (error) {
    return reply(res, 502, { error: "RunPod request failed", detail: String(error.message).slice(0, 700) });
  }
}
