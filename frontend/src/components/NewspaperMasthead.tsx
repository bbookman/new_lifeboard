import mastheadImage from "@/assets/newspaper-masthead.jpg";

export const NewspaperMasthead = () => {
  const currentDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  return (
    <header className="bg-gradient-to-r from-newspaper-masthead to-newspaper-masthead/90 text-white py-6 mb-8">
      <div className="container mx-auto px-4">
        <div className="text-center">
          <h1 className="font-headline text-6xl md:text-8xl font-black tracking-tight mb-2">
            THE DAILY DIGEST
          </h1>
          <div className="flex items-center justify-center space-x-4 text-sm font-body font-medium">
            <span>{currentDate}</span>
            <span>•</span>
            <span>Your Personalized News</span>
            <span>•</span>
            <span>Edition No. {Math.floor(Math.random() * 1000) + 1}</span>
          </div>
        </div>
      </div>
    </header>
  );
};