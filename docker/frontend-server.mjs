import { createReadStream, existsSync } from "node:fs";
import { promises as fs } from "node:fs";
import http from "node:http";
import path from "node:path";

const host = process.env.FRONTEND_HOST ?? "0.0.0.0";
const port = Number.parseInt(process.env.FRONTEND_PORT ?? "4173", 10);
const distRoot = "/app/frontend/dist";

const MIME_TYPES = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function resolvePath(urlPath) {
  const normalized = path.posix.normalize(urlPath);
  const relativePath = normalized.replace(/^(\.\.(\/|\\|$))+/, "").replace(/^\/+/, "");
  return path.join(distRoot, relativePath);
}

async function sendFile(res, filePath) {
  const extension = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[extension] ?? "application/octet-stream";
  const stat = await fs.stat(filePath);
  res.writeHead(200, {
    "Content-Length": stat.size,
    "Content-Type": contentType,
    ...(path.basename(filePath) === "runtime-config.js" ? { "Cache-Control": "no-store" } : {}),
  });
  createReadStream(filePath).pipe(res);
}

const server = http.createServer(async (req, res) => {
  try {
    const requestUrl = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
    const requestedPath = resolvePath(requestUrl.pathname);
    const indexPath = path.join(distRoot, "index.html");

    if (existsSync(requestedPath)) {
      const stat = await fs.stat(requestedPath);
      if (stat.isFile()) {
        await sendFile(res, requestedPath);
        return;
      }
      const nestedIndexPath = path.join(requestedPath, "index.html");
      if (existsSync(nestedIndexPath)) {
        await sendFile(res, nestedIndexPath);
        return;
      }
    }

    await sendFile(res, indexPath);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(`frontend server error: ${message}\n`);
  }
});

server.listen(port, host, () => {
  console.log(`frontend: serving static files on http://${host}:${port}`);
});
