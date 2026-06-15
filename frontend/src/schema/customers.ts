import { pgTable, serial, text, varchar, integer, timestamp } from 'drizzle-orm/pg-core';

export const customers = pgTable('customers', {
  id: serial('id').primaryKey(),
  phone_number: varchar('phone_number', { length: 32 }).notNull().unique(),
  name: text('name'),
  first_seen: timestamp('first_seen').notNull().defaultNow(),
  last_seen: timestamp('last_seen').notNull().defaultNow(),
  message_count: integer('message_count').notNull().default(1),
  last_message: text('last_message'),
  last_order_id: varchar('last_order_id', { length: 64 }),
  last_order_status: varchar('last_order_status', { length: 32 }),
  last_transaction_ref: varchar('last_transaction_ref', { length: 128 }),
  notes: text('notes'),
  email: text('email'),
  cnic: text('cnic'),
  created_at: timestamp('created_at').notNull().defaultNow(),
});

export type Customers = typeof customers;
