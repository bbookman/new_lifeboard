import { Card } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, Clock, ExternalLink, UserCircle } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Data type definitions
export interface DailySummaryData {
  type: "daily-summary";
  date: string;
  totalItems: number;
  highlights: string[];
  keyThemes: string[];
  moodScore: number;
  weatherSummary: string;
  // Optional properties for LLM-generated content
  generatedContent?: string;
  generationTime?: number;
  modelInfo?: Record<string, any>;
  cached?: boolean;
}

export interface ContentItemData {
  type: "content-item";
  id: string;
  username?: string;
  handle?: string;
  content: string;
  timestamp: string;
  likes?: number;
  retweets?: number;
  verified?: boolean;
  source: "twitter" | "news" | "limitless" | "music" | "photo";
  url?: string;
  hasMedia?: boolean;
  mediaUrl?: string;
}

export interface LimitlessContentData {
  type: "limitless";
  id: string;
  title?: string;
  timestamp: string;
  displayConversation: ConversationNode[];
  semanticClusters: Record<string, SemanticClusterData>;
  semanticMetadata: {
    totalLines: number;
    clusteredLines: number;
    uniqueThemes: string[];
    semanticDensity: number;
    clustersFound: number;
  };
}

interface ConversationNode {
  content: string;
  speaker: string;
  timestamp: string;
  type: string;
  representsCluster?: string;
  hiddenVariations?: number;
  isDeduplicated?: boolean;
  isUnique?: boolean;
  canonicalConfidence?: number;
  replacedOriginal?: string;
}

interface SemanticClusterData {
  theme: string;
  canonical: string;
  variations: Array<{
    text: string;
    speaker: string;
    similarity: number;
    timestamp: string;
  }>;
  frequency: number;
  confidence: number;
}

export type CardData = DailySummaryData | ContentItemData | LimitlessContentData;

interface ContentCardProps {
  data: CardData;
  className?: string;
}

const DailySummaryContent = ({ data }: { data: DailySummaryData }) => {
  const [showFullContent, setShowFullContent] = useState(false);

  // If we have generated content, show it instead of the structured format
  if (data.generatedContent) {
    return (
      <div className="space-y-4">
        {/* Header with AI badge and metadata */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-800">
              🤖 AI Summary
            </Badge>
            {data.cached && (
              <Badge variant="outline" className="text-xs">
                Cached
              </Badge>
            )}
          </div>
          
        </div>

        {/* Full generated content */}
        <div className="prose prose-sm max-w-none text-newspaper-headline
          prose-headings:text-newspaper-headline
          prose-p:text-newspaper-headline
          prose-p:leading-relaxed
          prose-ul:list-disc
          prose-ul:pl-6
          prose-li:mb-1
          prose-strong:text-newspaper-headline
          prose-strong:font-semibold">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {data.generatedContent}
          </ReactMarkdown>
        </div>

        {/* Model information */}
        {data.modelInfo && (
          <div className="flex items-center justify-between pt-3 border-t border-gray-200 text-xs text-gray-500">
            <span>
              Model: {data.modelInfo.model || 'Unknown'} 
              ({data.modelInfo.provider || 'Unknown'})
            </span>
            <span>
              Date: {data.date}
            </span>
          </div>
        )}
      </div>
    );
  }

  // Fallback to structured format for backward compatibility
  return (
    <div className="space-y-4">
      {/* Weather Summary */}
      <div>
        <h3 className="font-body font-semibold text-newspaper-headline mb-2">Weather</h3>
        <p className="font-body text-newspaper-byline text-sm">{data.weatherSummary}</p>
      </div>

      {/* Key Highlights */}
      <div>
        <h3 className="font-body font-semibold text-newspaper-headline mb-2">Highlights</h3>
        <ul className="space-y-1">
          {data.highlights.map((highlight, index) => (
            <li key={index} className="font-body text-newspaper-byline text-sm flex items-start">
              <span className="text-primary mr-2">•</span>
              {highlight}
            </li>
          ))}
        </ul>
      </div>

      {/* Key Themes */}
      <div>
        <h3 className="font-body font-semibold text-newspaper-headline mb-2">Themes</h3>
        <div className="flex flex-wrap gap-2">
          {data.keyThemes.map((theme, index) => (
            <Badge key={index} variant="secondary" className="text-xs">
              {theme}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
};

const ContentItemContent = ({ data }: { data: ContentItemData }) => {
  const getSourceAccentColor = (source: string) => {
    switch (source) {
      case 'twitter': return 'social-accent';
      case 'news': return 'news-accent';
      case 'music': return 'music-accent';
      case 'photo': return 'photo-accent';
      default: return 'primary';
    }
  };

  const extractTitle = (content: string) => {
    // Extract title from content (first line before \n\n)
    const lines = content.split('\n\n');
    return lines[0] || content;
  };

  const extractContentWithoutTitle = (content: string) => {
    // Extract content without the title (everything after first \n\n)
    const lines = content.split('\n\n');
    return lines.slice(1).join('\n\n') || '';
  };

  const accentColor = getSourceAccentColor(data.source);

  return (
    <div className="flex space-x-3 h-full">
      <div className="flex-1 flex flex-col h-full">
        {data.content && (
          <>
            <div className="flex items-center space-x-2 mb-1">
              {data.url ? (
                <a 
                  href={data.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="font-body font-semibold text-blue-600 underline text-base"
                >
                  {extractTitle(data.content)}
                </a>
              ) : (
                <span className="font-body font-semibold text-newspaper-headline text-base">
                  {extractTitle(data.content)}
                </span>
              )}
            </div>
          
            <div className={`font-body text-newspaper-headline leading-relaxed mb-3 ${!data.hasMedia ? 'flex-1 flex items-center' : ''}`}>
              <p className={`${!data.hasMedia ? 'text-lg' : 'text-base'}`}>
                {extractContentWithoutTitle(data.content)}
              </p>
            </div>

            {/* Display media if available - fill remaining space */}
            {data.hasMedia && data.mediaUrl && (
              <div className="flex-1 flex flex-col mb-3">
                <div className="flex-1 bg-gray-100 p-4 rounded-lg border-2 border-blue-200 flex items-center justify-center">
                  <img 
                    src={data.mediaUrl}
                    alt="Tweet media"
                    className="max-w-full max-h-full rounded-lg border-2 border-red-500 hover:opacity-90 transition-opacity cursor-pointer"
                    style={{ 
                      backgroundColor: '#e5e7eb',
                      objectFit: 'contain',
                      display: 'block'
                    }}
                    onClick={() => {
                      // Open image in new tab when clicked
                      window.open(data.mediaUrl, '_blank');
                    }}
                    onLoad={(e) => {
                      console.log(`✅ [ContentCard] Successfully loaded media: ${data.mediaUrl}`);
                      console.log(`✅ [ContentCard] Image dimensions: ${e.currentTarget.naturalWidth}x${e.currentTarget.naturalHeight}`);
                      const target = e.currentTarget as HTMLImageElement;
                      target.style.backgroundColor = 'white';
                      target.style.borderColor = '#10b981'; // Green border when loaded
                    }}
                    onError={(e) => {
                      console.error(`❌ [ContentCard] Failed to load media: ${data.mediaUrl}`);
                      console.error(`❌ [ContentCard] Error event:`, e);
                      
                      // Test the URL directly
                      fetch(data.mediaUrl!, { method: 'HEAD', mode: 'no-cors' })
                        .then(() => console.log(`🌐 [ContentCard] URL is accessible via fetch: ${data.mediaUrl}`))
                        .catch(err => console.error(`🌐 [ContentCard] URL failed via fetch: ${data.mediaUrl}`, err));
                      
                      const target = e.currentTarget as HTMLImageElement;
                      target.style.borderColor = '#ef4444'; // Red border on error
                      target.style.backgroundColor = '#fef2f2'; // Light red background
                      
                      // Show error message instead of broken image
                      const errorDiv = document.createElement('div');
                      errorDiv.textContent = `Failed to load image: ${data.mediaUrl}`;
                      errorDiv.style.cssText = 'padding: 10px; text-align: center; color: #ef4444; font-size: 12px; word-break: break-all;';
                      target.style.display = 'none';
                      target.parentNode?.appendChild(errorDiv);
                    }}
                  />
                </div>
              </div>
            )}

            {/* Debug: Show if hasMedia but no mediaUrl */}
            {data.hasMedia && !data.mediaUrl && (
              <div className="mb-3 bg-yellow-50 p-2 rounded-lg text-xs text-yellow-700">
                ⚠️ Has media but no URL available
              </div>
            )}
          
            {(data.likes !== undefined || data.retweets !== undefined) && (
              <div className="flex space-x-6 text-newspaper-byline text-sm">
                {data.likes !== undefined && (
                  <span className={`hover:text-${accentColor} cursor-pointer transition-colors`}>
                    ♡ {data.likes.toLocaleString()}
                  </span>
                )}
                {data.retweets !== undefined && (
                  <span className={`hover:text-${accentColor} cursor-pointer transition-colors`}>
                    ↻ {data.retweets.toLocaleString()}
                  </span>
                )}
                <span className={`hover:text-${accentColor} cursor-pointer transition-colors`}>
                  ⤴ Share
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

const LimitlessContent = ({ data }: { data: LimitlessContentData }) => {
  const [viewMode, setViewMode] = useState<'condensed' | 'full'>('condensed');
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [isRegenerating, setIsRegenerating] = useState(false);

  const toggleClusterExpansion = (clusterId: string) => {
    const newExpanded = new Set(expandedClusters);
    if (newExpanded.has(clusterId)) {
      newExpanded.delete(clusterId);
    } else {
      newExpanded.add(clusterId);
    }
    setExpandedClusters(newExpanded);
  };

  const handleExpandContent = () => {
    const contentData = encodeURIComponent(JSON.stringify(data));
    window.open(`/limitless-content/${data.id}?data=${contentData}`, '_blank');
  };

  const handleRegenerateSpeakerLabels = async () => {
    try {
      setIsRegenerating(true);

      // Extract date from timestamp (format: YYYY-MM-DD)
      const daysDate = data.timestamp.split('T')[0];

      const response = await fetch('https://localhost:8000/api/speaker-labeling/regenerate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ days_date: daysDate }),
      });

      if (!response.ok) {
        throw new Error(`Failed to regenerate speaker labels: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Speaker labeling regeneration result:', result);

      // Show success message and reload after a short delay
      alert(`Speaker labels regenerated successfully!\n\nItems improved: ${result.items_improved}\nItems skipped: ${result.items_skipped}\n\nThe page will reload to show updated content.`);
      window.location.reload();
    } catch (error) {
      console.error('Error regenerating speaker labels:', error);
      alert('Failed to regenerate speaker labels. Please try again.');
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with title and controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-headline text-lg font-semibold text-newspaper-headline">
            {data.title || "Conversation"}
          </h3>
          <div className="flex items-center space-x-2 mt-1">
            <Clock className="w-3 h-3 text-newspaper-byline" />
            <span className="text-xs text-newspaper-byline">{data.timestamp}</span>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant="secondary" className="text-xs">
            {data.semanticMetadata.clusteredLines} of {data.semanticMetadata.totalLines} lines
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setViewMode(viewMode === 'condensed' ? 'full' : 'condensed')}
          >
            {viewMode === 'condensed' ? 'Show Full' : 'Show Condensed'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRegenerateSpeakerLabels}
            disabled={isRegenerating}
            className="p-2 bg-white hover:bg-gray-50 border-gray-200"
            title="Regenerate speaker labels"
          >
            <UserCircle className={`w-4 h-4 text-gray-600 ${isRegenerating ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExpandContent}
            className="p-2 bg-white hover:bg-gray-50 border-gray-200"
            title="Open in new page"
          >
            <ExternalLink className="w-4 h-4 text-gray-600" />
          </Button>
        </div>
      </div>
      
      {/* Semantic density indicator */}
      <div className="space-y-1">
        <div className="w-full bg-muted rounded-full h-2">
          <div 
            className="bg-primary h-2 rounded-full transition-all"
            style={{ width: `${data.semanticMetadata.semanticDensity * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Semantic density: {Math.round(data.semanticMetadata.semanticDensity * 100)}%</span>
          <span>{data.semanticMetadata.clustersFound} patterns found</span>
        </div>
      </div>
      
      {/* Conversation content */}
      <div className="space-y-3">
        {data.displayConversation.map((node, index) => (
          <ConversationNode
            key={`${node.speaker}-${index}`}
            node={node}
            clusters={data.semanticClusters}
            expanded={expandedClusters.has(node.representsCluster || '')}
            onToggleExpand={toggleClusterExpansion}
          />
        ))}
      </div>
      
      {/* Theme summary */}
      {data.semanticMetadata.uniqueThemes.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-3 border-t border-muted">
          <span className="text-xs text-muted-foreground font-medium">Themes:</span>
          {data.semanticMetadata.uniqueThemes.map(theme => (
            <Badge key={theme} variant="outline" className="text-xs">
              {theme.replace('_', ' ')}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
};

const ConversationNode = ({ 
  node, 
  clusters, 
  expanded, 
  onToggleExpand 
}: {
  node: ConversationNode;
  clusters: Record<string, SemanticClusterData>;
  expanded: boolean;
  onToggleExpand: (clusterId: string) => void;
}) => {
  const cluster = node.representsCluster ? clusters[node.representsCluster] : null;
  
  return (
    <div className="conversation-node">
      <div className="flex items-start space-x-3">
        <Avatar className="w-8 h-8 flex-shrink-0">
          <div className="w-full h-full bg-social-accent rounded-full flex items-center justify-center">
            <span className="text-white font-bold text-sm">
              {node.speaker?.charAt(0) || '?'}
            </span>
          </div>
        </Avatar>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-1">
            <span className="font-semibold text-sm text-newspaper-headline">{node.speaker}</span>
            <span className="text-xs text-newspaper-byline">
              {new Date(node.timestamp).toLocaleTimeString()}
            </span>
            
            {node.isDeduplicated && node.hiddenVariations && node.hiddenVariations > 0 && (
              <Badge variant="secondary" className="text-xs bg-primary/10 text-primary">
                +{node.hiddenVariations} similar
              </Badge>
            )}
            
            {node.canonicalConfidence && (
              <Badge variant="outline" className="text-xs">
                {Math.round(node.canonicalConfidence * 100)}% confidence
              </Badge>
            )}
          </div>
          
          <div className="prose prose-sm max-w-none mb-2 text-newspaper-headline
            prose-headings:text-newspaper-headline
            prose-p:text-newspaper-headline
            prose-p:leading-relaxed
            prose-ul:list-none
            prose-ul:pl-0
            prose-li:pl-0
            prose-li:mb-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {node.content}
            </ReactMarkdown>
          </div>
          
          {node.replacedOriginal && (
            <div className="prose prose-xs max-w-none text-muted-foreground italic mb-2">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {`(Replaced: "${node.replacedOriginal}")`}
              </ReactMarkdown>
            </div>
          )}
          
          {/* Cluster expansion */}
          {cluster && node.hiddenVariations && node.hiddenVariations > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-auto p-1 text-newspaper-byline hover:text-newspaper-headline"
              onClick={() => onToggleExpand(node.representsCluster!)}
            >
              {expanded ? 'Hide' : 'Show'} {node.hiddenVariations} variations
              <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </Button>
          )}
          
          {expanded && cluster && cluster.variations.length > 0 && (
            <div className="mt-2 pl-4 border-l-2 border-primary/20 space-y-2">
              {cluster.variations.map((variation, index) => (
                <div key={index} className="text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-newspaper-byline font-medium">"{variation.text}"</span>
                    <Badge variant="outline" className="text-xs">
                      {Math.round(variation.similarity * 100)}% similar
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {variation.speaker} • {new Date(variation.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const ContentCard = ({ data, className = "" }: ContentCardProps) => {
  return (
    <Card className={`p-4 hover:shadow-lg transition-shadow h-full flex flex-col ${className}`}>
      {data.type === "daily-summary" ? (
        <DailySummaryContent data={data} />
      ) : data.type === "limitless" ? (
        <LimitlessContent data={data} />
      ) : (
        <ContentItemContent data={data} />
      )}
    </Card>
  );
};