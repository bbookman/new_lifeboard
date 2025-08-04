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

export const NavigationSidebar = ({ 
  items, 
  activeItem, 
  onItemClick,
  className 
}: NavigationSidebarProps) => {
  return (
    <nav className={`nav-sidebar ${className || ''}`}>
      <div>
        <div>
          {items.map((item) => (
            <button
              key={item.id}
              className={`nav-button ${activeItem === item.id ? 'active' : ''}`}
              onClick={() => onItemClick(item)}
              title={item.label}
            >
              {item.icon && (
                <span 
                  style={{ marginRight: '0.5rem' }}
                  role="img" 
                  aria-label={item.label}
                >
                  {item.icon}
                </span>
              )}
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
};