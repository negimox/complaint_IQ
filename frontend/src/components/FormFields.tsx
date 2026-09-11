import React from 'react';
import './FormFields.css';

interface BaseFieldProps {
  label: string;
  id: string;
  disabled?: boolean;
  className?: string;
  aiJustFilled?: boolean;
}

// ── TextField ─────────────────────────────────────────────────────────────────
interface TextFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
  placeholder?: string;
  multiline?: boolean;
  rows?: number;
}

export function TextField({
  label, id, value, onChange, disabled, className, aiJustFilled, multiline, rows = 4, placeholder,
}: TextFieldProps) {
  const cls = [
    'form-field',
    className,
    aiJustFilled ? 'field-just-filled' : '',
  ].filter(Boolean).join(' ');

  const inputProps = {
    id,
    disabled,
    className: 'form-field__input',
    value: value ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange?.(e.target.value),
    placeholder: placeholder ?? 'Awaiting AI extraction…',
  };

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">{label}</label>
      {multiline ? (
        <textarea {...inputProps} rows={rows} />
      ) : (
        <input {...inputProps} type="text" />
      )}
    </div>
  );
}

// ── SelectField ───────────────────────────────────────────────────────────────
interface SelectFieldProps extends BaseFieldProps {
  value: string | null;
  options: { value: string; label: string }[];
  onChange?: (val: string) => void;
}

export function SelectField({
  label, id, value, options, onChange, disabled, className, aiJustFilled,
}: SelectFieldProps) {
  const cls = [
    'form-field',
    className,
    aiJustFilled ? 'field-just-filled' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">{label}</label>
      <select
        id={id}
        disabled={disabled}
        className={`form-field__input form-field__select ${!value ? 'form-field__select--empty' : ''}`}
        value={value ?? ''}
        onChange={(e) => onChange?.(e.target.value)}
      >
        <option value="" disabled>Awaiting AI extraction…</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

// ── DateField ─────────────────────────────────────────────────────────────────
interface DateFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
}

export function DateField({ label, id, value, onChange, disabled, className, aiJustFilled }: DateFieldProps) {
  const cls = [
    'form-field',
    className,
    aiJustFilled ? 'field-just-filled' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">{label}</label>
      <input
        type="date"
        id={id}
        disabled={disabled}
        className={`form-field__input ${!value ? 'form-field__input--empty' : ''}`}
        value={value ?? ''}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder="Awaiting AI extraction…"
      />
    </div>
  );
}

// ── QuantityField ─────────────────────────────────────────────────────────────
interface QuantityFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
}

export function QuantityField({ label, id, value, onChange, disabled, className, aiJustFilled }: QuantityFieldProps) {
  const cls = [
    'form-field',
    className,
    aiJustFilled ? 'field-just-filled' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">{label}</label>
      <div className="form-field__quantity-wrapper">
        <input
          type="text"
          id={id}
          disabled={disabled}
          className="form-field__input"
          value={value ?? ''}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="Awaiting AI extraction…"
        />
        <span className="form-field__unit-suffix text-small">units</span>
      </div>
    </div>
  );
}
