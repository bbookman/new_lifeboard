import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  BarChart3, 
  TrendingUp, 
  MessageCircle, 
  Clock, 
  ChevronDown,
  Filter
} from "lucide-react";

interface SemanticPattern {
  clusterId: string;
  theme: string;
  canonical: string;
  frequency: number;
  confidence: number;
  lastSeen: string;
  trend: 'increasing' | 'decreasing' | 'stable';
  conversations: Array<{
    id: string;
    title: string;
    date: string;
    variations: number;
  }>;
}

interface PatternStats {
  totalPatterns: number;
  averageFrequency: number;
  topThemes: Array<{
    theme: string;
    count: number;
    percentage: number;
  }>;
  recentActivity: number;
}

interface ConversationPatternsViewProps {
  timeframe?: 'week' | 'month' | 'quarter' | 'all';
  onPatternClick?: (pattern: SemanticPattern) => void;
}

export const ConversationPatternsView = ({ 
  timeframe = 'month',
  onPatternClick 
}: ConversationPatternsViewProps) => {
  const [patterns, setPatterns] = useState<SemanticPattern[]>([]);
  const [stats, setStats] = useState<PatternStats | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState(timeframe);
  const [sortBy, setSortBy] = useState<'frequency' | 'confidence' | 'recent'>('frequency');
  const [filterTheme, setFilterTheme] = useState<string>('all');
  const [expandedPattern, setExpandedPattern] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Mock data for demonstration - replace with actual API call
  useEffect(() => {
    const fetchPatterns = async () => {
      setLoading(true);
      
      // Simulated API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Mock pattern data
      const mockPatterns: SemanticPattern[] = [
        {
          clusterId: "weather_complaints_001",
          theme: "weather_complaints",
          canonical: "I hate this weather",
          frequency: 12,
          confidence: 0.89,
          lastSeen: "2024-01-14",
          trend: "increasing",
          conversations: [
            { id: "conv1", title: "Morning Chat", date: "2024-01-14", variations: 3 },
            { id: "conv2", title: "Therapy Session", date: "2024-01-12", variations: 2 },
            { id: "conv3", title: "Work Meeting", date: "2024-01-10", variations: 4 }
          ]
        },
        {
          clusterId: "meeting_prep_002",
          theme: "meeting_preparation",
          canonical: "I need to prepare for the meeting",
          frequency: 8,
          confidence: 0.92,
          lastSeen: "2024-01-13",
          trend: "stable",
          conversations: [
            { id: "conv4", title: "Team Sync", date: "2024-01-13", variations: 2 },
            { id: "conv5", title: "Project Review", date: "2024-01-11", variations: 3 }
          ]
        },
        {
          clusterId: "energy_state_003",
          theme: "energy_levels",
          canonical: "I'm so tired today",
          frequency: 15,
          confidence: 0.85,
          lastSeen: "2024-01-15",
          trend: "decreasing",
          conversations: [
            { id: "conv6", title: "Daily Check-in", date: "2024-01-15", variations: 4 },
            { id: "conv7", title: "Evening Reflection", date: "2024-01-14", variations: 3 }
          ]
        }
      ];

      const mockStats: PatternStats = {
        totalPatterns: 3,
        averageFrequency: 11.7,
        topThemes: [
          { theme: "energy_levels", count: 15, percentage: 42.9 },
          { theme: "weather_complaints", count: 12, percentage: 34.3 },
          { theme: "meeting_preparation", count: 8, percentage: 22.9 }
        ],
        recentActivity: 35
      };

      setPatterns(mockPatterns);
      setStats(mockStats);
      setLoading(false);
    };

    fetchPatterns();
  }, [selectedTimeframe]);

  const sortedPatterns = patterns
    .filter(pattern => filterTheme === 'all' || pattern.theme === filterTheme)
    .sort((a, b) => {
      switch (sortBy) {
        case 'frequency':
          return b.frequency - a.frequency;
        case 'confidence':
          return b.confidence - a.confidence;
        case 'recent':
          return new Date(b.lastSeen).getTime() - new Date(a.lastSeen).getTime();
        default:
          return 0;
      }
    });

  const uniqueThemes = Array.from(new Set(patterns.map(p => p.theme)));

  const getTrendIcon = (trend: SemanticPattern['trend']) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp className="w-3 h-3 text-green-500" />;
      case 'decreasing':
        return <TrendingUp className="w-3 h-3 text-red-500 rotate-180" />;
      case 'stable':
        return <BarChart3 className="w-3 h-3 text-blue-500" />;
    }
  };

  const formatTheme = (theme: string) => {
    return theme.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-muted rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-muted rounded"></div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-headline text-2xl font-bold text-newspaper-headline">
              Conversation Patterns
            </h2>
            <p className="text-newspaper-byline text-sm">
              Discover recurring themes and topics in your conversations
            </p>
          </div>
          
          <div className="flex items-center space-x-3">
            <Select value={selectedTimeframe} onValueChange={(value: any) => setSelectedTimeframe(value)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="week">This Week</SelectItem>
                <SelectItem value="month">This Month</SelectItem>
                <SelectItem value="quarter">This Quarter</SelectItem>
                <SelectItem value="all">All Time</SelectItem>
              </SelectContent>
            </Select>

            <Select value={filterTheme} onValueChange={setFilterTheme}>
              <SelectTrigger className="w-40">
                <Filter className="w-4 h-4 mr-2" />
                <SelectValue placeholder="Filter by theme" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Themes</SelectItem>
                {uniqueThemes.map(theme => (
                  <SelectItem key={theme} value={theme}>
                    {formatTheme(theme)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="font-headline text-2xl font-bold text-newspaper-headline">
                {stats.totalPatterns}
              </div>
              <div className="text-newspaper-byline text-sm">Total Patterns</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="font-headline text-2xl font-bold text-newspaper-headline">
                {stats.averageFrequency.toFixed(1)}
              </div>
              <div className="text-newspaper-byline text-sm">Avg Frequency</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="font-headline text-2xl font-bold text-newspaper-headline">
                {stats.recentActivity}
              </div>
              <div className="text-newspaper-byline text-sm">Recent Activity</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="font-headline text-2xl font-bold text-newspaper-headline">
                {stats.topThemes.length}
              </div>
              <div className="text-newspaper-byline text-sm">Active Themes</div>
            </div>
          </div>
        )}

        {/* Sort Options */}
        <div className="flex items-center space-x-2">
          <span className="text-sm text-newspaper-byline">Sort by:</span>
          <Button
            variant={sortBy === 'frequency' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setSortBy('frequency')}
          >
            Frequency
          </Button>
          <Button
            variant={sortBy === 'confidence' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setSortBy('confidence')}
          >
            Confidence
          </Button>
          <Button
            variant={sortBy === 'recent' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setSortBy('recent')}
          >
            Recent
          </Button>
        </div>
      </Card>

      {/* Patterns List */}
      <div className="space-y-4">
        {sortedPatterns.map((pattern) => (
          <Card key={pattern.clusterId} className="p-4 hover:shadow-lg transition-shadow">
            <div className="space-y-3">
              {/* Pattern Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Badge variant="secondary" className="bg-primary/10 text-primary">
                    {formatTheme(pattern.theme)}
                  </Badge>
                  {getTrendIcon(pattern.trend)}
                  <span className="text-sm text-newspaper-byline">
                    {pattern.frequency} occurrences
                  </span>
                  <Badge variant="outline" className="text-xs">
                    {Math.round(pattern.confidence * 100)}% confidence
                  </Badge>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Clock className="w-3 h-3 text-newspaper-byline" />
                  <span className="text-xs text-newspaper-byline">
                    Last seen {new Date(pattern.lastSeen).toLocaleDateString()}
                  </span>
                </div>
              </div>

              {/* Canonical Line */}
              <div 
                className="cursor-pointer"
                onClick={() => onPatternClick && onPatternClick(pattern)}
              >
                <p className="font-body text-newspaper-headline text-base leading-relaxed">
                  "{pattern.canonical}"
                </p>
              </div>

              {/* Conversations Toggle */}
              <Button
                variant="ghost"
                size="sm"
                className="text-xs text-newspaper-byline hover:text-newspaper-headline"
                onClick={() => setExpandedPattern(
                  expandedPattern === pattern.clusterId ? null : pattern.clusterId
                )}
              >
                <MessageCircle className="w-3 h-3 mr-1" />
                {pattern.conversations.length} conversations
                <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${
                  expandedPattern === pattern.clusterId ? 'rotate-180' : ''
                }`} />
              </Button>

              {/* Expanded Conversations */}
              {expandedPattern === pattern.clusterId && (
                <div className="pl-4 border-l-2 border-primary/20 space-y-2">
                  {pattern.conversations.map((conv) => (
                    <div key={conv.id} className="flex items-center justify-between py-2">
                      <div>
                        <div className="font-medium text-sm text-newspaper-headline">
                          {conv.title}
                        </div>
                        <div className="text-xs text-newspaper-byline">
                          {new Date(conv.date).toLocaleDateString()}
                        </div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {conv.variations} variations
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {sortedPatterns.length === 0 && (
        <Card className="p-8 text-center">
          <MessageCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="font-headline text-lg font-semibold text-newspaper-headline mb-2">
            No Patterns Found
          </h3>
          <p className="text-newspaper-byline">
            {filterTheme === 'all' 
              ? "No conversation patterns detected for this timeframe."
              : `No patterns found for theme "${formatTheme(filterTheme)}".`
            }
          </p>
          {filterTheme !== 'all' && (
            <Button 
              variant="outline" 
              size="sm" 
              className="mt-3"
              onClick={() => setFilterTheme('all')}
            >
              Show All Themes
            </Button>
          )}
        </Card>
      )}

      {/* Theme Distribution */}
      {stats && stats.topThemes.length > 0 && (
        <Card className="p-6">
          <h3 className="font-headline text-lg font-semibold text-newspaper-headline mb-4">
            Theme Distribution
          </h3>
          <div className="space-y-3">
            {stats.topThemes.map((theme, index) => (
              <div key={theme.theme} className="flex items-center space-x-3">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-newspaper-headline">
                      {formatTheme(theme.theme)}
                    </span>
                    <span className="text-sm text-newspaper-byline">
                      {theme.count} ({theme.percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2">
                    <div 
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{ width: `${theme.percentage}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default ConversationPatternsView;