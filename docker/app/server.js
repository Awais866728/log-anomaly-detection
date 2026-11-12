const express = require("express");
const { Pool } = require("pg");

const pool = new Pool(); // reads PGHOST, PGUSER, PGPASSWORD, PGDATABASE from the environment
const app = express();
app.use(express.json());

function log(level, message) {
  const line = `${new Date().toISOString()} ${level} ${message}`;
  if (level === "ERROR") console.error(line);
  else console.log(line);
}

// one line per request, written when the response is finished
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    const ip = req.headers["x-real-ip"] || req.socket.remoteAddress;
    log("INFO", `${ip} ${req.method} ${req.originalUrl} ${res.statusCode} ${Date.now() - start}ms`);
  });
  next();
});

app.get("/", (req, res) => res.json({ status: "ok" }));

app.get("/items", async (req, res, next) => {
  try {
    const { rows } = await pool.query("SELECT id, name, created_at FROM items ORDER BY id DESC LIMIT 50");
    res.json(rows);
  } catch (err) {
    next(err);
  }
});

app.post("/items", async (req, res, next) => {
  const name = req.body && req.body.name;
  if (typeof name !== "string" || name.trim() === "" || name.length > 100) {
    return res.status(400).json({ error: "name must be a non-empty string of at most 100 characters" });
  }
  try {
    const { rows } = await pool.query(
      "INSERT INTO items (name) VALUES ($1) RETURNING id, name, created_at",
      [name.trim()]
    );
    res.status(201).json(rows[0]);
  } catch (err) {
    next(err);
  }
});

app.use((err, req, res, next) => {
  log("ERROR", `${req.method} ${req.originalUrl} ${err.message}`);
  res.status(500).json({ error: "internal error" });
});

async function start() {
  // Postgres may still be starting, so retry a few times
  for (let attempt = 1; ; attempt++) {
    try {
      await pool.query(
        "CREATE TABLE IF NOT EXISTS items (id SERIAL PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now())"
      );
      break;
    } catch (err) {
      log("ERROR", `database not ready (attempt ${attempt}): ${err.message}`);
      if (attempt === 10) process.exit(1);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
  log("INFO", "table items ready");
  app.listen(3000, () => log("INFO", "app listening on port 3000"));
}

pool.on("error", (err) => log("ERROR", `database connection error: ${err.message}`));
start();
