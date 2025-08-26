import { useSearchParams } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface LimitlessExpandedData {
  type: "limitless";
  id: string;
  title: string;
  timestamp: string;
  markdownContent: string;
}

export const LimitlessMarkdownExpanded = () => {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<LimitlessExpandedData | null>(null);

  useEffect(() => {
    // First try the new key-based approach (sessionStorage)
    const keyParam = searchParams.get('key');
    if (keyParam) {
      try {
        const storedData = sessionStorage.getItem(keyParam);
        if (storedData) {
          const parsedData = JSON.parse(storedData);
          setData(parsedData);
          return;
        }
      } catch (error) {
        console.error('Failed to parse stored content data:', error);
      }
    }
    
    // Fallback to old data parameter approach for backwards compatibility
    const dataParam = searchParams.get('data');
    if (dataParam) {
      try {
        const parsedData = JSON.parse(decodeURIComponent(dataParam));
        setData(parsedData);
      } catch (error) {
        console.error('Failed to parse URL content data:', error);
      }
    }
  }, [searchParams]);

  if (!data) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center">
            <p className="text-xl text-newspaper-byline">Loading content...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Content */}
      <div className="max-w-5xl mx-auto p-8">
        <Card className="p-8">
          <div className="prose prose-lg max-w-none 
            prose-headings:text-newspaper-headline 
            prose-p:text-newspaper-byline 
            prose-hr:border-gray-300
            prose-h1:text-3xl prose-h1:font-bold prose-h1:mb-4 prose-h1:mt-6
            prose-h2:text-2xl prose-h2:font-bold prose-h2:mb-3 prose-h2:mt-5
            prose-h3:text-xl prose-h3:font-bold prose-h3:mb-2 prose-h3:mt-4
            prose-p:mb-3 prose-p:leading-relaxed prose-p:text-base
            prose-ul:mb-4 prose-li:mb-1
            prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
            prose-pre:bg-gray-100 prose-pre:p-4 prose-pre:rounded-md prose-pre:overflow-x-auto
            prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:my-3
            prose-a:text-blue-600 prose-a:hover:text-blue-800 prose-a:underline">
            <MarkdownRenderer content={data.markdownContent} />
          </div>
        </Card>
      </div>
    </div>
  );
};