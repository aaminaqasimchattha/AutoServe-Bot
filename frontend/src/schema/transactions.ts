import { pgTable, serial, text, varchar, timestamp } from 'drizzle-orm/pg-core';
import { customers } from './customers';

export const transactions = pgTable('transaction_data', {
  id: serial('id').primaryKey(),
  transaction_id: varchar('transaction_id', { length: 128 }),
  sender_name: text('sender_name'),
  receiver_name: text('receiver_name'),
  amount: text('amount'),
  date: text('date'),
  time: text('time'),
  bank_or_service: text('bank_or_service'),
  status: text('status'),
  raw_text: text('raw_text'),
  // FK → customers.phone_number  (nullable for rows saved before customer tracking was added)
  sender_number: text('sender_number').references(() => customers.phone_number, { onDelete: 'set null' }),
  created_at: timestamp('created_at').notNull().defaultNow(),
});

export type Transactions = typeof transactions;

