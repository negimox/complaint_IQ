import type { ComplaintStatus } from '../types/complaint';
import './StatusBadge.css';

interface StatusBadgeProps {
  status: ComplaintStatus;
}

const STATUS_CONFIG: Record<ComplaintStatus, { label: string; className: string }> = {
  pending_triage:   { label: 'Pending Triage',   className: 'status-badge--amber' },
  ready_to_commit:  { label: 'Ready to Commit',  className: 'status-badge--green' },
  committed:        { label: 'Committed',         className: 'status-badge--blue'  },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const { label, className } = STATUS_CONFIG[status];
  return (
    <span className={`status-badge text-badge ${className}`}>
      <span className="status-badge__dot" />
      {label}
    </span>
  );
}
