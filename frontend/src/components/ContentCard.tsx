import { Card } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, Clock } from "lucide-react";
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
  return (
    <div className="space-y-4">
      <div className="border-b-2 border-primary pb-3">
        <h2 className="font-headline text-2xl font-bold text-newspaper-headline">
          Daily Summary
        </h2>
        <p className="text-newspaper-byline font-body text-sm">
          {new Date(data.date).toLocaleDateString('en-US', { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
          })}
        </p>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="text-center p-3 bg-muted rounded-lg">
          <div className="font-headline text-2xl font-bold text-newspaper-headline">
            {data.totalItems}
          </div>
          <div className="text-newspaper-byline text-sm">Total Items</div>
        </div>
        <div className="text-center p-3 bg-muted rounded-lg">
          <div className="font-headline text-2xl font-bold text-newspaper-headline">
            {data.moodScore}/10
          </div>
          <div className="text-newspaper-byline text-sm">Mood Score</div>
        </div>
      </div>

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

  const accentColor = getSourceAccentColor(data.source);

  return (
    <div className="flex space-x-3">
      <Avatar className="w-12 h-12">
        <div className={`w-full h-full bg-${accentColor} rounded-full flex items-center justify-center`}>
          <span className="text-white font-bold text-lg">
            {data.username ? data.username.charAt(0) : data.source.charAt(0).toUpperCase()}
          </span>
        </div>
      </Avatar>
      
      <div className="flex-1 min-w-0">
        {data.username && (
          <div className="flex items-center space-x-2 mb-1">
            <h3 className="font-body font-semibold text-newspaper-headline truncate">
              {data.username}
            </h3>
            {data.verified && (
              <Badge variant="secondary" className={`bg-${accentColor} text-white text-xs`}>
                ✓
              </Badge>
            )}
            {data.handle && (
              <>
                <span className="text-newspaper-byline text-sm">
                  {data.handle}
                </span>
                <span className="text-newspaper-byline text-sm">•</span>
              </>
            )}
            <span className="text-newspaper-byline text-sm">
              {data.timestamp}
            </span>
          </div>
        )}
        
        <p className="font-body text-newspaper-headline leading-relaxed mb-3">
          {data.content}
        </p>
        
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
      </div>
    </div>
  );
};

const LimitlessContent = ({ data }: { data: LimitlessContentData }) => {
  const [viewMode, setViewMode] = useState<'condensed' | 'full'>('condensed');
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  
  const toggleClusterExpansion = (clusterId: string) => {
    const newExpanded = new Set(expandedClusters);
    if (newExpanded.has(clusterId)) {
      newExpanded.delete(clusterId);
    } else {
      newExpanded.add(clusterId);
    }
    setExpandedClusters(newExpanded);
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
    <Card className={`p-4 hover:shadow-lg transition-shadow ${className}`}>
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