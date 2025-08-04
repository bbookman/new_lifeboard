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
      </div>
    </div>
  );
};