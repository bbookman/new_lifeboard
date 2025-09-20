import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, Clock, RefreshCw } from "lucide-react";
import { useState, useEffect } from "react";
import { useLimitlessData } from "../hooks/useLimitlessData";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LimitlessContentData } from "./ContentCard";
import { extractDateFromLimitlessId } from "../utils/limitless";

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
    <div className="conversation-node mb-6">
      <div className="flex items-start space-x-4">
        <Avatar className="w-10 h-10 flex-shrink-0">
          <div className="w-full h-full bg-social-accent rounded-full flex items-center justify-center">
            <span className="text-white font-bold text-base">
              {node.speaker?.charAt(0) || '?'}
            </span>
          </div>
        </Avatar>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-3 mb-2">
            <span className="font-semibold text-lg text-newspaper-headline">{node.speaker}</span>
            <span className="text-sm text-newspaper-byline">
              {new Date(node.timestamp).toLocaleTimeString()}
            </span>
            
            {node.isDeduplicated && node.hiddenVariations && node.hiddenVariations > 0 && (
              <Badge variant="secondary" className="text-sm bg-primary/10 text-primary">
                +{node.hiddenVariations} similar
              </Badge>
            )}
            
            {node.canonicalConfidence && (
              <Badge variant="outline" className="text-sm">
                {Math.round(node.canonicalConfidence * 100)}% confidence
              </Badge>
            )}
          </div>
          
          <div className="prose prose-lg max-w-none mb-4 text-newspaper-headline
            prose-headings:text-newspaper-headline
            prose-p:text-newspaper-headline
            prose-p:leading-relaxed
            prose-ul:list-none
            prose-ul:pl-0
            prose-li:pl-0
            prose-li:mb-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {node.content}
            </ReactMarkdown>
          </div>
          
          {node.replacedOriginal && (
            <div className="prose prose-base max-w-none text-muted-foreground italic mb-4">
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
              className="text-sm h-auto p-2 text-newspaper-byline hover:text-newspaper-headline mb-2"
              onClick={() => onToggleExpand(node.representsCluster!)}
            >
              {expanded ? 'Hide' : 'Show'} {node.hiddenVariations} variations
              <ChevronDown className={`w-4 h-4 ml-2 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            </Button>
          )}
          
          {expanded && cluster && cluster.variations.length > 0 && (
            <div className="mt-4 pl-6 border-l-2 border-primary/20 space-y-3">
              {cluster.variations.map((variation, index) => (
                <div key={index} className="text-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-newspaper-byline font-medium">"{variation.text}"</span>
                    <Badge variant="outline" className="text-sm">
                      {Math.round(variation.similarity * 100)}% similar
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
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

export const LimitlessContentExpanded = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState<LimitlessContentData | null>(null);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  const limitlessData = useLimitlessData();

  useEffect(() => {
    const dataParam = searchParams.get('data');
    const keyParam = searchParams.get('key');
    
    if (dataParam) {
      try {
        const parsedData = JSON.parse(decodeURIComponent(dataParam));
        setData(parsedData);
      } catch (error) {
        console.error('Failed to parse content data:', error);
      }
    } else if (keyParam) {
      try {
        const storedData = sessionStorage.getItem(keyParam);
        if (storedData) {
          const parsedData = JSON.parse(storedData);
          setData(parsedData);
        }
      } catch (error) {
        console.error('Failed to parse stored content data:', error);
      }
    }
  }, [searchParams]);

  const handleRefresh = async () => {
    if (!data) return;
    
    const extractedDate = extractDateFromLimitlessId(data.id);
    if (!extractedDate) {
      console.error('Could not extract date from data ID:', data.id);
      return;
    }

    try {
      setRefreshing(true);
      
      // Note: This refresh only updates markdown content, not conversation data
      // The conversation view displays displayConversation, semanticClusters, and semanticMetadata
      // which are not updated by the current refresh mechanism
      
      // Clear current limitless data
      limitlessData.clearContent();
      
      // Reset fetch attempted state for the extracted date only
      limitlessData.resetFetchAttempted(extractedDate);
      
      // Trigger server-side refresh by fetching fresh data
      const md = await limitlessData.fetchData(extractedDate, true);
      
      // Navigate back to the day view where conversation data will be refreshed
      console.log('Refresh completed - navigating back to day view for updated conversation data');
      
      // Create a toast/notification message
      const message = 'Data refresh initiated. Returning to day view where updated conversation will be available.';
      
      // For now, we'll navigate back and let the user know via console
      // In a full implementation, you would show a toast/snackbar here
      console.log(message);
      
      // Navigate back to the day view
      navigate(-1);
      
    } catch (error) {
      console.error('Error refreshing limitless data:', error);
    } finally {
      setRefreshing(false);
    }
  };

  const toggleClusterExpansion = (clusterId: string) => {
    const newExpanded = new Set(expandedClusters);
    if (newExpanded.has(clusterId)) {
      newExpanded.delete(clusterId);
    } else {
      newExpanded.add(clusterId);
    }
    setExpandedClusters(newExpanded);
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-4xl mx-auto">
          <div className="text-center">
            <p className="text-xl text-newspaper-byline">Loading content...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 bg-white shadow-sm z-10 p-4 border-b">
        <div className="max-w-4xl mx-auto">
          <div className="relative">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-newspaper-headline">
                {data.title || "Conversation"}
              </h1>
              <div className="flex items-center justify-center space-x-2 mt-1">
                <Clock className="w-4 h-4 text-newspaper-byline" />
                <span className="text-sm text-newspaper-byline">{data.timestamp}</span>
              </div>
              <div className="flex items-center justify-center space-x-2 mt-2">
                <Badge variant="secondary">
                  {data.semanticMetadata.clusteredLines} of {data.semanticMetadata.totalLines} lines
                </Badge>
              </div>
            </div>
            
            {/* Refresh button positioned in top right */}
            <div className="absolute top-0 right-0 z-20">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                className="p-2 bg-white hover:bg-gray-50 border-gray-200 shadow-sm"
                title="Trigger server refresh and return to day view (conversation data will update there)"
              >
                <RefreshCw className={`w-4 h-4 text-gray-600 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto p-8">
        <Card className="p-8">
          {/* Semantic density indicator */}
          <div className="space-y-2 mb-8">
            <div className="w-full bg-muted rounded-full h-3">
              <div 
                className="bg-primary h-3 rounded-full transition-all"
                style={{ width: `${data.semanticMetadata.semanticDensity * 100}%` }}
              />
            </div>
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Semantic density: {Math.round(data.semanticMetadata.semanticDensity * 100)}%</span>
              <span>{data.semanticMetadata.clustersFound} patterns found</span>
            </div>
          </div>

          {/* Conversation content */}
          <div className="space-y-6">
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
            <div className="flex flex-wrap gap-3 pt-6 border-t border-muted mt-8">
              <span className="text-base text-muted-foreground font-medium">Themes:</span>
              {data.semanticMetadata.uniqueThemes.map(theme => (
                <Badge key={theme} variant="outline" className="text-sm">
                  {theme.replace('_', ' ')}
                </Badge>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
