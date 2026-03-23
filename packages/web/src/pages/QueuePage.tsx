import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ResearchRequest, ResearchOutput, QueueStatus } from '../api';
import OutputContent from '../components/OutputContent';

const STATUS_COLORS: Record<string, string> = {
  queued: 'border-yellow-800 text-yellow-600',
  processing: 'border-blue-800 text-blue-400',
  completed: 'border-green-800 text-green-500',
  failed: 'border-red-800 text-red-400',
};

export default function QueuePage() {
  const [requests, setRequests] = useState<ResearchRequest[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedOutput, setExpandedOutput] = useState<ResearchOutput | null>(null);

  const refresh = async () => {
    const [reqs, qs] = await Promise.all([
      api.requests.list({ limit: '50' }),
      api.system.queueStatus(),
    ]);
    setRequests(reqs);
    setQueueStatus(qs);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  const handleCancel = async (reqId: string) => {
    try {
      await api.requests.cancel(reqId);
      refresh();
    } catch { /* already cancelled */ }
  };

  const handleRetry = async (reqId: string) => {
    try {
      await api.requests.retry(reqId);
      refresh();
    } catch { /* ignore */ }
  };

  const handleExpand = async (req: ResearchRequest) => {
    if (expandedId === req.id) {
      setExpandedId(null);
      setExpandedOutput(null);
      return;
    }
    setExpandedId(req.id);
    setExpandedOutput(null);
    if (req.status === 'completed') {
      const outputs = await api.outputs.list();
      const match = outputs.find(o => o.request_id === req.id);
      setExpandedOutput(match || null);
    }
  };

  if (loading) return <p className="text-sand-600 text-xs">loading...</p>;

  return (
    <div className="space-y-5">
      {queueStatus && (
        <div className="flex gap-5 text-xs">
          <span className="text-yellow-600">queued: {queueStatus.queued}</span>
          <span className="text-blue-400">processing: {queueStatus.processing}</span>
          <span className="text-green-500">completed: {queueStatus.completed}</span>
          <span className="text-red-400">failed: {queueStatus.failed}</span>
        </div>
      )}

      {requests.length === 0 ? (
        <p className="text-sand-600 text-xs">no requests yet.</p>
      ) : (
        <div className="space-y-2">
          {requests.map(req => (
            <div key={req.id} className="bg-sand-900 border border-sand-800">
              <div
                className={`p-4 ${req.status === 'completed' ? 'cursor-pointer hover:bg-sand-800/50' : ''}`}
                onClick={() => req.status === 'completed' && handleExpand(req)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-sand-200 leading-relaxed">{req.query}</p>
                    <div className="flex items-center gap-3 mt-2 text-xs">
                      <span className={`px-1.5 py-0.5 border text-[10px] uppercase tracking-wider ${STATUS_COLORS[req.status]}`}>
                        {req.status}
                      </span>
                      <span className="text-sand-600">{req.request_type}</span>
                      <span className="text-sand-600">p={req.priority}</span>
                      {req.tags.length > 0 && (
                        <span className="text-sand-700">
                          {req.tags.map(t => `#${t}`).join(' ')}
                        </span>
                      )}
                      {req.status === 'completed' && (
                        <span className="text-sand-700 text-[10px]">
                          [{expandedId === req.id ? 'collapse' : 'expand'}]
                        </span>
                      )}
                    </div>
                    {req.error && (
                      <p className="text-red-400 text-xs mt-2">// {req.error}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {req.status === 'queued' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleCancel(req.id); }}
                        className="text-xs text-sand-600 hover:text-red-400 transition-colors"
                      >
                        [cancel]
                      </button>
                    )}
                    {req.status === 'failed' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRetry(req.id); }}
                        className="text-xs text-sand-600 hover:text-accent-light transition-colors"
                      >
                        [retry]
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {expandedId === req.id && req.status === 'completed' && (
                <div className="border-t border-sand-800 p-4">
                  {expandedOutput ? (
                    <>
                      <div className="flex gap-4 text-[10px] text-sand-600 mb-3 uppercase tracking-wide">
                        <span>{expandedOutput.token_count} tok</span>
                        <span>{expandedOutput.inference_time_ms ? `${(expandedOutput.inference_time_ms / 1000).toFixed(1)}s` : ''}</span>
                        <span>{expandedOutput.model_id}</span>
                        {expandedOutput.truncated && (
                          <span className="text-amber-500">truncated</span>
                        )}
                      </div>
                      <OutputContent content={expandedOutput.content} />
                    </>
                  ) : (
                    <p className="text-sand-600 text-xs">loading...</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
