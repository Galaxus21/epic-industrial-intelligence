/**
 * AI Operations Brain — Integrations API helpers (types + fetchers)
 */

export interface IntegrationSetupField {
  key: string;
  label: string;
  placeholder: string;
  env: string;
  secret?: boolean;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  status: "connected" | "active" | "configure" | "error";
  item_count: number;
  action_required: number;
  last_sync: string | null;
  webhook_url?: string;
  setup_fields: IntegrationSetupField[];
  tags: string[];
}

export interface FeedItem {
  id: string;
  source: string;
  source_label: string;
  icon: string;
  color: string;
  from: string;
  title: string;
  preview: string;
  equipment: string[];
  action_required: boolean;
  severity: "High" | "Medium" | "Low" | "Info";
  timestamp: string;
  channel: string;
  has_ai_reply?: boolean;
}

export interface EmailMessage {
  id: string;
  from: string;
  subject: string;
  date: string;
  body: string;
  equipment_mentions: string[];
  action_required: boolean;
  ingested_at: string;
}

export interface SlackMessage {
  id: string;
  channel: string;
  user_display: string;
  user_avatar: string;
  text: string;
  timestamp: string;
  thread_replies: { user: string; text: string; timestamp: string }[];
  equipment_mentions: string[];
  action_required: boolean;
  severity: string;
  has_ai_reply?: boolean;
}
