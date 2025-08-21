import type { ReactNode } from 'react';
import { NewspaperMasthead } from './NewspaperMasthead';

interface NewspaperLayoutProps {
  children: ReactNode;
  showMasthead?: boolean;
  className?: string;
  selectedDate?: string;
}

export const NewspaperLayout = ({ children, showMasthead = true, className, selectedDate }: NewspaperLayoutProps) => {
  return (
    <div className={className} style={{ minHeight: '100vh' }}>
      {showMasthead && <NewspaperMasthead selectedDate={selectedDate} />}

      <div className="container" style={{ paddingBottom: '3rem' }}>
        {children}
      </div>
    </div>
  );
};
