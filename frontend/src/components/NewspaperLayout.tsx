import type { ReactNode } from "react";
import { NewspaperMasthead } from "./NewspaperMasthead";

interface NewspaperLayoutProps {
  children: ReactNode;
  showMasthead?: boolean;
  className?: string;
}

export const NewspaperLayout = ({ 
  children, 
  showMasthead = true,
  className 
}: NewspaperLayoutProps) => {
  return (
    <div className={className} style={{ minHeight: '100vh' }}>
      {showMasthead && <NewspaperMasthead />}
      
      <div className="container" style={{ paddingBottom: '3rem' }}>
        {children}
        
        {/* Footer */}
        <footer style={{ marginTop: '3rem', paddingTop: '2rem', borderTop: '1px solid #ddd' }}>
          <div className="text-center">
            <p className="text-sm text-muted">
              Lifeboard
            </p>
            <p style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.25rem' }}>
              Curated from your conversations, activities, and daily moments
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
};