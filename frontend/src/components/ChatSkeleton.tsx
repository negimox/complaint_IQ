import React from 'react';
import './ChatSkeleton.css';

export default function ChatSkeleton() {
  return (
    <div className="chat-skeleton" aria-label="Loading chat history" role="status">
      <div className="chat-skeleton__status">
        <span className="chat-skeleton__pulse-dot" />
        <span className="text-small">Restoring conversation history from QMS ledger…</span>
      </div>

      {/* Assistant bubble skeleton */}
      <div className="chat-skeleton__bubble chat-skeleton__bubble--assistant">
        <div className="chat-skeleton__avatar" />
        <div className="chat-skeleton__lines">
          <div className="chat-skeleton__line" style={{ width: '85%' }} />
          <div className="chat-skeleton__line" style={{ width: '60%' }} />
        </div>
      </div>

      {/* User bubble skeleton */}
      <div className="chat-skeleton__bubble chat-skeleton__bubble--user">
        <div className="chat-skeleton__lines chat-skeleton__lines--user">
          <div className="chat-skeleton__line chat-skeleton__line--user" style={{ width: '70%' }} />
        </div>
      </div>

      {/* Assistant bubble skeleton */}
      <div className="chat-skeleton__bubble chat-skeleton__bubble--assistant">
        <div className="chat-skeleton__avatar" />
        <div className="chat-skeleton__lines">
          <div className="chat-skeleton__line" style={{ width: '92%' }} />
          <div className="chat-skeleton__line" style={{ width: '78%' }} />
          <div className="chat-skeleton__line" style={{ width: '45%' }} />
        </div>
      </div>
    </div>
  );
}
