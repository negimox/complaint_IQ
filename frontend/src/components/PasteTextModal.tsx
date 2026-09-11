import { useState, useRef, useEffect } from 'react';
import { Clipboard, X } from 'lucide-react';
import './PasteTextModal.css';

interface PasteTextModalProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export default function PasteTextModal({ onSubmit, disabled }: PasteTextModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap + auto-focus textarea when opened
  useEffect(() => {
    if (isOpen) textareaRef.current?.focus();
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) setIsOpen(false);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen]);

  const handleSubmit = () => {
    if (text.trim()) {
      onSubmit(text.trim());
      setText('');
      setIsOpen(false);
    }
  };

  return (
    <>
      <button
        className="paste-btn"
        onClick={() => setIsOpen(true)}
        disabled={disabled}
        id="paste-complaint-btn"
      >
        <Clipboard size={16} />
        Paste Complaint Text / Email
      </button>

      {isOpen && (
        <div
          className="paste-modal-overlay"
          onClick={(e) => { if (e.target === e.currentTarget) setIsOpen(false); }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="paste-modal-title"
        >
          <div className="paste-modal" ref={dialogRef}>
            <div className="paste-modal__header">
              <h2 id="paste-modal-title" className="text-h2">Paste Complaint Text</h2>
              <button
                className="paste-modal__close"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="paste-modal__body">
              <p className="text-small paste-modal__hint">
                Paste an email, text report, or any unstructured complaint description below.
                The AI will extract all relevant fields automatically.
              </p>
              <textarea
                ref={textareaRef}
                className="paste-modal__textarea"
                placeholder="e.g. Apollo Pharmacy reported 12 discolored capsules in a sealed bottle of Amoxicillin 500mg, Batch BMX240601..."
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={10}
              />
            </div>
            <div className="paste-modal__footer">
              <button
                className="btn-secondary"
                onClick={() => { setIsOpen(false); setText(''); }}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleSubmit}
                disabled={!text.trim()}
                id="paste-modal-submit-btn"
              >
                Extract &amp; Populate Form
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
