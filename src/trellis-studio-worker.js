// Browser-to-TRELLIS relay on a fixed, user-provided RunPod Pod endpoint.
// Zero secrets in this Worker. The user enters the Pod bearer token in the browser;
// it is forwarded only to the pinned HTTPS Pod origin and never persisted or logged.
// Do not allow user-controlled target URLs or arbitrary proxy paths.
const POD = "https://o6ussh9yhl3r1h-8000.proxy.runpod.net";
const JOB_ID = /^[0-9a-f]{24}$/;
const MAX_IMAGE = 15 * 1024 * 1024;
function json(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {"Content-Type":"application/json; charset=utf-8", "Cache-Control":"no-store", "X-Content-Type-Options":"nosniff", "Access-Control-Allow-Origin":"none"}
  });
}
function credential(request) {
  const authorization = request.headers.get("Authorization") || "";
  return /^Bearer [\x21-\x7e]{8,512}$/.test(authorization) ? authorization : null;
}
async function requestPod(request, path, method, content) {
  const headers = {"Authorization": credential(request)};
  if (content) headers["Content-Type"] = content.type;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(POD + path, {
      method, headers,
      ...(content ? {body: content.data} : {}),
      signal: controller.signal,
      redirect: "manual"
    });
    if (response.status >= 300 && response.status < 400)
      return json(502, {error:"Unexpected upstream redirect"});
    const body = await response.text();
    if (body.length > 65536) return json(502,{error:"Unexpected upstream response size"});
    let data;
    try { data = JSON.parse(body); }
    catch { return json(502, {error:"RunPod returned a non-JSON response", http_status:response.status}); }
    return json(response.status, data);
  } catch (error) {
    return json(502, {error:"RunPod unreachable or timed out", detail: error.name === "AbortError" ? "timeout" : "connection_error"});
  } finally {
    clearTimeout(timeout);
  }
}
async function checkedJob(request, jobId) {
  const reply = await requestPod(request, "/jobs/" + jobId, "GET");
  if (reply.status !== 200) return {reply, job:null};
  const job = await reply.json();
  return {reply, job};
}
const PAGE_HEADERS = {
  "Content-Type":"text/html; charset=utf-8",
  "Cache-Control":"no-store",
  "X-Content-Type-Options":"nosniff",
  "Referrer-Policy":"no-referrer",
  "X-Frame-Options":"DENY",
  "Content-Security-Policy":"default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' blob:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
};

const HTML = "<!doctype html>\n<html lang=\"ar\" dir=\"rtl\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n<title>TRELLIS 3D Studio | RunPod</title>\n<style>\n:root{font-family:system-ui,-apple-system,\"Segoe UI\",Tahoma,sans-serif;color-scheme:dark;background:#0d1220;color:#f1f5ff}\n*{box-sizing:border-box}body{margin:0;padding:32px 18px;background:radial-gradient(circle at 85% 0%,#192c50,#0d1220 48%)}\nmain{max-width:740px;margin:0 auto}.tag{display:inline-block;color:#87d6ff;font-size:13px;letter-spacing:1px;font-weight:700}\nh1{font-size:clamp(28px,5vw,45px);margin:12px 0 6px}p{color:#b2c3db;line-height:1.8}\n.card{background:#151e30;border:1px solid #2c3d58;padding:24px;border-radius:20px;margin:20px 0;box-shadow:0 12px 40px #03081530}\nlabel{font-weight:650;display:block;margin:13px 0 9px}input{background:#0c1424;border:1px solid #465674;color:white;width:100%;padding:13px;border-radius:12px;font:inherit}\ninput[type=file]{cursor:pointer}input:focus,button:focus-visible{outline:2px solid #72d8ff;outline-offset:2px}\nbutton{background:#6cd3fd;border:none;color:#071426;border-radius:12px;padding:14px 22px;font:inherit;font-weight:800;cursor:pointer;width:100%;margin-top:18px}\nbutton:disabled{opacity:.45;cursor:not-allowed}#state{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;background:#0c1424;padding:15px;border-radius:12px;min-height:60px;border:1px solid #354662}\n.hint{font-size:13px;color:#9aafca}.bad{color:#ffb6b6}.good{color:#9affd8}\n#download{display:none;background:#a7f3d0}#preview{display:none;max-width:100%;max-height:250px;border-radius:12px;margin-top:15px}\nsmall{color:#97abc8}a{color:#8edbff}\n</style>\n</head>\n<body>\n<main>\n<span class=\"tag\">SECRET MISSION · RUNPOD</span>\n<h1>حوّل الصورة إلى مجسّم 3D</h1>\n<p>واجهة مباشرة لتجربة Microsoft TRELLIS على RTX A6000. ارفع صورة PNG أو JPG، وتابع توليد المجسّم وحفظ نسخة GLB في Cloudflare R2.</p>\n<section class=\"card\">\n<div id=\"health\" class=\"hint\" role=\"status\">جاري التحقق من اتصال RunPod…</div>\n<label for=\"key\">مفتاح TRELLIS_API_KEY الخاص بالـPod</label>\n<input id=\"key\" type=\"password\" autocomplete=\"off\" spellcheck=\"false\" placeholder=\"اكتب المفتاح هنا فقط — لن يتم حفظه\" />\n<p class=\"hint\">مهم: لا تكتب المفتاح في ChatGPT. الواجهة تستخدمه أثناء الطلب فقط ولا تحفظه في المتصفح.</p>\n<label for=\"photo\">صورة الشخصية (PNG / JPG — حتى 15MB)</label>\n<input id=\"photo\" type=\"file\" accept=\"image/png,image/jpeg\" />\n<img id=\"preview\" alt=\"معاينة الصورة المختارة\"/>\n<button id=\"generate\" type=\"button\">ابدأ توليد 3D</button>\n</section>\n<section class=\"card\">\n<label>حالة العملية</label>\n<div id=\"state\" role=\"status\" aria-live=\"polite\">في انتظار اختيار صورة ومفتاح الدخول.</div>\n<button id=\"download\" type=\"button\">تنزيل ملف GLB المحفوظ</button>\n<label for=\"recoveryJob\">استرجاع مجسّم تولّد لكن تعطل رفعه</label>\n<input id=\"recoveryJob\" type=\"text\" inputmode=\"text\" autocomplete=\"off\" spellcheck=\"false\" placeholder=\"رقم المهمة المكون من 24 حرفًا\" />\n<button id=\"recover\" type=\"button\">استرجع ملف GLB من R2 بعد إصلاح النسخ الاحتياطي</button>\n<p class=\"hint\">استرجاع الملف يحتاج نفس مفتاح Pod، ويمكن فقط بعد وجود ملف GLB محفوظ فعلاً في R2.</p>\n</section>\n<p class=\"hint\">تشغيل الـGPU مدفوع طالما الـPod يعمل. اختبار /health لا يبدأ توليدًا، لكن توليد مجسّم قد يستغرق وقتًا لتنزيل أوزان النموذج.</p>\n</main>\n<script>\n\"use strict\";\nconst key = document.getElementById(\"key\");\nconst file = document.getElementById(\"photo\");\nconst generate = document.getElementById(\"generate\");\nconst state = document.getElementById(\"state\");\nconst download = document.getElementById(\"download\");\nconst recoveryJob = document.getElementById(\"recoveryJob\");\nconst recover = document.getElementById(\"recover\");\nconst health = document.getElementById(\"health\");\nconst preview = document.getElementById(\"preview\");\nlet currentJob = null;\nlet polling = false;\nlet previewURL = null;\nconst auth = () => ({Authorization:\"Bearer \" + key.value.trim()});\nconst message = (s,good) => {state.textContent=s;state.className=good===true?\"good\":good===false?\"bad\":\"\"};\nconst wait = ms => new Promise(resolve => setTimeout(resolve,ms));\nfile.addEventListener(\"change\",()=>{\n  if(previewURL)URL.revokeObjectURL(previewURL);\n  preview.style.display=\"none\";\n  if(file.files[0] && file.files[0].type.startsWith(\"image/\")){\n    previewURL=URL.createObjectURL(file.files[0]);\n    preview.src=previewURL;\n    preview.style.display=\"block\";\n  }\n});\nasync function status(){\n  try{\n    const r=await fetch(\"/api/trellis/health\",{cache:\"no-store\"});\n    const d=await r.json();\n    health.textContent=d.gpu&&d.gpu.ready?\"● GPU جاهز: \"+d.gpu.gpu:\"● الـPod مش جاهز: \"+(d.error||d.status||\"غير متاح\");\n    health.className=d.gpu&&d.gpu.ready?\"good\":\"bad\";\n  }catch{health.textContent=\"تعذّر الاتصال بـRunPod\";health.className=\"bad\";}\n}\nstatus();\ngenerate.addEventListener(\"click\",async()=>{\n if(polling)return;\n const f=file.files[0];\n if(key.value.trim().length<8)return message(\"لازم تدخل TRELLIS_API_KEY الصحيح.\",false);\n if(!f||![\"image/png\",\"image/jpeg\"].includes(f.type)||!f.size||f.size>15*1024*1024)return message(\"اختار PNG أو JPG صالح بحجم لا يتجاوز 15MB.\",false);\n polling=true;generate.disabled=true;download.style.display=\"none\";currentJob=null;\n try{\n   message(\"جاري رفع الصورة والتحقق من المفتاح…\");\n   const r=await fetch(\"/api/trellis/generate\",{method:\"POST\",headers:{...auth(),\"Content-Type\":f.type},body:f});\n   const d=await r.json();\n   if(!r.ok)throw Error((d.error||\"فشل الطلب\")+\" (HTTP \"+r.status+\")\");\n   if(!d.job_id)throw Error(\"السيرفر لم يرجع رقم المهمة\");\n   currentJob=d.job_id;message(\"تم استلام الصورة. جارٍ توليد الموديل…\\nJob: \"+currentJob,true);\n   while(polling){\n     await wait(5000);\n     const s=await fetch(\"/api/trellis/jobs/\"+currentJob,{headers:auth(),cache:\"no-store\"});\n     const j=await s.json();\n     if(!s.ok)throw Error((j.error||\"فشل متابعة المهمة\")+\" (HTTP \"+s.status+\")\");\n     if(j.status===\"completed\"){\n       message(\"✓ تم توليد GLB، وسيرفر TRELLIS أكد التحقق من نسخة R2.\\nJob: \"+currentJob,true);\n       download.style.display=\"block\";break;\n     }\n     if(j.status===\"failed\")throw Error(j.error||\"فشل التوليد\");\n     message(\"المهمة تعمل على GPU…\\nJob: \"+currentJob+\"\\nالحالة: \"+(j.status||\"running\"));\n   }\n }catch(e){message(\"حدث خطأ: \"+e.message,false)}\n finally{polling=false;generate.disabled=false}\n});\ndownload.addEventListener(\"click\",async()=>{\n if(!currentJob)return;\n download.disabled=true;message(\"جاري التأكد من نسخة R2 وتحميل GLB…\");\n try{\n   const r=await fetch(\"/api/trellis/download/\"+currentJob,{headers:auth(),cache:\"no-store\"});\n   if(!r.ok){const d=await r.json();throw Error(d.error||\"لم يمكن تنزيل الملف\");}\n   const blob=await r.blob();const url=URL.createObjectURL(blob);\n   const a=document.createElement(\"a\");a.href=url;a.download=\"trellis-\"+currentJob+\".glb\";document.body.appendChild(a);a.click();a.remove();\n   URL.revokeObjectURL(url);message(\"✓ تم تنزيل ملف GLB المحفوظ في R2.\",true);\n }catch(e){message(\"خطأ تنزيل: \"+e.message,false)}\n finally{download.disabled=false}\n});\n\nrecover.addEventListener(\"click\",async()=>{\n const jobId=recoveryJob.value.trim();\n if(!/^[0-9a-f]{24}$/.test(jobId))return message(\"رقم المهمة يجب أن يكون 24 حرفًا من 0-9 وa-f.\",false);\n if(key.value.trim().length<8)return message(\"أدخل مفتاح TRELLIS_API_KEY الخاص بالـPod.\",false);\n recover.disabled=true;message(\"جاري البحث عن نسخة R2 لمهمة \"+jobId+\"…\");\n try{\n  const r=await fetch(\"/api/trellis/recover/\"+jobId,{headers:auth(),cache:\"no-store\"});\n  if(!r.ok){const d=await r.json();throw Error(d.error||\"الملف غير متاح\");}\n  const blob=await r.blob();const url=URL.createObjectURL(blob);\n  const a=document.createElement(\"a\");a.href=url;a.download=\"trellis-\"+jobId+\".glb\";document.body.appendChild(a);a.click();a.remove();\n  URL.revokeObjectURL(url);message(\"✓ تم استرجاع GLB من R2.\",true);\n }catch(e){message(\"تعذر الاسترجاع: \"+e.message,false)}\n finally{recover.disabled=false;}\n});\n</script>\n</body>\n</html>";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (request.method === "GET" && (path === "/" || path === "/studio"))
      return new Response(HTML, {status:200, headers:PAGE_HEADERS});
    if (request.method === "GET" && path === "/api/trellis/health") {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const r = await fetch(POD + "/health", {signal:controller.signal,redirect:"manual"});
        if (r.status === 404)
          return json(503,{error:"RunPod proxy returned 404. Check that the Pod is running and its HTTP 8000 endpoint URL is still correct.",http_status:404});
        if (r.status !== 200 && r.status !== 503)
          return json(502,{error:"RunPod health endpoint unavailable",http_status:r.status});
        const value=await r.json();
        return json(r.status,{status:value.status,gpu:value.gpu,backup_ready:value.backup_ready});
      } catch {return json(502,{error:"RunPod health check failed"});}
      finally {clearTimeout(timeout);}
    }
    if (path.startsWith("/api/trellis/")) {
      if (!credential(request)) return json(401,{error:"Valid Bearer token required"});
      if (request.method === "POST" && path === "/api/trellis/generate") {
        const type = (request.headers.get("Content-Type")||"").split(";")[0].trim().toLowerCase();
        if (!["image/png","image/jpeg"].includes(type))
          return json(415,{error:"Only PNG or JPEG images are accepted"});
        const declared = request.headers.get("Content-Length");
        const length = declared === null ? null : Number(declared);
        if (declared !== null && (!Number.isInteger(length) || length < 1 || length > MAX_IMAGE))
          return json(413,{error:"Image must be 1 to 15 MiB"});
        const data = await request.arrayBuffer();
        if (!data.byteLength || data.byteLength > MAX_IMAGE)
          return json(413,{error:"Image must be 1 to 15 MiB"});
        return requestPod(request,"/generate","POST",{type,data});
      }
      const jobMatch=path.match(/^\/api\/trellis\/jobs\/([0-9a-f]{24})$/);
      if (request.method === "GET" && jobMatch)
        return requestPod(request,"/jobs/"+jobMatch[1],"GET");
      const downloadMatch=path.match(/^\/api\/trellis\/(download|recover)\/([0-9a-f]{24})$/);
      if (request.method === "GET" && downloadMatch) {
        const recovery = downloadMatch[1] === "recover";
        const jobId=downloadMatch[2];
        const {reply,job}=await checkedJob(request,jobId);
        if (reply.status !== 200) return reply;
        if (recovery) {
          if (!["failed","completed"].includes(job?.status)) return json(409,{error:"Job has not finished generating"});
        } else if (job?.status !== "completed" || job?.backup !== "verified") {
          return json(409,{error:"TRELLIS job has no verified backup yet"});
        }
        if (!env.TRELLIS_OUTPUTS) return json(503,{error:"R2 bucket is not bound to studio"});
        const prefix="models/"+jobId+"-";
        const listing=await env.TRELLIS_OUTPUTS.list({prefix,limit:25});
        const candidates=(listing.objects||[]).filter(o=>/^models\/[0-9a-f]{24}-[0-9a-f]{16}\.glb$/.test(o.key));
        if (candidates.length !== 1) return json(404,{error:"Expected one backed-up GLB for this job",count:candidates.length});
        const file=await env.TRELLIS_OUTPUTS.get(candidates[0].key);
        if (!file) return json(404,{error:"GLB backup not found"});
        return new Response(file.body,{status:200,headers:{
          "Content-Type":"model/gltf-binary",
          "Content-Disposition":"attachment; filename=\"trellis-"+jobId+".glb\"",
          "Cache-Control":"private, no-store",
          "X-Content-Type-Options":"nosniff",
          "Content-Length":String(file.size)
        }});
      }
      return json(404,{error:"Unknown TRELLIS endpoint"});
    }
    return json(404,{error:"Not found"});
  }
};
