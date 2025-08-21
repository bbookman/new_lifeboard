interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  className?: string;
}

export const SectionHeader = ({
  title,
  subtitle,
  accentColor = 'border-news-accent',
  className,
}: SectionHeaderProps) => {
  return (
    <div className={`newspaper-section-header ${accentColor} ${className || ''}`}>
      <h2>{title}</h2>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
};
