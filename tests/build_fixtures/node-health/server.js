// Minimal stdlib health-check app — a build-loop test fixture, not an example.
// No npm dependencies, so the container build needs no package index.
// Binds 0.0.0.0 so the platform's port mapping can reach it.
const http = require("http");

const PORT = 3000;

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
  } else if (req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("node-health is running on Causeway.\n");
  } else {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("not found\n");
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`node-health listening on 0.0.0.0:${PORT}`);
});
