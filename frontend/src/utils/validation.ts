import type { Complaint } from '../types/complaint';

export type FormValidationErrors = Record<string, string>;

export interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  fieldId: string;
  passed: boolean;
  warning?: boolean;
}

export interface CompletenessReport {
  score: number;            // 0 - 100
  totalChecks: number;
  passedChecks: number;
  items: ChecklistItem[];
  canCommit: boolean;
  summaryMessage: string;
}

/**
 * Validates an individual field value based on pharma QMS rules (ICH Q10 / 21 CFR 211.198).
 * Returns an error message string if invalid, or null if valid.
 */
export function validateComplaintField(
  field: string,
  value: string | null | undefined,
  allFields?: Partial<Complaint> | null
): string | null {
  const trimmed = typeof value === 'string' ? value.trim() : '';

  switch (field) {
    case 'complaint_source':
      if (!trimmed) return 'Complaint source is required.';
      return null;

    case 'customer_name':
      if (!trimmed) return 'Customer / Reporting entity name is required.';
      if (trimmed.length < 2) return 'Customer name must be at least 2 characters.';
      return null;

    case 'product_name':
      if (!trimmed) return 'Product name is required for batch traceability.';
      if (trimmed.length < 2) return 'Product name must be at least 2 characters.';
      return null;

    case 'batch_lot_number':
      if (!trimmed) return 'Batch or lot number is required.';
      if (trimmed.length < 2) return 'Batch / lot number must be at least 2 characters.';
      return null;

    case 'manufacturing_date': {
      if (!trimmed) return 'Manufacturing date is required.';
      const mfgDate = new Date(trimmed);
      if (isNaN(mfgDate.getTime())) return 'Please enter a valid manufacturing date.';
      const today = new Date();
      today.setHours(23, 59, 59, 999);
      if (mfgDate > today) return 'Manufacturing date cannot be in the future.';
      if (allFields?.expiry_date) {
        const expDate = new Date(allFields.expiry_date);
        if (!isNaN(expDate.getTime()) && mfgDate >= expDate) {
          return 'Manufacturing date must precede the expiry date.';
        }
      }
      return null;
    }

    case 'expiry_date': {
      if (!trimmed) return null; // Expiry date can be omitted / "Not Provided" in certain preliminary complaints
      const expDate = new Date(trimmed);
      if (isNaN(expDate.getTime())) return 'Please enter a valid expiry date.';
      if (allFields?.manufacturing_date) {
        const mfgDate = new Date(allFields.manufacturing_date);
        if (!isNaN(mfgDate.getTime()) && expDate <= mfgDate) {
          return 'Expiry date must be later than manufacturing date.';
        }
      }
      return null;
    }

    case 'affected_quantity':
      if (!trimmed) return 'Affected quantity is required (e.g., 48 capsules, 25 kg).';
      if (trimmed.length < 2) return 'Please specify quantity and unit (e.g. 100 tablets).';
      return null;

    case 'complaint_category':
      if (!trimmed) return 'Complaint type / category is required.';
      return null;

    case 'complaint_date': {
      if (!trimmed) return 'Complaint receipt date is required.';
      const cDate = new Date(trimmed);
      if (isNaN(cDate.getTime())) return 'Please enter a valid complaint date.';
      const today = new Date();
      today.setHours(23, 59, 59, 999);
      if (cDate > today) return 'Complaint date cannot be in the future.';
      return null;
    }

    case 'complaint_description':
      if (!trimmed) return 'Detailed complaint description is required.';
      if (trimmed.length < 20) {
        return `Description is too brief for QA investigation (${trimmed.length}/20 characters minimum).`;
      }
      return null;

    case 'severity_suggested':
    case 'severity_final':
      if (!trimmed || trimmed === 'Not Assessed') {
        return 'Initial severity must be classified before committing.';
      }
      return null;

    case 'priority':
      if (!trimmed || trimmed === 'Not Assessed') {
        return 'Priority level must be assigned before committing.';
      }
      return null;

    default:
      return null;
  }
}

/**
 * Validates the entire complaint against all mandatory fields and chronological constraints.
 */
export function validateEntireComplaint(complaint: Partial<Complaint> | null): {
  isValid: boolean;
  errors: FormValidationErrors;
} {
  if (!complaint) {
    return {
      isValid: false,
      errors: { form: 'Complaint record has not been initialized.' },
    };
  }

  const fieldsToCheck = [
    'complaint_source',
    'customer_name',
    'product_name',
    'batch_lot_number',
    'manufacturing_date',
    'expiry_date',
    'affected_quantity',
    'complaint_category',
    'complaint_date',
    'complaint_description',
    'severity_suggested',
    'priority',
  ];

  const errors: FormValidationErrors = {};

  for (const field of fieldsToCheck) {
    const err = validateComplaintField(field, (complaint as any)[field], complaint);
    if (err) {
      errors[field] = err;
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Evaluates completeness for the QMS Pre-Commit Checklist.
 */
export function evaluateCompleteness(complaint: Partial<Complaint> | null): CompletenessReport {
  if (!complaint) {
    return {
      score: 0,
      totalChecks: 8,
      passedChecks: 0,
      items: [],
      canCommit: false,
      summaryMessage: 'Complaint form not loaded.',
    };
  }

  const items: ChecklistItem[] = [
    {
      id: 'customer_origin',
      label: 'Origin & Customer Identification',
      description: 'Source channel and reporting customer/entity recorded',
      fieldId: 'customer_name',
      passed: Boolean(
        complaint.complaint_source &&
        complaint.customer_name &&
        complaint.customer_name.trim().length >= 2
      ),
    },
    {
      id: 'product_id',
      label: 'Product Identification',
      description: 'Pharmaceutical drug product name recorded',
      fieldId: 'product_name',
      passed: Boolean(complaint.product_name && complaint.product_name.trim().length >= 2),
    },
    {
      id: 'batch_lot',
      label: 'Batch / Lot Traceability',
      description: 'Batch number specified for production recall & retention sample check',
      fieldId: 'batch_lot_number',
      passed: Boolean(complaint.batch_lot_number && complaint.batch_lot_number.trim().length >= 2),
    },
    {
      id: 'date_integrity',
      label: 'Chronological Date Integrity',
      description: 'Valid manufacturing date; manufacturing precedes expiry',
      fieldId: 'manufacturing_date',
      passed: (() => {
        if (!complaint.manufacturing_date) return false;
        const mfg = new Date(complaint.manufacturing_date);
        if (isNaN(mfg.getTime())) return false;
        const now = new Date();
        now.setHours(23, 59, 59, 999);
        if (mfg > now) return false;
        if (complaint.expiry_date) {
          const exp = new Date(complaint.expiry_date);
          if (isNaN(exp.getTime()) || mfg >= exp) return false;
        }
        return true;
      })(),
    },
    {
      id: 'quantity',
      label: 'Affected Quantity & Unit',
      description: 'Quantity specified with measurable units (e.g. capsules, vials, kg)',
      fieldId: 'affected_quantity',
      passed: Boolean(complaint.affected_quantity && complaint.affected_quantity.trim().length >= 2),
    },
    {
      id: 'categorization',
      label: 'QMS Defect Classification',
      description: 'Defect category assigned (e.g., Contamination, Packaging, Efficacy)',
      fieldId: 'complaint_category',
      passed: Boolean(complaint.complaint_category && complaint.complaint_category.trim()),
    },
    {
      id: 'description',
      label: 'Detailed Investigation Narrative',
      description: 'Comprehensive description of defect (minimum 20 characters)',
      fieldId: 'complaint_description',
      passed: Boolean(
        complaint.complaint_description &&
        complaint.complaint_description.trim().length >= 20
      ),
    },
    {
      id: 'risk_assessment',
      label: 'Severity & Priority Assignment',
      description: 'Criticality level and priority assessed for QA triage',
      fieldId: 'severity_suggested',
      passed: Boolean(
        complaint.severity_suggested &&
        complaint.severity_suggested !== 'Not Assessed' &&
        complaint.priority &&
        complaint.priority !== 'Not Assessed'
      ),
    },
  ];

  const passedChecks = items.filter((item) => item.passed).length;
  const totalChecks = items.length;
  const score = Math.round((passedChecks / totalChecks) * 100);
  const canCommit = passedChecks === totalChecks;

  let summaryMessage = '';
  if (canCommit) {
    summaryMessage = 'All QMS integrity checks satisfied. Ready for immutable ledger commitment.';
  } else {
    const missingCount = totalChecks - passedChecks;
    summaryMessage = `${missingCount} required QMS ${missingCount === 1 ? 'check' : 'checks'} remaining before commitment.`;
  }

  return {
    score,
    totalChecks,
    passedChecks,
    items,
    canCommit,
    summaryMessage,
  };
}
