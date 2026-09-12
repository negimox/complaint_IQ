import React, { useState, useEffect, useCallback } from 'react';
import { Copy, ExternalLink, AlertCircle, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { api } from '../api/client';
import './DuplicateAlertCard.css';

interface SimilarComplaint {
  id: string;
  customer_name: string | null;
  product_name: string | null;
  batch_lot_number: string | null;
  complaint_category: string | null;
  severity_suggested: string | null;
  complaint_summary: string | null;
  complaint_date: string | null;
  similarity: number;
}

interface DuplicatesResponse {
  complaint_id: string;
  duplicates: SimilarComplaint[];
  count: number;
  message: string;
}

interface DuplicateAlertCardProps {
  complaintId: string | null;
  isCommitted?: boolean;
}

const DuplicateAlertCard: React.FC<DuplicateAlertCardProps> = ({
  complaintId,
  isCommitted,
}) => {
  const [loading, setLoading] = useState(false);
  const [duplicates, setDuplicates] = useState<SimilarComplaint[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [checked, setChecked] = useState(false);
  const [message, setMessage] = useState('');

  const checkDuplicates = useCallback(async () => {
    if (!complaintId || checked) return;
    setLoading(true);
    try {
      const { data } = await api.get<DuplicatesResponse>(
        `/complaints/${complaintId}/duplicates`
      );
      setDuplicates(data.duplicates || []);
      setMessage(data.message || '');
    } catch {
      setDuplicates([]);
    } finally {
      setLoading(false);
      setChecked(true);
    }
  }, [complaintId, checked]);

  useEffect(() => {
    // Auto-check after complaint is created (has an ID)
    if (complaintId && !checked) {
      checkDuplicates();
    }
  }, [complaintId, checked, checkDuplicates]);

  if (!complaintId || (!loading && checked && duplicates.length === 0)) return null;

  const getSeverityClass = (sev: string | null) => {
    if (sev === 'Critical') return 'dup-severity--critical';
    if (sev === 'Major') return 'dup-severity--major';
    return 'dup-severity--minor';
  };

  const getSimilarityClass = (sim: number) => {
    if (sim >= 0.95) return 'dup-sim--very-high';
    if (sim >= 0.88) return 'dup-sim--high';
    return 'dup-sim--medium';
  };

  return (
    <div className="dup-card">
      <button
        className="dup-card__header"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
        id="duplicate-alert-toggle"
      >
        <span className="dup-card__header-left">
          <Copy size={14} className="dup-card__icon" />
          <span className="dup-card__title">Duplicate Detection</span>
          {loading && <Loader2 size={12} className="dup-card__spinner" />}
          {!loading && duplicates.length > 0 && (
            <span className="dup-card__count-badge">{duplicates.length} similar</span>
          )}
        </span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="dup-card__body">
          {loading && (
            <div className="dup-card__loading" aria-busy="true">
              <div className="dup-card__loading-head">
                <Loader2 size={13} className="dup-card__spinner" />
                <span>Searching QMS ledger for similar complaints via pgvector…</span>
              </div>
              <div className="dup-item dup-item--skeleton">
                <div className="dup-skeleton__bar" style={{ width: 110, height: 16 }} />
                <div className="dup-skeleton__bar" style={{ width: '85%', height: 13 }} />
                <div className="dup-skeleton__bar" style={{ width: '60%', height: 13 }} />
              </div>
            </div>
          )}

          {!loading && duplicates.length > 0 && (
            <>
              <div className="dup-card__alert-row">
                <AlertCircle size={13} />
                <span>
                  {duplicates.length} committed complaint{duplicates.length > 1 ? 's' : ''} with
                  high similarity detected. Review before committing to avoid duplicate investigations.
                </span>
              </div>
              <div className="dup-card__list">
                {duplicates.map((d) => (
                  <div key={d.id} className="dup-item">
                    <div className="dup-item__top">
                      <span className="dup-item__id">{d.id}</span>
                      <span className={`dup-item__sim ${getSimilarityClass(d.similarity)}`}>
                        {Math.round(d.similarity * 100)}% match
                      </span>
                      {d.severity_suggested && (
                        <span className={`dup-item__sev ${getSeverityClass(d.severity_suggested)}`}>
                          {d.severity_suggested}
                        </span>
                      )}
                    </div>
                    {d.complaint_summary && (
                      <p className="dup-item__summary">{d.complaint_summary}</p>
                    )}
                    <div className="dup-item__meta">
                      {d.product_name && <span>{d.product_name}</span>}
                      {d.batch_lot_number && <span>Lot: {d.batch_lot_number}</span>}
                      {d.complaint_category && <span>{d.complaint_category}</span>}
                      {d.complaint_date && <span>{d.complaint_date}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {!loading && checked && duplicates.length === 0 && (
            <p className="dup-card__no-results">No similar complaints found in the committed ledger.</p>
          )}
        </div>
      )}
    </div>
  );
};

export default DuplicateAlertCard;
