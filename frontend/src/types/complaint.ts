// ── Complaint domain types mirroring the backend Pydantic schemas ─────────────

export type ComplaintStatus = 'pending_triage' | 'ready_to_commit' | 'committed';
export type SeverityLevel = 'Critical' | 'Major' | 'Minor' | 'Not Assessed';
export type PriorityLevel = 'High' | 'Medium' | 'Low' | 'Not Assessed';
export type ChatRole = 'user' | 'assistant';

export interface Complaint {
  id: string;
  status: ComplaintStatus;
  // Section 1
  complaint_source: string | null;
  customer_name: string | null;
  // Section 2
  product_name: string | null;
  product_strength_grade: string | null;
  batch_lot_number: string | null;
  manufacturing_date: string | null;
  expiry_date: string | null;
  affected_quantity: string | null;
  // Section 3
  originating_site_block: string | null;
  impacted_npm: string | null;
  complaint_category: string | null;
  complaint_date: string | null;
  complaint_description: string | null;
  // Section 4
  severity_suggested: SeverityLevel | null;
  severity_final: SeverityLevel | null;
  priority: PriorityLevel | null;
  suggested_next_action: string | null;
  initial_risk_assessment: string | null;
  // Meta
  raw_source_text: string | null;
  raw_source_file_path: string | null;
  // Phase 6 bonus fields
  complaint_summary: string | null;
  capa_recommendation: string | null;
  created_at: string | null;
  updated_at: string | null;
  committed_at: string | null;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  created_at: string;
}

export interface AuditLog {
  id: string;
  complaint_id: string;
  actor: 'ai' | 'user';
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  source_message: string | null;
  created_at: string;
}

export type ExtractionStatus =
  | 'idle'
  | 'uploading'
  | 'extracting'
  | 'validating'
  | 'assessing'
  | 'processing'
  | 'complete'
  | 'error';
