import './ProgressBar.css';

interface ProgressBarProps {
  progress: number;   // 0–100
  label?: string;     // status message
  visible: boolean;
}

export default function ProgressBar({ progress, label, visible }: ProgressBarProps) {
  if (!visible) return null;

  return (
    <div className="progress-bar-section fade-in-up">
      <div className="progress-bar-section__header">
        <span className="text-section-label">Extraction Progress</span>
        <span className="progress-bar-section__pct text-badge">{progress}%</span>
      </div>
      <div className="progress-bar__track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div
          className="progress-bar__fill"
          style={{ width: `${progress}%` }}
        />
      </div>
      {label && (
        <p className="progress-bar__label text-small">{label}</p>
      )}
    </div>
  );
}
