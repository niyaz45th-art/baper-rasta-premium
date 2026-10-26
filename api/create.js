import formidable from "formidable";
import fs from "fs";
export const config = { api: { bodyParser: false } };
export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();
  const TRIPO_KEY = "tsk_gqHJPWaDtKEPkM95ce0HXrovBVcmPZgKohhk6peMzUS";
  try {
    const form = formidable({});
    const [fields, files] = await form.parse(req);
    const file = files.file?.[0];
    if (!file) return res.status(400).json({ error: "No file" });
    const fileBuffer = fs.readFileSync(file.filepath);
    const blob = new Blob([fileBuffer], { type: file.mimetype || "image/png" });
    const fd = new FormData();
    fd.append("type", "image_to_model");
    fd.append("file", blob, file.originalFilename || "bus.png");
    let r = await fetch("https://api.tripo3d.ai/v2/openapi/task", {
      method: "POST",
      headers: { "Authorization": `Bearer ${TRIPO_KEY}` },
      body: fd
    });
    let data = await r.json();
    return res.status(r.status).json(data);
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
