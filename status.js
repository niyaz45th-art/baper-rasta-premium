
const API = "https://api.tripo3d.ai/v2/openapi";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");

    return res.status(405).json({
      error: "শুধু GET অনুমোদিত"
    });
  }

  const key = process.env.TRIPO_API_KEY;

  if (!key) {
    return res.status(500).json({
      error: "TRIPO_API_KEY সেট করা নেই"
    });
  }

  const taskId = req.query?.taskId;

  if (
    typeof taskId !== "string" ||
    !/^[a-zA-Z0-9_-]+$/.test(taskId)
  ) {
    return res.status(400).json({
      error: "সঠিক taskId দিতে হবে"
    });
  }

  try {
    const response = await fetch(
      `${API}/task/${encodeURIComponent(taskId)}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${key}`
        },
        signal: AbortSignal.timeout(20000)
      }
    );

    const result = await response
      .json()
      .catch(() => ({}));

    if (!response.ok || result.code !== 0) {
      console.error("Tripo status error:", result);

      return res.status(502).json({
        error: "Tripo থেকে Task Status পাওয়া যায়নি"
      });
    }

    const task = result.data || {};
    const output = task.output || {};

    const modelUrl =
      output.model ||
      output.pbr_model ||
      output.model_url ||
      output.base_model ||
      null;

    return res.status(200).json({
      ...result,
      data: {
        ...task,
        output: {
          ...output,
          model: modelUrl
        }
      }
    });

  } catch (error) {
    console.error("status.js error:", error);

    return res.status(500).json({
      error: "Status পরীক্ষা করতে সমস্যা হয়েছে"
    });
  }
}
