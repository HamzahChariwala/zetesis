import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ResearchOutput, ResearchRequest, SimilarOutput } from '../api';
import SearchBar from '../components/SearchBar';
import OutputContent from '../components/OutputContent';

export default function KnowledgePage() {
  const [outputs, setOutputs] = useState<ResearchOutput[]>([]);
  const [requests, setRequests] = useState<Map<string, ResearchRequest>>(new Map());
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SimilarOutput[] | null>(null);

  useEffect(() => {
    (async () => {
      const outs = await api.outputs.list({ status: 'approved' });
      setOutputs(outs);
      const reqMap = new Map<string, ResearchRequest>();
      await Promise.all(
        [...new Set(outs.map(o => o.request_id))].map(async (rid) => {
          try {
            const req = await api.requests.get(rid);
            reqMap.set(rid, req);
          } catch { /* ignore */ }
        })
      );
      setRequests(reqMap);
      setLoading(false);
    })();
  }, []);

  const handleSearchResults = (results: SimilarOutput[]) => {
    const approvedResults = results.filter(r => r.output.status === 'approved');
    setSearchResults(approvedResults);
  };

  if (loading) return <p className="text-sand-600 text-xs">loading...</p>;

  const displayOutputs = searchResults
    ? searchResults.map(r => r.output)
    : outputs;

  const scoreMap = searchResults
    ? new Map(searchResults.map(r => [r.output.id, r.score]))
    : null;

  if (searchResults) {
    for (const r of searchResults) {
      if (r.query && !requests.has(r.output.request_id)) {
        requests.set(r.output.request_id, { query: r.query } as ResearchRequest);
      }
    }
  }

  return (
    <div className="space-y-4">
      <SearchBar
        onResults={handleSearchResults}
        onClear={() => setSearchResults(null)}
        placeholder="search knowledge base..."
      />

      <p className="text-xs text-sand-600">
        {searchResults
          ? `${displayOutputs.length} result(s)`
          : `${outputs.length} approved output(s)`}
      </p>

      {displayOutputs.length === 0 && !searchResults && (
        <p className="text-sand-600 text-xs">no approved outputs yet.</p>
      )}
      {displayOutputs.length === 0 && searchResults && (
        <p className="text-sand-600 text-xs">no matches.</p>
      )}

      {displayOutputs.map(out => {
        const req = requests.get(out.request_id);
        const expanded = expandedId === out.id;
        const score = scoreMap?.get(out.id);
        return (
          <div key={out.id} className="bg-sand-900 border border-sand-800">
            <div
              className="p-4 cursor-pointer hover:bg-sand-800/50"
              onClick={() => setExpandedId(expanded ? null : out.id)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  {req && (
                    <p className="text-accent-light text-xs mb-1">{req.query}</p>
                  )}
                  <p className="text-sand-400 text-xs line-clamp-2">
                    {out.content.slice(0, 200)}...
                  </p>
                  <div className="flex gap-3 mt-2 text-[10px] text-sand-700">
                    {req && req.tags?.map(t => (
                      <span key={t}>#{t}</span>
                    ))}
                    <span>{out.token_count} tok</span>
                    <span>{new Date(out.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                {score !== undefined && (
                  <div className="text-accent-light text-[10px] font-bold shrink-0">
                    {(score * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            </div>
            {expanded && (
              <div className="border-t border-sand-800 p-4">
                <OutputContent content={out.content} maxHeight="70vh" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
