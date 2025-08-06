import React, { useEffect } from 'react';

/**
 * GridShell.tsx
 *
 * Enforces a robust two-column responsive grid with defensive width utilities.
 * Left and right areas are provided as React nodes to keep layout concerns isolated.
 * Includes temporary diagnostics to verify active breakpoint and container width.
 */
export interface GridShellProps {
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
}

function logGridMetrics(): void {
  try {
    const container = document.querySelector('[data-grid-shell="container"]') as HTMLElement | null;
    const grid = document.querySelector('[data-grid-shell="grid"]') as HTMLElement | null;
    const cw = container?.getBoundingClientRect().width ?? -1;
    const gw = grid?.getBoundingClientRect().width ?? -1;
    const ww = window.innerWidth;
    const isSmActive = cw >= 640 || gw >= 640 || ww >= 640;
    // eslint-disable-next-line no-console
    console.log('[GridShell] widths', { window: ww, container: cw, grid: gw, isSmActive });
  } catch (e) {
    // eslint-disable-next-line no-console
    console.log('[GridShell] metrics error', e);
  }
}

export const GridShell = ({ left, right, className }: GridShellProps) => {
  useEffect(() => {
    logGridMetrics();
    const onResize = () => logGridMetrics();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <div
      data-grid-shell="container"
      className={["container mx-auto w-full min-w-0 overflow-visible", className].filter(Boolean).join(" ")}
    >
      <div data-grid-shell="grid" className="flex gap-8">
        <div className="flex-[2] border-r border-gray-200 pr-8 min-w-0">
          {left}
        </div>
        <div className="flex-1 min-w-0">
          {right}
        </div>
      </div>
    </div>
  );
};

export default GridShell;