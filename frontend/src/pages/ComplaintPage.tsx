import { useEffect, useRef, useState, useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Send, RefreshCw, Database, AlertCircle, Sparkles, AlertTriangle, X } from "lucide-react";

import type { AppDispatch, RootState } from "../store";
import {
  createComplaint,
  restoreOrInitComplaint,
  resetForm,
  setFieldLocally,
  setFieldTouched,
  validateForm,
  commitComplaint,
  patchComplaint,
  applyAIExtraction,
  clearFilledFields,
  clearFormError,
} from "../store/complaintFormSlice";
import {
  resetChat,
  addUserMessage,
  addAssistantMessage,
  restoreChatForComplaint,
  setExtractionStatus,
  setProcessing,
  sendChatMessage,
} from "../store/copilotChatSlice";

import SectionCard from "../components/SectionCard";
import {
  TextField,
  SelectField,
  DateField,
  QuantityField,
} from "../components/FormFields";
import StatusBadge from "../components/StatusBadge";
import ChatBubble from "../components/ChatBubble";
import Dropzone from "../components/Dropzone";
import PasteTextModal from "../components/PasteTextModal";
import ProgressBar from "../components/ProgressBar";
import AIAssessmentCard from "../components/AIAssessmentCard";
import SubmitChecklist from "../components/SubmitChecklist";
import CAPARecommendationCard from "../components/CAPARecommendationCard";
import DuplicateAlertCard from "../components/DuplicateAlertCard";
import ChatSkeleton from "../components/ChatSkeleton";
import { evaluateCompleteness } from "../utils/validation";

import "./ComplaintPage.css";

const COMPLAINT_SOURCE_OPTIONS = [
  { value: "Pharmacy", label: "Pharmacy" },
  { value: "Email", label: "Email" },
  { value: "Distributor", label: "Distributor" },
  { value: "Phone", label: "Phone" },
  { value: "Portal", label: "Portal" },
  { value: "Other", label: "Other" },
];

const CATEGORY_OPTIONS = [
  { value: "Discoloration", label: "Discoloration" },
  {
    value: "Foreign Matter / Contamination",
    label: "Foreign Matter / Contamination",
  },
  { value: "Packaging Defect", label: "Packaging Defect" },
  { value: "Labeling Defect", label: "Labeling Defect" },
  { value: "Subpotency / Efficacy", label: "Subpotency / Efficacy" },
  { value: "Dissolution / Physical", label: "Dissolution / Physical" },
  { value: "Sterility", label: "Sterility" },
  { value: "Adverse Event", label: "Adverse Event" },
  { value: "Damaged Goods", label: "Damaged Goods" },
  { value: "Other", label: "Other" },
];

export default function ComplaintPage() {
  const dispatch = useDispatch<AppDispatch>();
  const {
    current: complaint,
    loading,
    committing,
    justFilledFields,
    validationErrors,
    touchedFields,
    error: serverError,
  } = useSelector((s: RootState) => s.complaintForm);

  const {
    messages,
    extractionStatus,
    extractionProgress,
    extractionStatusLabel,
    isProcessing,
    isRestoringChat,
  } = useSelector((s: RootState) => s.copilotChat);

  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [commitErrorAlert, setCommitErrorAlert] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const saveTimeoutRef = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );

  // ── Session Restoration & Initialization ─────────────────────────────────────
  useEffect(() => {
    dispatch(restoreOrInitComplaint());
  }, [dispatch]);

  // Restore chat messages for active complaint session
  useEffect(() => {
    if (complaint?.id) {
      dispatch(restoreChatForComplaint(complaint.id));
    }
  }, [complaint?.id, dispatch]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isCommitted = complaint?.status === "committed";
  const isExtracting = isProcessing || extractionStatus === "processing";
  const isDisabled = isCommitted || loading || isExtracting;

  // ── Debounced Field Handlers ────────────────────────────────────────────────
  const handleFieldChange = (field: string, value: string) => {
    if (!complaint || isDisabled) return;
    dispatch(setFieldLocally({ field: field as any, value }));
    setCommitErrorAlert(null);

    // Debounce save to backend (600ms)
    if (saveTimeoutRef.current[field]) {
      clearTimeout(saveTimeoutRef.current[field]);
    }
    saveTimeoutRef.current[field] = setTimeout(() => {
      dispatch(
        patchComplaint({ id: complaint.id, updates: { [field]: value } }),
      );
    }, 600);
  };

  const handleFieldBlur = (field: string) => {
    if (!complaint || isDisabled) return;
    dispatch(setFieldTouched(field));

    // Force flush pending debounced save
    if (saveTimeoutRef.current[field]) {
      clearTimeout(saveTimeoutRef.current[field]);
    }
    const val = (complaint as any)[field];
    dispatch(patchComplaint({ id: complaint.id, updates: { [field]: val } }));
  };

  const handleFocusField = useCallback((fieldId: string) => {
    const el = document.getElementById(fieldId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.focus();
    }
  }, []);

  // ── Ingest & Chat Handlers ──────────────────────────────────────────────────
  const handlePasteText = async (text: string) => {
    if (!complaint) return;
    dispatch(
      addUserMessage({
        message: `[Intake Text Submitted]: "${text.slice(0, 90)}..."`,
        complaintId: complaint.id,
      }),
    );
    dispatch(setProcessing(true));
    dispatch(
      setExtractionStatus({
        status: "uploading",
        progress: 10,
        label: "Initiating ComplaintIQ intake pipeline...",
      }),
    );

    try {
      const baseUrl =
        import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/copilot/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({
          text,
          complaint_id: complaint.id,
        }),
      });

      if (!response.ok) {
        let errMsg = `Server returned HTTP ${response.status}`;
        try {
          const errData = await response.json();
          if (errData?.detail) {
            errMsg =
              typeof errData.detail === "string"
                ? errData.detail
                : JSON.stringify(errData.detail);
          }
        } catch {
          // fallback to status code message
        }
        throw new Error(errMsg);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
              const dataStr = trimmed.slice(5).trim();
              if (!dataStr) continue;
              try {
                const event = JSON.parse(dataStr);
                const progress = event.progress ?? 50;
                const message = event.status_message ?? "";
                const step = event.step ?? "";

                if (
                  step === "risk_assessor" ||
                  progress === 100 ||
                  event.complaint
                ) {
                  dispatch(
                    setExtractionStatus({
                      status: "complete",
                      progress: 100,
                      label: message || "Extraction complete.",
                    }),
                  );
                  if (event.complaint) {
                    dispatch(applyAIExtraction(event.complaint));
                    setTimeout(() => {
                      dispatch(clearFilledFields());
                    }, 2500);
                  }
                  const prod = event.complaint?.product_name || "the product";
                  const lot = event.complaint?.batch_lot_number || "N/A";
                  const sev = event.complaint?.severity_suggested || "Major";
                  const cat = event.complaint?.complaint_category || "General";
                  dispatch(
                    addAssistantMessage({
                      message: `Complaint details extracted and validated for ${prod} (Batch ${lot}). Categorized as "${cat}" with suggested severity "${sev}". Form is populated and ready for QA review.`,
                      complaintId: complaint.id,
                    }),
                  );
                } else {
                  dispatch(
                    setExtractionStatus({
                      status: "processing",
                      progress,
                      label: message,
                    }),
                  );
                }
              } catch (parseErr) {
                console.warn("Error parsing SSE event chunk:", parseErr);
              }
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Extraction intake error:", err);
      dispatch(
        setExtractionStatus({
          status: "idle",
          progress: 0,
          label: "Extraction failed",
        }),
      );
      dispatch(
        addAssistantMessage({
          message: `Unable to complete extraction: ${err.message || "Network error"}. Please verify connection and try again.`,
          complaintId: complaint.id,
        }),
      );
    } finally {
      dispatch(setProcessing(false));
    }
  };

  const handleFileDrop = async (file: File) => {
    if (!complaint) return;
    setActiveFile(file);
    dispatch(
      addUserMessage({
        message: `📁 Attached document: "${file.name}" (${(file.size / 1024).toFixed(1)} KB)`,
        complaintId: complaint.id,
      }),
    );
    dispatch(setProcessing(true));
    dispatch(
      setExtractionStatus({
        status: "uploading",
        progress: 10,
        label: `Uploading '${file.name}' to Document Ingestion pipeline...`,
      }),
    );

    try {
      const baseUrl =
        import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
      const formData = new FormData();
      formData.append("file", file);
      formData.append("complaint_id", complaint.id);

      const response = await fetch(`${baseUrl}/copilot/ingest`, {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
        },
        body: formData,
      });

      if (!response.ok) {
        let errMsg = `Server returned HTTP ${response.status}`;
        try {
          const errData = await response.json();
          if (errData?.detail) {
            errMsg =
              typeof errData.detail === "string"
                ? errData.detail
                : JSON.stringify(errData.detail);
          }
        } catch {
          // fallback to status code message
        }
        throw new Error(errMsg);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data:")) {
              const dataStr = trimmed.slice(5).trim();
              if (!dataStr) continue;
              try {
                const event = JSON.parse(dataStr);
                const progress = event.progress ?? 50;
                const message = event.status_message ?? "";
                const step = event.step ?? "";

                if (
                  step === "risk_assessor" ||
                  progress === 100 ||
                  event.complaint
                ) {
                  dispatch(
                    setExtractionStatus({
                      status: "complete",
                      progress: 100,
                      label: message || "Document extraction complete.",
                    }),
                  );
                  if (event.complaint) {
                    dispatch(applyAIExtraction(event.complaint));
                    setTimeout(() => {
                      dispatch(clearFilledFields());
                    }, 2500);
                  }
                  const prod = event.complaint?.product_name || "the product";
                  const lot = event.complaint?.batch_lot_number || "N/A";
                  const sev = event.complaint?.severity_suggested || "Major";
                  const cat = event.complaint?.complaint_category || "General";
                  dispatch(
                    addAssistantMessage({
                      message: `Successfully ingested document "${file.name}". Extracted complaint for ${prod} (Batch ${lot}), categorized as "${cat}" with suggested severity "${sev}". Form is populated and ready for review.`,
                      complaintId: complaint.id,
                    }),
                  );
                } else if (step === "document_loader") {
                  dispatch(
                    setExtractionStatus({
                      status: "extracting",
                      progress,
                      label:
                        message ||
                        `Parsing document structure & tables from ${file.name}...`,
                    }),
                  );
                } else if (step === "validator") {
                  dispatch(
                    setExtractionStatus({
                      status: "validating",
                      progress,
                      label: message,
                    }),
                  );
                } else if (step === "risk_assessor") {
                  dispatch(
                    setExtractionStatus({
                      status: "assessing",
                      progress,
                      label: message,
                    }),
                  );
                } else {
                  dispatch(
                    setExtractionStatus({
                      status: "processing",
                      progress,
                      label: message,
                    }),
                  );
                }
              } catch (parseErr) {
                console.warn("Error parsing SSE event chunk:", parseErr);
              }
            }
          }
        }
      }
    } catch (err: any) {
      console.error("File ingestion error:", err);
      dispatch(
        setExtractionStatus({
          status: "idle",
          progress: 0,
          label: "Document extraction failed",
        }),
      );
      dispatch(
        addAssistantMessage({
          message: `Failed to process document "${file.name}": ${err.message || "Network error"}. Please try again.`,
          complaintId: complaint.id,
        }),
      );
    } finally {
      dispatch(setProcessing(false));
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || !complaint || isCommitted || isProcessing) return;
    const text = chatInput.trim();
    setChatInput("");
    dispatch(addUserMessage({ message: text, complaintId: complaint.id }));

    try {
      const resultAction = await dispatch(
        sendChatMessage({ complaintId: complaint.id, message: text }),
      );
      if (sendChatMessage.fulfilled.match(resultAction)) {
        const { updated_fields } = resultAction.payload;
        if (updated_fields && Object.keys(updated_fields).length > 0) {
          dispatch(applyAIExtraction(updated_fields as any));
          setTimeout(() => {
            dispatch(clearFilledFields());
          }, 2500);
        }
      }
    } catch (err) {
      console.error("Chat error:", err);
    }
  };

  // ── Pre-Commit Guard ────────────────────────────────────────────────────────
  const handleCommit = async () => {
    if (!complaint) return;
    dispatch(validateForm());
    const report = evaluateCompleteness(complaint);

    if (!report.canCommit) {
      setCommitErrorAlert(report.summaryMessage);
      const firstFailing = report.items.find((i) => !i.passed);
      if (firstFailing) {
        handleFocusField(firstFailing.fieldId);
      }
      return;
    }

    setCommitErrorAlert(null);
    try {
      await dispatch(commitComplaint(complaint.id)).unwrap();
      dispatch(
        addAssistantMessage({
          message: `✓ Complaint ${complaint.id} has been formally committed to the immutable QMS audit ledger. All fields locked in compliance with 21 CFR 211.198.`,
          complaintId: complaint.id,
        }),
      );
    } catch (err: any) {
      const msg = err?.message || "Failed to commit complaint to QMS ledger.";
      setCommitErrorAlert(msg);
      console.error("Failed to commit:", err);
    }
  };

  // ── Reset Handler ───────────────────────────────────────────────────────────
  const handleReset = async () => {
    setShowResetConfirm(false);
    setActiveFile(null);
    setCommitErrorAlert(null);
    const oldId = complaint?.id;
    dispatch(resetForm());
    if (oldId) {
      dispatch(resetChat(oldId));
    } else {
      dispatch(resetChat());
    }

    const action = await dispatch(createComplaint());
    if (createComplaint.fulfilled.match(action)) {
      dispatch(
        addAssistantMessage({
          message:
            "Initialized a fresh complaint record. Upload a document or paste text above to begin.",
          complaintId: action.payload.id,
        }),
      );
    }
  };

  if (loading && !complaint) {
    return (
      <div className="page-loading">
        <div className="page-loading__spinner" />
        <p className="text-body">Initializing complaint session…</p>
      </div>
    );
  }

  if (!complaint && serverError) {
    return (
      <div className="server-error-state">
        <div className="server-error-card" role="alert">
          <div className="server-error-card__icon-wrap">
            <AlertTriangle size={30} className="server-error-card__icon" />
          </div>
          <h2 className="server-error-card__title">Backend Communication Error</h2>
          <p className="server-error-card__message">{serverError}</p>
          <div className="server-error-card__tips">
            <p className="text-small">Troubleshooting Guidance:</p>
            <ul className="text-small">
              <li>Ensure the FastAPI server is running (<code>uvicorn app.main:app --reload --port 8000</code>)</li>
              <li>Verify PostgreSQL / Supabase connection credentials in <code>backend/.env</code></li>
              <li>Inspect backend server terminal logs for database or runtime exceptions</li>
            </ul>
          </div>
          <div className="server-error-card__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => dispatch(restoreOrInitComplaint())}
            >
              <RefreshCw size={14} />
              <span>Retry Connection</span>
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => dispatch(createComplaint())}
            >
              <span>Initialize New Session</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const todayIso = new Date().toISOString().split("T")[0];

  return (
    <div className="complaint-page">
      {/* ── Left pane: Form ─────────────────────────────────────────────────── */}
      <main className="complaint-page__form-pane" aria-label="Complaint form">
        <div className="form-pane-inner">
          {/* Server Error Alert Banner */}
          {serverError && (
            <div className="server-error-banner" role="alert">
              <div className="server-error-banner__content">
                <AlertTriangle size={16} className="server-error-banner__icon" />
                <span className="text-small">{serverError}</span>
              </div>
              <button
                type="button"
                className="server-error-banner__close"
                onClick={() => dispatch(clearFormError())}
                title="Dismiss server alert"
                aria-label="Dismiss server alert"
              >
                <X size={14} />
              </button>
            </div>
          )}

          {/* Header */}
          <div className="form-header">
            <div className="form-header__title-group">
              <h1 className="text-h1">Log Customer Complaint</h1>
              <p className="text-small form-header__subtitle">
                API &amp; FDF Quality Assurance Module
              </p>
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

          {/* AI-generated complaint summary chip */}
          {complaint?.complaint_summary && (
            <div className="complaint-summary-chip">
              <Sparkles size={11} className="complaint-summary-chip__icon" />
              <span>{complaint.complaint_summary}</span>
            </div>
          )}

          {/* AI Extraction Status HUD Banner */}
          {isExtracting && (
            <div className="extraction-active-banner" role="status" aria-live="polite">
              <div className="extraction-active-banner__left">
                <Sparkles size={16} className="extraction-sparkle-spin" />
                <div className="extraction-active-banner__text">
                  <span className="extraction-active-banner__title">
                    AI Document Extraction &amp; Triage in Progress
                  </span>
                  <span className="extraction-active-banner__subtitle text-small">
                    {extractionStatusLabel || "Synthesizing pharmaceutical QMS fields from source…"}
                  </span>
                </div>
              </div>
              <div className="extraction-active-banner__badge">
                {extractionProgress}%
              </div>
            </div>
          )}

          {/* Section 1: Origin & Customer Details */}
          <SectionCard number={1} title="Origin & Customer Details">
            <SelectField
              id="complaint_source"
              label="Complaint Source"
              value={complaint?.complaint_source ?? null}
              options={COMPLAINT_SOURCE_OPTIONS}
              onChange={(v) => handleFieldChange("complaint_source", v)}
              onBlur={() => handleFieldBlur("complaint_source")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.complaint_source
                  ? validationErrors.complaint_source
                  : undefined
              }
              aiJustFilled={justFilledFields.has("complaint_source")}
            />
            <TextField
              id="customer_name"
              label="Customer Name"
              value={complaint?.customer_name ?? null}
              onChange={(v) => handleFieldChange("customer_name", v)}
              onBlur={() => handleFieldBlur("customer_name")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.customer_name
                  ? validationErrors.customer_name
                  : undefined
              }
              helperText="Reporting hospital, pharmacy, distributor, or patient"
              aiJustFilled={justFilledFields.has("customer_name")}
            />
          </SectionCard>

          {/* Section 2: Product & Batch Identification */}
          <SectionCard number={2} title="Product & Batch Identification">
            <TextField
              id="product_name"
              label="Product Name"
              value={complaint?.product_name ?? null}
              onChange={(v) => handleFieldChange("product_name", v)}
              onBlur={() => handleFieldBlur("product_name")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.product_name
                  ? validationErrors.product_name
                  : undefined
              }
              aiJustFilled={justFilledFields.has("product_name")}
            />
            <TextField
              id="product_strength_grade"
              label="Product Strength / Grade"
              value={complaint?.product_strength_grade ?? null}
              onChange={(v) => handleFieldChange("product_strength_grade", v)}
              onBlur={() => handleFieldBlur("product_strength_grade")}
              disabled={isDisabled}
              loading={isExtracting}
              error={
                touchedFields.product_strength_grade
                  ? validationErrors.product_strength_grade
                  : undefined
              }
              helperText="e.g. 500mg, Grade A, 10mg/mL"
              aiJustFilled={justFilledFields.has("product_strength_grade")}
            />
            <TextField
              id="batch_lot_number"
              label="Batch / Lot Number"
              value={complaint?.batch_lot_number ?? null}
              onChange={(v) => handleFieldChange("batch_lot_number", v)}
              onBlur={() => handleFieldBlur("batch_lot_number")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.batch_lot_number
                  ? validationErrors.batch_lot_number
                  : undefined
              }
              helperText="e.g. BMX240601"
              aiJustFilled={justFilledFields.has("batch_lot_number")}
            />
            <DateField
              id="manufacturing_date"
              label="Manufacturing Date"
              value={complaint?.manufacturing_date ?? null}
              onChange={(v) => handleFieldChange("manufacturing_date", v)}
              onBlur={() => handleFieldBlur("manufacturing_date")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              max={todayIso}
              error={
                touchedFields.manufacturing_date
                  ? validationErrors.manufacturing_date
                  : undefined
              }
              aiJustFilled={justFilledFields.has("manufacturing_date")}
            />
            <DateField
              id="expiry_date"
              label="Expiry Date"
              value={complaint?.expiry_date ?? null}
              onChange={(v) => handleFieldChange("expiry_date", v)}
              onBlur={() => handleFieldBlur("expiry_date")}
              disabled={isDisabled}
              loading={isExtracting}
              min={complaint?.manufacturing_date || undefined}
              error={
                touchedFields.expiry_date
                  ? validationErrors.expiry_date
                  : undefined
              }
              helperText="Optional; must be later than manufacturing date if provided"
              aiJustFilled={justFilledFields.has("expiry_date")}
            />
            <QuantityField
              id="affected_quantity"
              label="Quantity Affected"
              value={complaint?.affected_quantity ?? null}
              onChange={(v) => handleFieldChange("affected_quantity", v)}
              onBlur={() => handleFieldBlur("affected_quantity")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.affected_quantity
                  ? validationErrors.affected_quantity
                  : undefined
              }
              helperText="Include count & unit (e.g. 12 bottles, 48 capsules)"
              aiJustFilled={justFilledFields.has("affected_quantity")}
            />
          </SectionCard>

          {/* Section 3: Complaint Details */}
          <SectionCard number={3} title="Complaint Details">
            <SelectField
              id="complaint_category"
              label="Complaint Type"
              value={complaint?.complaint_category ?? null}
              options={CATEGORY_OPTIONS}
              onChange={(v) => handleFieldChange("complaint_category", v)}
              onBlur={() => handleFieldBlur("complaint_category")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.complaint_category
                  ? validationErrors.complaint_category
                  : undefined
              }
              aiJustFilled={justFilledFields.has("complaint_category")}
            />
            <DateField
              id="complaint_date"
              label="Complaint Date"
              value={complaint?.complaint_date ?? null}
              onChange={(v) => handleFieldChange("complaint_date", v)}
              onBlur={() => handleFieldBlur("complaint_date")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              max={todayIso}
              error={
                touchedFields.complaint_date
                  ? validationErrors.complaint_date
                  : undefined
              }
              aiJustFilled={justFilledFields.has("complaint_date")}
            />
            <TextField
              id="originating_site_block"
              label="Originating Site / Block"
              value={complaint?.originating_site_block ?? null}
              onChange={(v) => handleFieldChange("originating_site_block", v)}
              onBlur={() => handleFieldBlur("originating_site_block")}
              disabled={isDisabled}
              loading={isExtracting}
              error={
                touchedFields.originating_site_block
                  ? validationErrors.originating_site_block
                  : undefined
              }
              helperText="e.g. Site 2, Block B, Sterile Fill Line 4"
              aiJustFilled={justFilledFields.has("originating_site_block")}
            />
            <TextField
              id="impacted_npm"
              label="Impacted Non-Product Materials"
              value={complaint?.impacted_npm ?? null}
              onChange={(v) => handleFieldChange("impacted_npm", v)}
              onBlur={() => handleFieldBlur("impacted_npm")}
              disabled={isDisabled}
              loading={isExtracting}
              error={
                touchedFields.impacted_npm
                  ? validationErrors.impacted_npm
                  : undefined
              }
              helperText="Non-product packaging/materials (e.g. Amber glass vial, Rubber stopper)"
              aiJustFilled={justFilledFields.has("impacted_npm")}
            />
            <TextField
              id="complaint_description"
              label="Detailed Complaint Description"
              value={complaint?.complaint_description ?? null}
              onChange={(v) => handleFieldChange("complaint_description", v)}
              onBlur={() => handleFieldBlur("complaint_description")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              multiline
              rows={5}
              className="full-width"
              error={
                touchedFields.complaint_description
                  ? validationErrors.complaint_description
                  : undefined
              }
              helperText="Minimum 20 characters describing observed defect, condition, and packaging status"
              aiJustFilled={justFilledFields.has("complaint_description")}
            />
          </SectionCard>

          {/* Section 4: Initial Assessment & Priority */}
          <SectionCard number={4} title="Initial Assessment & Priority">
            <SelectField
              id="severity_suggested"
              label="Initial Severity"
              value={complaint?.severity_suggested ?? null}
              options={[
                { value: "Critical", label: "Critical" },
                { value: "Major", label: "Major" },
                { value: "Minor", label: "Minor" },
                { value: "Not Assessed", label: "Not Assessed" },
              ]}
              onChange={(v) => handleFieldChange("severity_suggested", v)}
              onBlur={() => handleFieldBlur("severity_suggested")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.severity_suggested
                  ? validationErrors.severity_suggested
                  : undefined
              }
              aiJustFilled={justFilledFields.has("severity_suggested")}
            />
            <SelectField
              id="priority"
              label="Priority"
              value={complaint?.priority ?? null}
              options={[
                { value: "High", label: "High" },
                { value: "Medium", label: "Medium" },
                { value: "Low", label: "Low" },
                { value: "Not Assessed", label: "Not Assessed" },
              ]}
              onChange={(v) => handleFieldChange("priority", v)}
              onBlur={() => handleFieldBlur("priority")}
              disabled={isDisabled}
              loading={isExtracting}
              required
              error={
                touchedFields.priority ? validationErrors.priority : undefined
              }
              aiJustFilled={justFilledFields.has("priority")}
            />

            {/* AI Assessment sub-panel */}
            {complaint && (
              <div className="full-width">
                <AIAssessmentCard
                  severity={complaint.severity_suggested}
                  nextAction={complaint.suggested_next_action}
                  riskAssessment={complaint.initial_risk_assessment}
                  onSeverityChange={(v) =>
                    handleFieldChange("severity_suggested", v)
                  }
                  disabled={isDisabled}
                  loading={isExtracting}
                />
                {/* Phase 6: CAPA Recommendation */}
                <CAPARecommendationCard
                  capaRecommendation={complaint.capa_recommendation}
                  loading={isExtracting}
                />
                {/* Phase 6: Duplicate Detection */}
                <DuplicateAlertCard
                  complaintId={complaint.id}
                  complaintDescription={complaint.complaint_description}
                  isExtracting={isExtracting}
                  isCommitted={isCommitted}
                />
              </div>
            )}
          </SectionCard>

          {/* ── Pre-Commit Submit Checklist (Completeness Checker) ───────────── */}
          {!isCommitted && (
            <SubmitChecklist
              complaint={complaint}
              onFocusField={handleFocusField}
            />
          )}

          {/* ── Validation error alert on commit attempt ─────────────────────── */}
          {commitErrorAlert && (
            <div className="commit-error-banner" role="alert">
              <AlertCircle size={16} />
              <span>{commitErrorAlert}</span>
            </div>
          )}

          {/* ── Committed state info ─────────────────────────────────────────── */}
          {isCommitted && complaint?.committed_at && (
            <div className="committed-banner">
              <Database size={16} />
              Committed to QMS Ledger on{" "}
              {new Date(complaint.committed_at).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </div>
          )}

          {/* ── Action buttons ───────────────────────────────────────────────── */}
          <div className="form-actions">
            {isCommitted ? (
              <button
                className="btn-commit"
                onClick={handleReset}
                id="new-complaint-btn"
                type="button"
              >
                <RefreshCw size={16} />
                Log Another Complaint
              </button>
            ) : (
              <>
                <button
                  className="btn-secondary form-actions__reset"
                  onClick={() => setShowResetConfirm(true)}
                  id="reset-form-btn"
                  type="button"
                  disabled={isDisabled || isExtracting}
                >
                  <RefreshCw size={14} />
                  Reset Form
                </button>
                <button
                  className="btn-commit"
                  onClick={handleCommit}
                  disabled={committing || !complaint || isExtracting}
                  id="commit-btn"
                  type="button"
                >
                  <Database size={16} />
                  {committing ? "Committing…" : "Commit to QMS Ledger"}
                </button>
              </>
            )}
          </div>
        </div>
      </main>

      {/* ── Right pane: AI Copilot ────────────────────────────────────────────── */}
      <aside
        className="complaint-page__copilot-pane"
        aria-label="AI Complaint Intake Assistant"
      >
        {/* Copilot header */}
        <div className="copilot-header">
          <div className="copilot-header__title-group">
            <span className="copilot-header__icon" aria-hidden="true">
              ✦
            </span>
            <h2 className="text-h2">AI Complaint Intake Assistant</h2>
          </div>
        </div>

        <div className="copilot-body">
          {/* File dropzone */}
          <Dropzone
            onFileDrop={handleFileDrop}
            activeFile={activeFile}
            onClearFile={() => setActiveFile(null)}
            disabled={isDisabled || isExtracting}
          />

          {/* OR divider */}
          <div className="or-divider">OR</div>

          {/* Paste text button */}
          <PasteTextModal onSubmit={handlePasteText} disabled={isDisabled || isExtracting} />

          {/* Supported formats info */}
          <div className="format-info-box">
            <span className="format-info-box__icon" aria-hidden="true">
              ℹ
            </span>
            <span className="text-small">
              Supported formats: <strong>PDF, DOCX, TXT, EML</strong> — Max file
              size: 10MB
            </span>
          </div>

          {/* Extraction progress */}
          <ProgressBar
            visible={extractionStatus !== "idle"}
            progress={extractionProgress}
            label={extractionStatusLabel}
          />

          {/* Chat section label */}
          <p className="text-section-label">AI Assistant</p>

          {/* Chat messages */}
          <div
            className="chat-thread"
            aria-live="polite"
            aria-label="Chat thread"
          >
            {isRestoringChat ? (
              <ChatSkeleton />
            ) : (
              messages.map((msg) => (
                <ChatBubble key={msg.id} message={msg} />
              ))
            )}
            {isProcessing && !isRestoringChat && (
              <div className="chat-typing fade-in-up">
                <span />
                <span />
                <span />
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
                placeholder={
                  isRestoringChat
                    ? "Restoring conversation history…"
                    : isExtracting
                    ? "AI is extracting document details… please wait"
                    : isProcessing
                    ? "Copilot is analyzing…"
                    : "Ask me anything about this complaint…"
                }
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && !e.shiftKey && handleSendChat()
                }
                disabled={isDisabled || isProcessing || isRestoringChat}
                aria-label="Chat input"
                id="chat-input"
              />
              <button
                className="chat-send-btn"
                onClick={handleSendChat}
                disabled={
                  !chatInput.trim() || isDisabled || isProcessing || isRestoringChat
                }
                aria-label="Send message"
                id="chat-send-btn"
                type="button"
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
        <div
          className="paste-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-dialog-title"
        >
          <div className="paste-modal" style={{ maxWidth: 400 }}>
            <div className="paste-modal__header">
              <h2 id="reset-dialog-title" className="text-h2">
                Reset Form?
              </h2>
            </div>
            <div className="paste-modal__body">
              <p className="text-body">
                This will clear all extracted data, reset the status to Pending
                Triage, and initialize a fresh draft. This action cannot be
                undone.
              </p>
            </div>
            <div className="paste-modal__footer">
              <button
                className="btn-secondary"
                onClick={() => setShowResetConfirm(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleReset}
                id="reset-confirm-btn"
                type="button"
                style={{ background: "#DC2626" }}
              >
                Yes, Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
