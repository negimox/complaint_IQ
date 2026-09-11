import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, X } from 'lucide-react';
import './Dropzone.css';

interface DropzoneProps {
  onFileDrop: (file: File) => void;
  activeFile: File | null;
  onClearFile: () => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'message/rfc822': ['.eml'],
};

export default function Dropzone({ onFileDrop, activeFile, onClearFile, disabled }: DropzoneProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) onFileDrop(accepted[0]);
    },
    [onFileDrop]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 10 * 1024 * 1024, // 10 MB
    maxFiles: 1,
    disabled,
  });

  if (activeFile) {
    return (
      <div className="dropzone dropzone--file-attached">
        <FileText size={20} className="dropzone__file-icon" />
        <span className="dropzone__file-name text-body">{activeFile.name}</span>
        <button
          className="dropzone__clear-btn"
          onClick={onClearFile}
          aria-label="Remove file"
          disabled={disabled}
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`dropzone ${isDragActive ? 'dropzone--drag-over' : ''} ${disabled ? 'dropzone--disabled' : ''}`}
      aria-label="Drag and drop complaint document here, or click to browse"
    >
      <input {...getInputProps()} aria-live="polite" />
      <Upload size={28} className="dropzone__icon" />
      <p className="dropzone__text text-body">
        Drag &amp; drop complaint document here
      </p>
      <p className="dropzone__link">
        or <span className="dropzone__link-text">click to browse</span>
      </p>
      {fileRejections.length > 0 && (
        <p className="dropzone__error text-small">
          {fileRejections[0].errors[0]?.message ?? 'File not accepted'}
        </p>
      )}
    </div>
  );
}
