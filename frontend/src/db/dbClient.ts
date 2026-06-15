import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { config } from "dotenv";
import path from "node:path";
import fs from "node:fs";

const envCandidates = [
  path.resolve(__dirname, "../../.env"),
  path.resolve(__dirname, "../../../.env"),
];

for (const envPath of envCandidates) {
  config({ path: envPath, override: true });
}

const loadedEnvFiles = envCandidates.filter((envPath) => fs.existsSync(envPath));
const dbUri = process.env.DB_URI || process.env.DATABASE_URL;

console.info(
  `Frontend DB env check: loaded=${dbUri ? "yes" : "no"}, files=${loadedEnvFiles.length ? loadedEnvFiles.join(", ") : "none"}`
);

// 🧠 Global cache to ensure single instance (for hot reloads / multiple imports)
const globalForDb = global as unknown as {
  pool?: Pool;
  db?: ReturnType<typeof drizzle>;
  hasPinged?: boolean;
};

// 🧩 Create pool only once
if (!globalForDb.pool) {
  if (!dbUri) {
    console.warn(
      `No database URL configured. Checked: ${envCandidates.join(", ")}. Set DB_URI or DATABASE_URL for the frontend API.`
    );
  }

  globalForDb.pool = new Pool({
    connectionString: dbUri,
  });
}

// 🧩 Create drizzle instance only once
if (!globalForDb.db) {
  globalForDb.db = drizzle(globalForDb.pool);
}

// 🧠 Ping DB only once when app starts (first import)
async function pingDatabaseOnce() {
  if (globalForDb.hasPinged) return; // ✅ already done

  try {
    const client = await globalForDb.pool!.connect();
    const res = await client.query("SELECT NOW()");
    client.release();

    globalForDb.hasPinged = true;
  } catch (error: any) {
    console.error(`Database connection failed: ${error.message}\n`);

    // Optional: Stop the app if DB is critical
    process.exit(1);
  }
}

pingDatabaseOnce();

export const db = globalForDb.db!;
