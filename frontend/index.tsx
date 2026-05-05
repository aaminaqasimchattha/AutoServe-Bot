import { drizzle } from 'drizzle-orm/postgres-js'
import { sql } from 'drizzle-orm'
import postgres from 'postgres'

const connectionString = process.env.DATABASE_URL

// Disable prefetch as it is not supported for "Transaction" pool mode
const client = postgres(connectionString as string, { prepare: false })
const db = drizzle(client)

async function main() {
  const allUsers = await db.execute(sql`select * from users`)
  console.log('users:', allUsers)
}

main().catch((err) => console.error(err))

export {}
