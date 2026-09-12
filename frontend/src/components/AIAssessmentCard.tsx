import type { SeverityLevel } from '../types/complaint';
import './AIAssessmentCard.css';

interface AIAssessmentCardProps {
  severity: SeverityLevel | null;
  nextAction: string | null;
  riskAssessment: string | null;
  onSeverityChange?: (val: SeverityLevel) => void;
  disabled?: boolean;
  loading?: boolean;
}

const SEVERITY_OPTIONS: SeverityLevel[] = ['Critical', 'Major', 'Minor', 'Not Assessed'];

export default function AIAssessmentCard({
  severity,
  nextAction,
  riskAssessment,
  onSeverityChange,
  disabled,
  loading,
}: AIAssessmentCardProps) {
  if (loading && !severity && !nextAction && !riskAssessment) {
    return (
      <div className="ai-assessment-card ai-assessment-card--skeleton fade-in-up" aria-busy="true">
        <div className="ai-assessment-card__header">
          <span className="ai-assessment-card__title text-section-label">
            ✦ AI Risk Assessment
          </span>
          <span className="ai-assessment-card__hint text-small">Synthesizing risk matrix…</span>
        </div>
        <div className="ai-assessment-card__body">
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Severity (Suggested)</span>
            <div className="ai-assessment-skeleton__bar" style={{ width: 130, height: 26 }} />
          </div>
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Suggested Next Action</span>
            <div className="ai-assessment-skeleton__bar" style={{ width: '82%', height: 15 }} />
          </div>
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Initial Risk Assessment</span>
            <div className="ai-assessment-skeleton__bar" style={{ width: '92%', height: 15 }} />
            <div className="ai-assessment-skeleton__bar" style={{ width: '65%', height: 15 }} />
          </div>
        </div>
      </div>
    );
  }

  if (!severity && !nextAction && !riskAssessment) return null;

  return (
    <div className="ai-assessment-card fade-in-up">
      <div className="ai-assessment-card__header">
        <span className="ai-assessment-card__title text-section-label">
          ✦ AI Risk Assessment
        </span>
        <span className="ai-assessment-card__hint text-small">AI suggestion — verify before committing</span>
      </div>

      <div className="ai-assessment-card__body">
        {severity && (
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Severity (Suggested)</span>
            <select
              className={`ai-assessment-card__severity-select severity-select--${severity?.toLowerCase().replace(' ', '-')}`}
              value={severity ?? ''}
              onChange={(e) => onSeverityChange?.(e.target.value as SeverityLevel)}
              disabled={disabled}
            >
              {SEVERITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
        )}

        {nextAction && (
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Suggested Next Action</span>
            <p className="ai-assessment-card__value text-body">{nextAction}</p>
          </div>
        )}

        {riskAssessment && (
          <div className="ai-assessment-card__row">
            <span className="ai-assessment-card__field-label text-label">Initial Risk Assessment</span>
            <p className="ai-assessment-card__value text-body">{riskAssessment}</p>
          </div>
        )}
      </div>
    </div>
  );
}
