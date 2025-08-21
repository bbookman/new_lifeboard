import React from 'react';

/**
 * NewsPanel.tsx
 *
 * Renders a list of news articles. Receives data via props.
 * No layout or data fetching here—pure presentation.
 */
export interface NewsArticle {
  id: number;
  title: string;
  link?: string;
  snippet?: string;
  thumbnail_url?: string;
  published_datetime_utc?: string;
}

export interface NewsPanelProps {
  articles: NewsArticle[];
  loading: boolean;
}

export const NewsPanel = ({ articles, loading }: NewsPanelProps) => {
  return (
    <div className="space-y-6">
      <div>
        {loading && <div className="text-center py-4 text-gray-600">Loading news...</div>}

        {!loading && articles && articles.length > 0 && (
          <div className="space-y-6">
            {articles.map((article, index) => (
              <div
                key={article.id || index}
                className={`overflow-hidden hover:shadow-lg transition-shadow ${index === 0 ? 'border-l-4 border-l-red-500 pl-4' : ''}`}
              >
                {article.thumbnail_url && (
                  <div className="mb-3">
                    <img
                      src={article.thumbnail_url}
                      alt={article.title}
                      className="w-full h-40 object-cover rounded-lg"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none';
                      }}
                    />
                  </div>
                )}
                <h3 className="font-semibold text-base text-gray-800 leading-tight mb-2 hover:text-blue-600">
                  {article.link ? (
                    <a href={article.link} target="_blank" rel="noopener noreferrer" className="transition-colors">
                      {article.title}
                    </a>
                  ) : (
                    article.title
                  )}
                </h3>
                {article.snippet && <p className="text-sm text-gray-600 leading-relaxed mb-3">{article.snippet}</p>}
                {article.published_datetime_utc && (
                  <div className="text-xs text-gray-500 border-b border-gray-200 pb-4 mb-4 last:border-b-0 last:pb-0 last:mb-0">
                    {new Date(article.published_datetime_utc).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && (!articles || articles.length === 0) && (
          <div className="text-center py-4 text-gray-600">No news available for this date</div>
        )}
      </div>
    </div>
  );
};

export default NewsPanel;
