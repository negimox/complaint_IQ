import React, { useState } from 'react';
import { ShieldAlert, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import './CAPARecommendationCard.css';

interface CAPARecommendationCardProps {
  capaRecommendation: string | null;
}

function parseCAPAText(raw: string): {
  type: string;
  rationale: string;
  actions: string[];
} {
  const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
  let type = '';
  let rationale = '';
  const actions: string[] = [];
  let inActions = false;

  for (const line of lines) {
    if (line.startsWith('CAPA Type:')) {
      type = line.replace('CAPA Type:', '').trim();
    } else if (line.startsWith('Rationale:')) {
      rationale = line.replace('Rationale:', '').trim();
    } else if (line.startsWith('Recommended Actions:')) {
      inActions = true;
    } else if (inActions && (line.startsWith('•') || line.startsWith('-'))) {
      actions.push(line.replace(/^[•\-]\s*/, '').trim());
    }
  }

  return { type, rationale, actions };
}

const CAPARecommendationCard: React.FC<CAPARecommendationCardProps> = ({
  capaRecommendation,
}) => {
  const [expanded, setExpanded] = useState(true);

  if (!capaRecommendation) return null;

  const { type, rationale, actions } = parseCAPAText(capaRecommendation);

  const isUrgent = type.toLowerCase().includes('recall') || type.toLowerCase().includes('immediate');
  const isMonitoring = type.toLowerCase().includes('monitoring');

  return (
    <div className={`capa-card ${isUrgent ? 'capa-card--urgent' : isMonitoring ? 'capa-card--low' : 'capa-card--standard'}`}>
      <button
        className="capa-card__header"
        onClick={() => setExpanded((v) => !v)}
        type="button"
        aria-expanded={expanded}
        id="capa-card-toggle"
      >
        <span className="capa-card__header-left">
          <ShieldAlert size={15} className="capa-card__icon" />
          <span className="capa-card__title">CAPA Recommendation</span>
          <span className="capa-card__badge">ICH Q10</span>
        </span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="capa-card__body">
          {type && (
            <div className="capa-card__type">
              <span className="capa-card__type-label">CAPA Type</span>
              <span className={`capa-card__type-value ${isUrgent ? 'capa-card__type-value--urgent' : ''}`}>
                {type}
              </span>
            </div>
          )}

          {rationale && (
            <p className="capa-card__rationale">{rationale}</p>
          )}

          {actions.length > 0 && (
            <div className="capa-card__actions">
              <span className="capa-card__actions-label">Recommended Actions</span>
              <ul className="capa-card__actions-list">
                {actions.map((action, i) => (
                  <li key={i} className="capa-card__action-item">
                    <span className="capa-card__action-bullet" />
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="capa-card__disclaimer">
            <AlertTriangle size={11} />
            <span>AI recommendation — QA Director must initiate and own CAPA. Not a regulatory finding.</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default CAPARecommendationCard;
