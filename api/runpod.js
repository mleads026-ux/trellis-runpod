const GRAPHQL_URL = "https://api.runpod.io/graphql";
const INVOKE_URL = "https://api.runpod.ai/v2";

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
    if (req.method === "GET" && action === "gpu_types") {
      const data = await graphql("query { gpuTypes { id displayName memoryInGb secureCloud communityCloud lowestPrice(input: { gpuCount: 1 }) { minimumBidPrice uninterruptablePrice } } }");
      return reply(res, 200, data);
    }
    if (req.method === "GET" && action === "pods") {
      const data = await graphql("query { myself { pods { id name desiredStatus costPerHr gpuCount } } }");
      return reply(res, 200, data);
    }
    if (req.method === "POST" && (action === "start_pod" || action === "stop_pod")) {
      if (!podId) return reply(res, 400, { error: "RUNPOD_POD_ID is not configured" });
      const mutation = action === "start_pod"
        ? "mutation ($id: String!) { podResume(input: { podId: $id, gpuCount: 1 }) { id desiredStatus } }"
        : "mutation ($id: String!) { podStop(input: { podId: $id }) { id desiredStatus } }";
      const data = await graphql(mutation, { id: podId });
      return reply(res, 200, data);
    }
    if (req.method === "POST" && action === "submit_job") {
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
