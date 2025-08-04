export const NewspaperMasthead = () => {
  const currentDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  return (
    <header className="newspaper-masthead">
      <div className="container">
        <div className="text-center">
          <h1>LIFEBOARD</h1>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', fontSize: '0.875rem', fontWeight: '500' }}>
            <span>{currentDate}</span>
          </div>
        </div>
      </div>
    </header>
  );
};