import mastheadImage from "@/assets/newspaper-masthead.jpg";

interface NewspaperMastheadProps {
  selectedDate?: string;
}

export const NewspaperMasthead = ({ selectedDate }: NewspaperMastheadProps) => {
  const displayDate = selectedDate ? new Date(selectedDate + 'T00:00:00') : new Date();
  const formattedDate = displayDate.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });

  return (
    <header className="bg-gradient-to-r from-newspaper-masthead to-newspaper-masthead/90 text-white py-6 mb-8">
      <div className="container mx-auto px-4">
        <div className="text-center">
          <h1 className="font-headline text-lg font-black tracking-tight mb-2" >
            LIFEBOARD
          </h1>
          <div className="flex items-center justify-center space-x-4 text-lg font-body font-medium">
            <span>{formattedDate}</span>
          </div>
        </div>
      </div>
    </header>
  );
};