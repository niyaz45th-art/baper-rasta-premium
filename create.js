
import formidable from "formidable";
import fs from "node:fs/promises";
import path from "node:path";

export const config = {
  api: { bodyParser: false }
};

const API = "https://api.tripo3d.ai/v2/openapi";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({
      error: "শুধু POST অনুমোদিত"
    });
  }

  const key = process.env.TRIPO_API_KEY;

  if (!key) {
    return res.status(500).json({
      error: "TRIPO_API_KEY সেট করা নেই"
    });
  }

  let tempFile;

  try {
    const form = formidable({
      maxFiles: 1,
      maxFileSize: 10 * 1024 * 1024,
      allowEmptyFiles: false,
      minFileSize: 1
    });

    const [, files] = await form.parse(req);
    const entry = files.file;
    const file = Array.isArray(entry) ? entry[0] : entry;

    if (!file) {
      return res.status(400).json({
        error: "একটি ছবি আপলোড করো"
      });
    }

    tempFile = file.filepath;

    const allowed = {
      "image/jpeg": "jpg",
      "image/png": "png",
      "image/webp": "webp"
    };

    const extension = allowed[file.mimetype];

    if (!extension) {
      return res.status(400).json({
        error: "শুধু JPG, PNG অথবা WEBP ছবি গ্রহণ করা হয়"
      });
    }

    const bytes = await fs.readFile(file.filepath);
    const uploadForm = new FormData();

    uploadForm.append(
      "file",
      new Blob([bytes], { type: file.mimetype }),
      path.basename(
        file.originalFilename || `bus.${extension}`
      )
    );

    // Step 1: Upload image
    const uploadResponse = await fetch(
      `${API}/upload`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`
        },
        body: uploadForm,
        signal: AbortSignal.timeout(45000)
      }
    );

    const uploadData = await uploadResponse
      .json()
      .catch(() => ({}));

    if (!uploadResponse.ok || uploadData.code !== 0) {
      console.error("Tripo upload error:", uploadData);

      return res.status(502).json({
        error: "Tripo-তে ছবি আপলোড ব্যর্থ হয়েছে"
      });
    }

    const imageToken = uploadData.data?.image_token;

    if (!imageToken) {
      return res.status(502).json({
        error: "Tripo image token পাওয়া যায়নি"
      });
    }

    // Step 2: Create 3D task
    const taskResponse = await fetch(
      `${API}/task`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          type: "image_to_model",
          file: {
            type: extension,
            file_token: imageToken
          },
          texture: true,
          pbr: true
        }),
        signal: AbortSignal.timeout(45000)
      }
    );

    const taskData = await taskResponse
      .json()
      .catch(() => ({}));

    if (
      !taskResponse.ok ||
      taskData.code !== 0 ||
      !taskData.data?.task_id
    ) {
      console.error("Tripo task error:", taskData);

      return res.status(502).json({
        error: "3D মডেল তৈরির Task শুরু করা যায়নি"
      });
    }

    return res.status(200).json(taskData);

  } catch (error) {
    console.error("create.js error:", error);

    return res.status(500).json({
      error: "সার্ভারে সমস্যা হয়েছে। আবার চেষ্টা করো।"
    });

  } finally {
    if (tempFile) {
      await fs.unlink(tempFile).catch(() => {});
    }
  }
}
