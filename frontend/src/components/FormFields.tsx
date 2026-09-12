import React from 'react';
import { AlertCircle } from 'lucide-react';
import './FormFields.css';

export interface BaseFieldProps {
  label: string;
  id: string;
  disabled?: boolean;
  className?: string;
  aiJustFilled?: boolean;
  loading?: boolean;
  required?: boolean;
  error?: string | null;
  helperText?: string;
  onBlur?: () => void;
}

// ── TextField ─────────────────────────────────────────────────────────────────
export interface TextFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
  placeholder?: string;
  multiline?: boolean;
  rows?: number;
}

export function TextField({
  label,
  id,
  value,
  onChange,
  disabled,
  className,
  aiJustFilled,
  loading,
  required,
  error,
  helperText,
  onBlur,
  multiline,
  rows = 4,
  placeholder,
}: TextFieldProps) {
  const hasError = Boolean(error);
  const isFieldDisabled = disabled || loading;
  const cls = [
    'form-field',
    className,
    hasError ? 'form-field--error' : '',
    aiJustFilled ? 'field-just-filled' : '',
    loading ? 'form-field--extracting' : '',
  ].filter(Boolean).join(' ');

  const inputCls = [
    'form-field__input',
    hasError ? 'form-field__input--error' : '',
    loading ? 'form-field__input--extracting' : '',
  ].filter(Boolean).join(' ');

  const inputProps = {
    id,
    disabled: isFieldDisabled,
    className: inputCls,
    value: value ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange?.(e.target.value),
    onBlur: () => onBlur?.(),
    placeholder: loading ? 'Extracting from source document…' : (placeholder ?? 'Awaiting AI extraction…'),
    'aria-invalid': hasError,
    'aria-required': required,
    'aria-describedby': hasError ? `${id}-error` : helperText ? `${id}-helper` : undefined,
  };

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">
        {label}
        {required && <span className="form-field__label-required" aria-hidden="true">*</span>}
      </label>
      {multiline ? (
        <textarea {...inputProps} rows={rows} />
      ) : (
        <input {...inputProps} type="text" />
      )}
      {hasError ? (
        <div id={`${id}-error`} className="form-field__error-text" role="alert">
          <AlertCircle size={13} className="form-field__error-icon" />
          <span>{error}</span>
        </div>
      ) : helperText ? (
        <div id={`${id}-helper`} className="form-field__helper-text">
          {helperText}
        </div>
      ) : null}
    </div>
  );
}

// ── SelectField ───────────────────────────────────────────────────────────────
export interface SelectFieldProps extends BaseFieldProps {
  value: string | null;
  options: { value: string; label: string }[];
  onChange?: (val: string) => void;
}

export function SelectField({
  label,
  id,
  value,
  options,
  onChange,
  disabled,
  className,
  aiJustFilled,
  loading,
  required,
  error,
  helperText,
  onBlur,
}: SelectFieldProps) {
  const hasError = Boolean(error);
  const isFieldDisabled = disabled || loading;
  const cls = [
    'form-field',
    className,
    hasError ? 'form-field--error' : '',
    aiJustFilled ? 'field-just-filled' : '',
    loading ? 'form-field--extracting' : '',
  ].filter(Boolean).join(' ');

  const selectCls = [
    'form-field__input',
    'form-field__select',
    !value ? 'form-field__select--empty' : '',
    hasError ? 'form-field__input--error' : '',
    loading ? 'form-field__input--extracting' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">
        {label}
        {required && <span className="form-field__label-required" aria-hidden="true">*</span>}
      </label>
      <select
        id={id}
        disabled={isFieldDisabled}
        className={selectCls}
        value={value ?? ''}
        onChange={(e) => onChange?.(e.target.value)}
        onBlur={() => onBlur?.()}
        aria-invalid={hasError}
        aria-required={required}
        aria-describedby={hasError ? `${id}-error` : helperText ? `${id}-helper` : undefined}
      >
        <option value="" disabled>
          {loading ? 'AI extracting…' : 'Awaiting AI extraction…'}
        </option>
        {value && !options.some((opt) => opt.value === value) && (
          <option value={value}>{value}</option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      {hasError ? (
        <div id={`${id}-error`} className="form-field__error-text" role="alert">
          <AlertCircle size={13} className="form-field__error-icon" />
          <span>{error}</span>
        </div>
      ) : helperText ? (
        <div id={`${id}-helper`} className="form-field__helper-text">
          {helperText}
        </div>
      ) : null}
    </div>
  );
}

// ── DateField ─────────────────────────────────────────────────────────────────
export interface DateFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
  max?: string;
  min?: string;
}

export function DateField({
  label,
  id,
  value,
  onChange,
  disabled,
  className,
  aiJustFilled,
  loading,
  required,
  error,
  helperText,
  onBlur,
  max,
  min,
}: DateFieldProps) {
  const hasError = Boolean(error);
  const isFieldDisabled = disabled || loading;
  const cls = [
    'form-field',
    className,
    hasError ? 'form-field--error' : '',
    aiJustFilled ? 'field-just-filled' : '',
    loading ? 'form-field--extracting' : '',
  ].filter(Boolean).join(' ');

  const inputCls = [
    'form-field__input',
    !value ? 'form-field__input--empty' : '',
    hasError ? 'form-field__input--error' : '',
    loading ? 'form-field__input--extracting' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">
        {label}
        {required && <span className="form-field__label-required" aria-hidden="true">*</span>}
      </label>
      <input
        type="date"
        id={id}
        disabled={isFieldDisabled}
        className={inputCls}
        value={value ?? ''}
        max={max}
        min={min}
        onChange={(e) => onChange?.(e.target.value)}
        onBlur={() => onBlur?.()}
        placeholder={loading ? 'Extracting…' : 'Awaiting AI extraction…'}
        aria-invalid={hasError}
        aria-required={required}
        aria-describedby={hasError ? `${id}-error` : helperText ? `${id}-helper` : undefined}
      />
      {hasError ? (
        <div id={`${id}-error`} className="form-field__error-text" role="alert">
          <AlertCircle size={13} className="form-field__error-icon" />
          <span>{error}</span>
        </div>
      ) : helperText ? (
        <div id={`${id}-helper`} className="form-field__helper-text">
          {helperText}
        </div>
      ) : null}
    </div>
  );
}

// ── QuantityField ─────────────────────────────────────────────────────────────
export interface QuantityFieldProps extends BaseFieldProps {
  value: string | null;
  onChange?: (val: string) => void;
}

export function QuantityField({
  label,
  id,
  value,
  onChange,
  disabled,
  className,
  aiJustFilled,
  loading,
  required,
  error,
  helperText,
  onBlur,
}: QuantityFieldProps) {
  const hasError = Boolean(error);
  const isFieldDisabled = disabled || loading;
  const cls = [
    'form-field',
    className,
    hasError ? 'form-field--error' : '',
    aiJustFilled ? 'field-just-filled' : '',
    loading ? 'form-field--extracting' : '',
  ].filter(Boolean).join(' ');

  const inputCls = [
    'form-field__input',
    hasError ? 'form-field__input--error' : '',
    loading ? 'form-field__input--extracting' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={cls}>
      <label htmlFor={id} className="form-field__label text-label">
        {label}
        {required && <span className="form-field__label-required" aria-hidden="true">*</span>}
      </label>
      <div className="form-field__quantity-wrapper">
        <input
          type="text"
          id={id}
          disabled={isFieldDisabled}
          className={inputCls}
          value={value ?? ''}
          onChange={(e) => onChange?.(e.target.value)}
          onBlur={() => onBlur?.()}
          placeholder={loading ? 'Extracting quantity…' : 'Awaiting AI extraction… (e.g. 12 bottles)'}
          aria-invalid={hasError}
          aria-required={required}
          aria-describedby={hasError ? `${id}-error` : helperText ? `${id}-helper` : undefined}
        />
        <span className="form-field__unit-suffix text-small">units</span>
      </div>
      {hasError ? (
        <div id={`${id}-error`} className="form-field__error-text" role="alert">
          <AlertCircle size={13} className="form-field__error-icon" />
          <span>{error}</span>
        </div>
      ) : helperText ? (
        <div id={`${id}-helper`} className="form-field__helper-text">
          {helperText}
        </div>
      ) : null}
    </div>
  );
}
