import { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Send, RefreshCw, Database } from 'lucide-react';

import type { AppDispatch, RootState } from '../store';
import {
  createComplaint,
  resetForm,
  setFieldLocally,
  commitComplaint,
  patchComplaint,
} from '../store/complaintFormSlice';
import { resetChat, addUserMessage } from '../store/copilotChatSlice';

import SectionCard from '../components/SectionCard';
import { TextField, SelectField, DateField, QuantityField } from '../components/FormFields';
import StatusBadge from '../components/StatusBadge';
import ChatBubble from '../components/ChatBubble';
import Dropzone from '../components/Dropzone';
import PasteTextModal from '../components/PasteTextModal';
import ProgressBar from '../components/ProgressBar';
import AIAssessmentCard from '../components/AIAssessmentCard';

import './ComplaintPage.css';

const COMPLAINT_SOURCE_OPTIONS = [
  { value: 'Pharmacy', label: 'Pharmacy' },
  { value: 'Email', label: 'Email' },
  { value: 'Distributor', label: 'Distributor' },
  { value: 'Phone', label: 'Phone' },
  { value: 'Portal', label: 'Portal' },
  { value: 'Other', label: 'Other' },
];

const CATEGORY_OPTIONS = [
  { value: 'Contamination', label: 'Contamination' },
  { value: 'Discoloration', label: 'Discoloration' },
  { value: 'Packaging', label: 'Packaging' },
  { value: 'Labeling', label: 'Labeling' },
  { value: 'Efficacy', label: 'Efficacy' },
  { value: 'Sterility', label: 'Sterility' },
  { value: 'Foreign Matter', label: 'Foreign Matter' },
  { value: 'Other', label: 'Other' },
];

export default function ComplaintPage() {
  const dispatch = useDispatch<AppDispatch>();
  const { current: complaint, loading, committing, justFilledFields } = useSelector(
    (s: RootState) => s.complaintForm
  );
  const { messages, extractionStatus, extractionProgress, extractionStatusLabel, isProcessing } =
    useSelector((s: RootState) => s.copilotChat);

  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Initialize a new draft complaint on mount
  useEffect(() => {
    dispatch(createComplaint());
  }, [dispatch]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isCommitted = complaint?.status === 'committed';
  const isDisabled = isCommitted || loading;

  const handleFieldChange = (field: string, value: string) => {
    if (!complaint || isDisabled) return;
    dispatch(setFieldLocally({ field: field as any, value }));
    // Debounced save handled in a custom hook (future enhancement)
  };

  const handleFieldBlur = (field: string) => {
    if (!complaint || isDisabled) return;
    dispatch(patchComplaint({ id: complaint.id, updates: { [field]: (complaint as any)[field] } }));
  };

  const handlePasteText = (text: string) => {
    // Phase 3: will call /copilot/ingest — for now logs intent
    dispatch(addUserMessage(`[Paste] ${text.slice(0, 120)}…`));
    console.log('[Phase 3] Will send to /copilot/ingest:', text);
  };

  const handleFileDrop = (file: File) => {
    setActiveFile(file);
    // Phase 4: will POST multipart/form-data to /copilot/ingest
    console.log('[Phase 4] Will upload file:', file.name);
  };

  const handleSendChat = () => {
    if (!chatInput.trim() || !complaint || isCommitted) return;
    dispatch(addUserMessage(chatInput.trim()));
    setChatInput('');
    // Phase 5: will call /copilot/chat
    console.log('[Phase 5] Will send chat correction:', chatInput);
  };

  const handleCommit = async () => {
    if (!complaint) return;
    await dispatch(commitComplaint(complaint.id));
  };

  const handleReset = () => {
    dispatch(resetForm());
    dispatch(resetChat());
    setActiveFile(null);
    setShowResetConfirm(false);
    dispatch(createComplaint());
  };

  if (loading && !complaint) {
    return (
      <div className="page-loading">
        <div className="page-loading__spinner" />
        <p className="text-body">Initializing complaint session…</p>
      </div>
    );
  }

  return (
    <div className="complaint-page">
      {/* ── Left pane: Form ─────────────────────────────────────────────────── */}
      <main className="complaint-page__form-pane" aria-label="Complaint form">
        {/* Header */}
        <div className="form-header">
          <div className="form-header__title-group">
            <h1 className="text-h1">Log Customer Complaint</h1>
            <p className="text-small form-header__subtitle">API &amp; FDF Quality Assurance Module</p>
          </div>
          {complaint && <StatusBadge status={complaint.status} />}
        </div>

        <div className="form-header__divider" />

        {/* ID display */}
        {complaint && (
          <p className="form-id text-small">
            <span className="form-id__label">Complaint ID</span>
            <span className="form-id__value">{complaint.id}</span>
          </p>
        )}

        {/* Section 1: Origin & Customer Details */}
        <SectionCard number={1} title="Origin & Customer Details">
          <SelectField
            id="complaint_source"
            label="Complaint Source"
            value={complaint?.complaint_source ?? null}
            options={COMPLAINT_SOURCE_OPTIONS}
            onChange={(v) => handleFieldChange('complaint_source', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('complaint_source')}
          />
          <TextField
            id="customer_name"
            label="Customer Name"
            value={complaint?.customer_name ?? null}
            onChange={(v) => handleFieldChange('customer_name', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('customer_name')}
          />
        </SectionCard>

        {/* Section 2: Product & Batch Identification */}
        <SectionCard number={2} title="Product & Batch Identification">
          <TextField
            id="product_name"
            label="Product Name"
            value={complaint?.product_name ?? null}
            onChange={(v) => handleFieldChange('product_name', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('product_name')}
          />
          <TextField
            id="product_strength_grade"
            label="Product Strength / Grade"
            value={complaint?.product_strength_grade ?? null}
            onChange={(v) => handleFieldChange('product_strength_grade', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('product_strength_grade')}
          />
          <TextField
            id="batch_lot_number"
            label="Batch / Lot Number"
            value={complaint?.batch_lot_number ?? null}
            onChange={(v) => handleFieldChange('batch_lot_number', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('batch_lot_number')}
          />
          <DateField
            id="manufacturing_date"
            label="Manufacturing Date"
            value={complaint?.manufacturing_date ?? null}
            onChange={(v) => handleFieldChange('manufacturing_date', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('manufacturing_date')}
          />
          <DateField
            id="expiry_date"
            label="Expiry Date"
            value={complaint?.expiry_date ?? null}
            onChange={(v) => handleFieldChange('expiry_date', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('expiry_date')}
          />
          <QuantityField
            id="affected_quantity"
            label="Quantity Affected"
            value={complaint?.affected_quantity ?? null}
            onChange={(v) => handleFieldChange('affected_quantity', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('affected_quantity')}
          />
        </SectionCard>

        {/* Section 3: Complaint Details */}
        <SectionCard number={3} title="Complaint Details">
          <SelectField
            id="complaint_category"
            label="Complaint Type"
            value={complaint?.complaint_category ?? null}
            options={CATEGORY_OPTIONS}
            onChange={(v) => handleFieldChange('complaint_category', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('complaint_category')}
          />
          <DateField
            id="complaint_date"
            label="Complaint Date"
            value={complaint?.complaint_date ?? null}
            onChange={(v) => handleFieldChange('complaint_date', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('complaint_date')}
          />
          <TextField
            id="originating_site_block"
            label="Originating Site / Block"
            value={complaint?.originating_site_block ?? null}
            onChange={(v) => handleFieldChange('originating_site_block', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('originating_site_block')}
          />
          <TextField
            id="impacted_npm"
            label="Impacted Non-Product Materials"
            value={complaint?.impacted_npm ?? null}
            onChange={(v) => handleFieldChange('impacted_npm', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('impacted_npm')}
          />
          <TextField
            id="complaint_description"
            label="Detailed Complaint Description"
            value={complaint?.complaint_description ?? null}
            onChange={(v) => handleFieldChange('complaint_description', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('complaint_description')}
            multiline
            rows={5}
            className="full-width"
          />
        </SectionCard>

        {/* Section 4: Initial Assessment & Priority */}
        <SectionCard number={4} title="Initial Assessment & Priority">
          <SelectField
            id="severity_suggested"
            label="Initial Severity"
            value={complaint?.severity_suggested ?? null}
            options={[
              { value: 'Critical', label: 'Critical' },
              { value: 'Major', label: 'Major' },
              { value: 'Minor', label: 'Minor' },
              { value: 'Not Assessed', label: 'Not Assessed' },
            ]}
            onChange={(v) => handleFieldChange('severity_suggested', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('severity_suggested')}
          />
          <SelectField
            id="priority"
            label="Priority"
            value={complaint?.priority ?? null}
            options={[
              { value: 'High', label: 'High' },
              { value: 'Medium', label: 'Medium' },
              { value: 'Low', label: 'Low' },
              { value: 'Not Assessed', label: 'Not Assessed' },
            ]}
            onChange={(v) => handleFieldChange('priority', v)}
            disabled={isDisabled}
            aiJustFilled={justFilledFields.has('priority')}
          />

          {/* AI Assessment sub-panel */}
          {complaint && (
            <div className="full-width">
              <AIAssessmentCard
                severity={complaint.severity_suggested}
                nextAction={complaint.suggested_next_action}
                riskAssessment={complaint.initial_risk_assessment}
                onSeverityChange={(v) => handleFieldChange('severity_suggested', v)}
                disabled={isDisabled}
              />
            </div>
          )}
        </SectionCard>

        {/* ── Committed state info ─────────────────────────────────────────── */}
        {isCommitted && complaint?.committed_at && (
          <div className="committed-banner">
            <Database size={16} />
            Committed on{' '}
            {new Date(complaint.committed_at).toLocaleString('en-IN', {
              dateStyle: 'medium',
              timeStyle: 'short',
            })}
          </div>
        )}

        {/* ── Action buttons ───────────────────────────────────────────────── */}
        <div className="form-actions">
          {!isCommitted && (
            <>
              <button
                className="btn-secondary form-actions__reset"
                onClick={() => setShowResetConfirm(true)}
                id="reset-form-btn"
              >
                <RefreshCw size={14} />
                Reset Form
              </button>
              <button
                className="btn-commit"
                onClick={handleCommit}
                disabled={committing || !complaint}
                id="commit-btn"
              >
                <Database size={16} />
                {committing ? 'Committing…' : 'Commit to QMS Ledger'}
              </button>
            </>
          )}
        </div>
      </main>

      {/* ── Right pane: AI Copilot ────────────────────────────────────────────── */}
      <aside className="complaint-page__copilot-pane" aria-label="AI Complaint Intake Assistant">
        {/* Copilot header */}
        <div className="copilot-header">
          <div className="copilot-header__title-group">
            <span className="copilot-header__icon" aria-hidden="true">✦</span>
            <h2 className="text-h2">AI Complaint Intake Assistant</h2>
          </div>
          <span className="beta-badge">BETA</span>
        </div>

        <div className="copilot-body">
          {/* File dropzone */}
          <Dropzone
            onFileDrop={handleFileDrop}
            activeFile={activeFile}
            onClearFile={() => setActiveFile(null)}
            disabled={isDisabled}
          />

          {/* OR divider */}
          <div className="or-divider">OR</div>

          {/* Paste text button */}
          <PasteTextModal onSubmit={handlePasteText} disabled={isDisabled} />

          {/* Supported formats info */}
          <div className="format-info-box">
            <span className="format-info-box__icon" aria-hidden="true">ℹ</span>
            <span className="text-small">
              Supported formats: <strong>PDF, DOCX, TXT, EML</strong> — Max file size: 10MB
            </span>
          </div>

          {/* Extraction progress */}
          <ProgressBar
            visible={extractionStatus !== 'idle'}
            progress={extractionProgress}
            label={extractionStatusLabel}
          />

          {/* Chat section label */}
          <p className="text-section-label">AI Assistant</p>

          {/* Chat messages */}
          <div className="chat-thread" aria-live="polite" aria-label="Chat thread">
            {messages.map((msg) => (
              <ChatBubble key={msg.id} message={msg} />
            ))}
            {isProcessing && (
              <div className="chat-typing fade-in-up">
                <span /><span /><span />
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Chat input */}
        <div className="copilot-footer">
          {isCommitted ? (
            <p className="copilot-footer__locked text-small">
              🔒 This complaint has been committed to the QMS ledger.
            </p>
          ) : (
            <div className="chat-input-row">
              <input
                type="text"
                className="chat-input"
                placeholder="Ask me anything about this complaint…"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendChat()}
                disabled={isDisabled || isProcessing}
                aria-label="Chat input"
                id="chat-input"
              />
              <button
                className="chat-send-btn"
                onClick={handleSendChat}
                disabled={!chatInput.trim() || isDisabled || isProcessing}
                aria-label="Send message"
                id="chat-send-btn"
              >
                <Send size={16} />
              </button>
            </div>
          )}
          <p className="ai-disclaimer text-small">
            AI responses may contain errors. Please verify information.
          </p>
        </div>
      </aside>

      {/* ── Reset confirmation dialog ──────────────────────────────────────── */}
      {showResetConfirm && (
        <div className="paste-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="reset-dialog-title">
          <div className="paste-modal" style={{ maxWidth: 400 }}>
            <div className="paste-modal__header">
              <h2 id="reset-dialog-title" className="text-h2">Reset Form?</h2>
            </div>
            <div className="paste-modal__body">
              <p className="text-body">
                This will clear all extracted data, reset the status to Pending Triage, and clear the chat history.
                This action cannot be undone.
              </p>
            </div>
            <div className="paste-modal__footer">
              <button className="btn-secondary" onClick={() => setShowResetConfirm(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleReset} id="reset-confirm-btn" style={{ background: '#DC2626' }}>
                Yes, Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
