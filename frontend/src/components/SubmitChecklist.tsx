import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import type { Complaint } from '../types/complaint';
import { evaluateCompleteness } from '../utils/validation';
import './SubmitChecklist.css';

interface SubmitChecklistProps {
  complaint: Complaint | null;
  onFocusField?: (fieldId: string) => void;
}

export default function SubmitChecklist({ complaint, onFocusField }: SubmitChecklistProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const report = evaluateCompleteness(complaint);

  const { score, totalChecks, passedChecks, items, canCommit, summaryMessage } = report;

  const handleItemClick = (fieldId: string) => {
    if (onFocusField) {
      onFocusField(fieldId);
    } else {
      const el = document.getElementById(fieldId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.focus();
      }
    }
  };

  return (
    <div className={`submit-checklist ${canCommit ? 'submit-checklist--complete' : ''}`}>
      {/* Header */}
      <div
        className="submit-checklist__header"
        onClick={() => setIsExpanded((prev) => !prev)}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            setIsExpanded((prev) => !prev);
          }
        }}
      >
        <div className="submit-checklist__title-group">
          <ShieldCheck size={18} className="submit-checklist__shield-icon" />
          <div>
            <h3 className="submit-checklist__title">
              QMS Pre-Commit Compliance Checklist
            </h3>
            <p className="submit-checklist__subtitle">
              21 CFR 211.198 &amp; ICH Q10 Data Integrity Verification
            </p>
          </div>
        </div>

        <div className="submit-checklist__badge-group">
          <span
            className={`submit-checklist__score-badge ${
              canCommit ? 'score-badge--pass' : 'score-badge--pending'
            }`}
          >
            {passedChecks} / {totalChecks} Checks ({score}%)
          </span>
          <button
            type="button"
            className="submit-checklist__toggle-btn"
            aria-label={isExpanded ? 'Collapse checklist' : 'Expand checklist'}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="submit-checklist__progress-track">
        <div
          className={`submit-checklist__progress-bar ${
            canCommit ? 'progress-bar--complete' : ''
          }`}
          style={{ width: `${score}%` }}
        />
      </div>

      {/* Body */}
      {isExpanded && (
        <div className="submit-checklist__body">
          <div className="submit-checklist__items">
            {items.map((item) => (
              <div
                key={item.id}
                className={`checklist-item ${item.passed ? 'checklist-item--passed' : 'checklist-item--pending'}`}
                onClick={() => !item.passed && handleItemClick(item.fieldId)}
              >
                <div className="checklist-item__status-icon">
                  {item.passed ? (
                    <CheckCircle2 size={16} className="icon-pass" />
                  ) : (
                    <AlertCircle size={16} className="icon-pending" />
                  )}
                </div>

                <div className="checklist-item__content">
                  <div className="checklist-item__label-row">
                    <span className="checklist-item__label">{item.label}</span>
                    {!item.passed && (
                      <button
                        type="button"
                        className="checklist-item__resolve-link"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleItemClick(item.fieldId);
                        }}
                      >
                        Fill field <ArrowRight size={11} />
                      </button>
                    )}
                  </div>
                  <p className="checklist-item__desc">{item.description}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Status Alert Banner */}
          <div
            className={`submit-checklist__banner ${
              canCommit ? 'banner--success' : 'banner--warning'
            }`}
          >
            {canCommit ? (
              <>
                <CheckCircle2 size={16} className="banner-icon-success" />
                <span>{summaryMessage}</span>
              </>
            ) : (
              <>
                <AlertCircle size={16} className="banner-icon-warning" />
                <span>{summaryMessage}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
