import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
}

/**
 * Reusable markdown renderer component with consistent styling
 * Extracts the complex ReactMarkdown configuration from the main component
 */
export const MarkdownRenderer = ({ content }: MarkdownRendererProps) => {
  return (
    <div className="prose prose-sm max-w-none prose-headings:text-newspaper-headline prose-p:text-newspaper-byline prose-hr:border-gray-300">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-2xl font-bold text-newspaper-headline mb-3 mt-4">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xl font-bold text-newspaper-headline mb-2 mt-3">{children}</h2>,
          h3: ({ children }) => <h3 className="text-lg font-bold text-newspaper-headline mb-2 mt-3">{children}</h3>,
          p: ({ children }) => <p className="mb-2 text-newspaper-byline">{children}</p>,
          hr: () => <hr className="my-4 border-gray-300" />,
          // Support for code blocks and inline code
          code: ({ children, ...props }: any) => {
            const className = props.className || '';
            const isInline = !className.includes('language-');

            return isInline ? (
              <code className="bg-gray-100 px-1 py-0.5 rounded text-sm">{children}</code>
            ) : (
              <pre className="bg-gray-100 p-3 rounded-md overflow-x-auto">
                <code className={className}>{children}</code>
              </pre>
            );
          },
          // Support for lists - without bullet points
          ul: ({ children }) => <ul className="list-none mb-2">{children}</ul>,
          ol: ({ children }) => <ol className="list-none mb-2">{children}</ol>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          // Support for blockquotes
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2">{children}</blockquote>
          ),
          // Support for links
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-blue-600 hover:text-blue-800 underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
