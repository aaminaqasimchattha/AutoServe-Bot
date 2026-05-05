import { pgTable, serial, text, varchar, timestamp } from 'drizzle-orm/pg-core';

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
  sender_number: text('sender_number'),
  created_at: timestamp('created_at').notNull().defaultNow(),
});

export type Transactions = typeof transactions;
