export interface NavigationItem {
  id: string;
  label: string;
  icon?: string;
  path: string;
}

interface NavigationSidebarProps {
  items: NavigationItem[];
  activeItem?: string;
  onItemClick: (item: NavigationItem) => void;
  className?: string;
}

export const NavigationSidebar = ({ items, activeItem, onItemClick, className }: NavigationSidebarProps) => {
  return (
    <nav className={`border-b border-newspaper-divider bg-background ${className || ''}`}>
      <div className="container mx-auto px-4">
        <div className="flex space-x-8 py-4">
          {items.map((item) => (
            <button
              key={item.id}
              className={`nav-horizontal-button font-body text-sm transition-colors ${
                activeItem === item.id
                  ? 'text-newspaper-masthead font-semibold border-b-2 border-news-accent'
                  : 'text-newspaper-byline hover:text-newspaper-headline'
              }`}
              onClick={() => onItemClick(item)}
              title={item.label}
            >
              {item.icon && (
                <span role="img" aria-label={item.label} className="mr-2">
                  {item.icon}
                </span>
              )}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
};
