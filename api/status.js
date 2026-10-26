export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();
  const TRIPO_KEY = "tsk_gqHJPWaDtKEPkM95ce0HXrovBVcmPZgKohhk6peMzUS";
  const { taskId } = req.query;
  if (!taskId) return res.status(400).json({ error: "taskId required" });
  try {
    let r = await fetch(`https://api.tripo3d.ai/v2/openapi/task/${taskId}`, {
      headers: { "Authorization": `Bearer ${TRIPO_KEY}` }
    });
    let data = await r.json();
    return res.status(r.status).json(data);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
