import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ResearchOutput, ResearchRequest, SimilarOutput } from '../api';
import SearchBar from '../components/SearchBar';
import OutputContent from '../components/OutputContent';
import Rating from '../components/Rating';

export default function ReviewPage() {
  const [outputs, setOutputs] = useState<ResearchOutput[]>([]);
  const [requests, setRequests] = useState<Map<string, ResearchRequest>>(new Map());
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [followUpQuery, setFollowUpQuery] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SimilarOutput[] | null>(null);

  const refresh = async () => {
    const outs = await api.outputs.list({ status: 'unchecked' });
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
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const handleAction = async (outputId: string, action: 'approve' | 'comment' | 'follow_up' | 'delete') => {
    setActionLoading(true);
    try {
      await api.reviews.create(outputId, {
        action,
        comment: action === 'comment' ? comment : undefined,
        follow_up_query: action === 'follow_up' ? followUpQuery : undefined,
      });
      setComment('');
      setFollowUpQuery('');
      setExpandedId(null);
      refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSearchResults = (results: SimilarOutput[]) => {
    const uncheckedResults = results.filter(r => r.output.status === 'unchecked');
    setSearchResults(uncheckedResults);
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
        placeholder="search unchecked outputs..."
      />

      <p className="text-xs text-sand-600">
        {searchResults
          ? `${displayOutputs.length} result(s)`
          : `${outputs.length} output(s) to review`}
      </p>

      {displayOutputs.length === 0 && !searchResults && (
        <p className="text-sand-600 text-xs">no unchecked outputs.</p>
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
                    <p className="text-xs text-accent-light mb-1">{req.query}</p>
                  )}
                  <p className="text-sand-400 text-xs line-clamp-3">
                    {out.content.slice(0, 300)}...
                  </p>
                </div>
                <div className="text-right text-[10px] text-sand-600 shrink-0 space-y-1">
                  {score !== undefined && (
                    <div className="text-accent-light font-bold">{(score * 100).toFixed(1)}%</div>
                  )}
                  <div>{out.token_count} tok</div>
                  <div>{out.inference_time_ms ? `${(out.inference_time_ms / 1000).toFixed(1)}s` : ''}</div>
                  {out.truncated && (
                    <div className="text-amber-500 uppercase">trunc</div>
                  )}
                </div>
              </div>
            </div>

            {expanded && (
              <div className="border-t border-sand-800 p-4 space-y-4">
                <OutputContent content={out.content} />

                {out.truncated && (
                  <p className="text-amber-500 text-xs">
                    // output truncated at token limit
                  </p>
                )}

                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleAction(out.id, 'approve')}
                      disabled={actionLoading}
                      className="px-3 py-1.5 bg-green-900 text-green-400 text-xs border border-green-800 hover:bg-green-800 disabled:opacity-40"
                    >
                      [approve]
                    </button>
                    <button
                      onClick={() => handleAction(out.id, 'delete')}
                      disabled={actionLoading}
                      className="px-3 py-1.5 bg-red-950 text-red-400 text-xs border border-red-900 hover:bg-red-900 disabled:opacity-40"
                    >
                      [delete]
                    </button>
                  </div>
                  <Rating outputId={out.id} currentRating={out.rating} />
                </div>

                <div className="flex gap-2">
                  <input
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    placeholder="comment..."
                    className="flex-1 bg-sand-900 border border-sand-700 px-3 py-2 text-xs text-sand-200 placeholder-sand-600 focus:outline-none focus:border-accent"
                  />
                  <button
                    onClick={() => handleAction(out.id, 'comment')}
                    disabled={actionLoading || !comment.trim()}
                    className="px-3 py-1.5 bg-sand-800 text-sand-300 text-xs border border-sand-700 hover:bg-sand-700 disabled:opacity-40"
                  >
                    [comment]
                  </button>
                </div>

                <div className="flex gap-2">
                  <input
                    value={followUpQuery}
                    onChange={e => setFollowUpQuery(e.target.value)}
                    placeholder="follow-up question..."
                    className="flex-1 bg-sand-900 border border-sand-700 px-3 py-2 text-xs text-sand-200 placeholder-sand-600 focus:outline-none focus:border-accent"
                  />
                  <button
                    onClick={() => handleAction(out.id, 'follow_up')}
                    disabled={actionLoading || !followUpQuery.trim()}
                    className="px-3 py-1.5 bg-accent text-sand-100 text-xs border border-sand-600 hover:bg-accent-light disabled:opacity-40"
                  >
                    [follow-up]
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
