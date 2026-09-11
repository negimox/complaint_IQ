import React from 'react';
import './SectionCard.css';

interface SectionCardProps {
  number: number;
  title: string;
  children: React.ReactNode;
}

export default function SectionCard({ number, title, children }: SectionCardProps) {
  return (
    <div className="section-card">
      <div className="section-card__header">
        <span className="section-card__number">{number}.</span>
        <span className="section-card__title text-section-label">{title}</span>
      </div>
      <div className="section-card__body">{children}</div>
    </div>
  );
}
