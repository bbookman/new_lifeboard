import { Card } from "@/components/ui/card";

interface Photo {
  id: string;
  url: string;
  caption: string;
  timestamp: string;
  location?: string;
}

const samplePhotos: Photo[] = [
  {
    id: "1",
    url: "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?w=400&h=300&fit=crop",
    caption: "Morning coffee ritual",
    timestamp: "8:30 AM",
    location: "Home"
  },
  {
    id: "2",
    url: "https://images.unsplash.com/photo-1470813740244-df37b8c1edcb?w=400&h=300&fit=crop",
    caption: "Evening walk under the stars",
    timestamp: "7:45 PM",
    location: "City Park"
  },
  {
    id: "3",
    url: "https://images.unsplash.com/photo-1473091534298-04dcbce3278c?w=400&h=300&fit=crop",
    caption: "Working on new projects",
    timestamp: "2:15 PM",
    location: "Office"
  },
  {
    id: "4",
    url: "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=400&h=300&fit=crop",
    caption: "Late night coding session",
    timestamp: "11:30 PM",
    location: "Home Office"
  }
];

export const PhotoGallery = () => {
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-photo-accent pb-2">
        <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
          Visual Diary
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          Moments captured throughout your day
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {samplePhotos.map((photo) => (
          <Card key={photo.id} className="overflow-hidden hover:shadow-lg transition-shadow group">
            <div className="aspect-[4/3] relative overflow-hidden">
              <img 
                src={photo.url} 
                alt={photo.caption}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
              <div className="absolute top-3 right-3">
                <span className="bg-black/70 text-white px-2 py-1 rounded text-xs font-body">
                  {photo.timestamp}
                </span>
              </div>
            </div>
            
            <div className="p-4">
              <h3 className="font-body font-semibold text-newspaper-headline mb-1">
                {photo.caption}
              </h3>
              {photo.location && (
                <p className="text-newspaper-byline text-sm flex items-center">
                  📍 {photo.location}
                </p>
              )}
            </div>
          </Card>
        ))}
      </div>
      
      <div className="text-center">
        <button className="font-body text-photo-accent hover:text-photo-accent/80 transition-colors text-sm font-medium">
          View All Photos →
        </button>
      </div>
    </div>
  );
};