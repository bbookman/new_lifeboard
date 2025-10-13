import { useEffect, useState } from 'react';

interface YelpReviewsProps {
  selectedDate?: string;
}

interface YelpReview {
  id: string;
  business_name: string;
  rating: number;
  comment: string;
  review_date: string;
  days_date: string;
}

const renderStars = (rating: number) => {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  return (
    <span className="text-yellow-500">
      {'★'.repeat(fullStars)}
      {hasHalfStar && '⯨'}
      {'☆'.repeat(emptyStars)}
    </span>
  );
};

export const YelpReviews = ({ selectedDate }: YelpReviewsProps) => {
  const [reviews, setReviews] = useState<YelpReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReviews = async () => {
      if (!selectedDate) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/data_items?namespace=yelp&date=${selectedDate}`);

        if (!response.ok) {
          throw new Error(`Failed to fetch Yelp reviews: ${response.status}`);
        }

        const data = await response.json();

        // Parse metadata for each item
        const parsedReviews = data.map((item: any) => {
          let metadata;
          try {
            metadata = typeof item.metadata === 'string'
              ? JSON.parse(item.metadata)
              : item.metadata;
          } catch (e) {
            console.error('Failed to parse metadata for item:', item.id);
            metadata = {};
          }

          return {
            id: item.id,
            business_name: metadata.business_name || 'Unknown Business',
            rating: metadata.rating || 0,
            comment: metadata.comment || '',
            review_date: metadata.review_date || '',
            days_date: item.days_date || ''
          };
        });

        setReviews(parsedReviews);
      } catch (err) {
        console.error('Error fetching Yelp reviews:', err);
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchReviews();
  }, [selectedDate]);

  // Loading state
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="border-b-2 border-yellow-500 pb-2">
          <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
            Yelp Reviews
          </h2>
          <p className="text-newspaper-byline font-body text-sm">
            Your restaurant reviews and dining history
            {selectedDate && ` • ${selectedDate}`}
          </p>
        </div>

        <div className="card p-6 bg-gradient-to-r from-yellow-50 to-yellow-100">
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-yellow-500"></div>
            <span className="ml-3 text-newspaper-byline">Loading your reviews...</span>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="border-b-2 border-yellow-500 pb-2">
          <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
            Yelp Reviews
          </h2>
          <p className="text-newspaper-byline font-body text-sm">
            Your restaurant reviews and dining history
            {selectedDate && ` • ${selectedDate}`}
          </p>
        </div>

        <div className="card p-6 bg-gradient-to-r from-yellow-50 to-yellow-100">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-red-500 mb-2">⚠️</div>
              <p className="text-newspaper-byline mb-4">
                Failed to load reviews: {error}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Empty state
  if (!reviews || reviews.length === 0) {
    return null; // Don't show anything if no reviews
  }

  // Success state with reviews
  return (
    <div className="space-y-6">
      <div className="border-b-2 border-yellow-500 pb-2">
        <h2 className="font-headline text-3xl font-bold text-newspaper-headline">
          Yelp Reviews
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          Your restaurant reviews and dining history
          {selectedDate && ` • ${selectedDate}`}
        </p>
      </div>

      <div className="card p-6 bg-gradient-to-r from-yellow-50 to-yellow-100">
        <div className="space-y-6">
          {reviews.map((review) => (
            <div key={review.id} className="bg-white rounded-lg shadow-sm p-4">
              <div className="flex items-center gap-2 mb-2">
                <h3 className="font-headline text-xl font-bold text-newspaper-headline">
                  {review.business_name}
                </h3>
                {renderStars(review.rating)}
              </div>
              <p className="text-newspaper-body font-body leading-relaxed">
                {review.comment}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
