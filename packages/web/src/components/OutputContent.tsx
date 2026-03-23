import { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface OutputContentProps {
  content: string;
  maxHeight?: string;
}

export default function OutputContent({ content, maxHeight = '24rem' }: OutputContentProps) {
  const [rendered, setRendered] = useState(true);

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          onClick={() => setRendered(!rendered)}
          className="text-[10px] text-sand-600 border border-sand-700 px-2 py-1 hover:text-sand-300 hover:border-sand-600 transition-colors"
        >
          {rendered ? '[raw]' : '[render]'}
        </button>
      </div>
      <div
        className={`overflow-y-auto bg-sand-950 border border-sand-800 p-4 text-xs text-sand-300 leading-relaxed`}
        style={{ maxHeight }}
      >
        {rendered ? (
          <div className="prose-sand">
            <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
          </div>
        ) : (
          <pre className="whitespace-pre-wrap font-mono">{content}</pre>
        )}
      </div>
    </div>
  );
}
