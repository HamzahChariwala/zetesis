import { useEffect, useState } from 'react';
import { api } from '../api';
import type { RequestType, ModelInfo, ToolInfo } from '../api';

const REQUEST_TYPES: { value: RequestType; label: string }[] = [
  { value: 'deep_dive', label: 'deep_dive' },
  { value: 'literature_review', label: 'literature_review' },
  { value: 'idea_exploration', label: 'idea_exploration' },
  { value: 'fact_check', label: 'fact_check' },
];

export default function SubmitPage({ onNavigate }: { onNavigate: (tab: 'submit' | 'queue' | 'review' | 'knowledge') => void }) {
  const [query, setQuery] = useState('');
  const [type, setType] = useState<RequestType>('deep_dive');
  const [tags, setTags] = useState('');
  const [context, setContext] = useState('');
  const [priority, setPriority] = useState(5);
  const [modelId, setModelId] = useState<string>('');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [showModels, setShowModels] = useState(false);

  const refreshModels = async () => {
    try {
      const [modelsData, toolsData] = await Promise.all([
        api.system.models(),
        api.system.tools(),
      ]);
      setModels(modelsData.models);
      if (!modelId) setModelId(modelsData.default);
      setAvailableTools(toolsData.tools);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    refreshModels();
  }, []);

  // Poll model status while any download is in progress
  useEffect(() => {
    const hasActiveDownload = models.some(m => m.download?.status === 'downloading');
    if (!hasActiveDownload) return;
    const id = setInterval(refreshModels, 3000);
    return () => clearInterval(id);
  }, [models]);

  const handleDownload = async (id: string) => {
    try {
      await api.system.downloadModel(id);
      refreshModels();
    } catch { /* ignore */ }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmitting(true);
    setResult(null);
    try {
      const tagList = tags.split(',').map(t => t.trim()).filter(Boolean);
      await api.requests.create({
        query: query.trim(),
        request_type: type,
        tags: tagList.length > 0 ? tagList : undefined,
        context: context.trim() || undefined,
        priority,
        model_id: modelId || undefined,
        tools: selectedTools.size > 0 ? [...selectedTools] : undefined,
      });
      setResult({ ok: true, message: 'request queued' });
      setQuery('');
      setContext('');
      setTags('');
    } catch (err: unknown) {
      setResult({ ok: false, message: err instanceof Error ? err.message : 'failed' });
    } finally {
      setSubmitting(false);
    }
  };

  const selectedModel = models.find(m => m.id === modelId);
  const selectedNotReady = selectedModel && !selectedModel.downloaded;

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <div>
        <label className="block text-xs text-sand-500 mb-1.5 uppercase tracking-wide">query</label>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          rows={4}
          placeholder="what do you want to investigate?"
          className="w-full bg-sand-900 border border-sand-700 px-4 py-3 text-sm text-sand-100 placeholder-sand-600 focus:outline-none focus:border-accent resize-y"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-sand-500 mb-1.5 uppercase tracking-wide">type</label>
          <select
            value={type}
            onChange={e => setType(e.target.value as RequestType)}
            className="w-full bg-sand-900 border border-sand-700 px-4 py-2.5 text-sm text-sand-100 focus:outline-none focus:border-accent"
          >
            {REQUEST_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs text-sand-500 uppercase tracking-wide">model</label>
            <button
              type="button"
              onClick={() => setShowModels(!showModels)}
              className="text-[10px] text-sand-600 hover:text-sand-400"
            >
              [{showModels ? 'hide' : 'manage'}]
            </button>
          </div>
          <select
            value={modelId}
            onChange={e => setModelId(e.target.value)}
            className="w-full bg-sand-900 border border-sand-700 px-4 py-2.5 text-sm text-sand-100 focus:outline-none focus:border-accent"
          >
            {models.map(m => (
              <option key={m.id} value={m.id} disabled={!m.downloaded}>
                {m.label} ({m.size_gb}GB){!m.downloaded ? ' [not downloaded]' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Model management panel */}
      {showModels && (
        <div className="bg-sand-900 border border-sand-800 p-4 space-y-2">
          <p className="text-[10px] text-sand-600 uppercase tracking-wide mb-3">model management</p>
          {models.map(m => (
            <div key={m.id} className="flex items-center justify-between py-1.5">
              <div className="min-w-0">
                <span className="text-xs text-sand-300">{m.label}</span>
                <span className="text-[10px] text-sand-600 ml-2">{m.size_gb}GB</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {m.downloaded ? (
                  <span className="text-[10px] text-green-500 border border-green-800 px-2 py-0.5">ready</span>
                ) : m.download?.status === 'downloading' ? (
                  <span className="text-[10px] text-blue-400 border border-blue-800 px-2 py-0.5 animate-pulse">
                    downloading...
                  </span>
                ) : m.download?.status === 'failed' ? (
                  <>
                    <span className="text-[10px] text-red-400" title={m.download.error || ''}>failed</span>
                    <button
                      type="button"
                      onClick={() => handleDownload(m.id)}
                      className="text-[10px] text-sand-600 hover:text-sand-300 border border-sand-700 px-2 py-0.5"
                    >
                      [retry]
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleDownload(m.id)}
                    className="text-[10px] text-accent-light hover:text-sand-200 border border-sand-700 px-2 py-0.5 hover:border-sand-500"
                  >
                    [download]
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-sand-500 mb-1.5 uppercase tracking-wide">tags</label>
          <input
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="ml, inference, attention"
            className="w-full bg-sand-900 border border-sand-700 px-4 py-2.5 text-sm text-sand-100 placeholder-sand-600 focus:outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="block text-xs text-sand-500 mb-1.5 uppercase tracking-wide">priority (0-10)</label>
          <input
            type="range"
            min={0}
            max={10}
            value={priority}
            onChange={e => setPriority(Number(e.target.value))}
            className="w-full mt-2 accent-accent"
          />
          <div className="text-center text-xs text-sand-500 mt-1">{priority}</div>
        </div>
      </div>

      {availableTools.length > 0 && (
        <div>
          <label className="block text-xs text-sand-500 mb-2 uppercase tracking-wide">tools</label>
          <div className="flex gap-3">
            {availableTools.map(tool => {
              const active = selectedTools.has(tool.name);
              return (
                <button
                  key={tool.name}
                  type="button"
                  onClick={() => {
                    const next = new Set(selectedTools);
                    if (active) next.delete(tool.name); else next.add(tool.name);
                    setSelectedTools(next);
                  }}
                  className={`px-3 py-1.5 text-xs border transition-colors ${
                    active
                      ? 'bg-accent text-sand-100 border-accent-light'
                      : 'bg-sand-900 text-sand-500 border-sand-700 hover:border-sand-500'
                  }`}
                  title={tool.description}
                >
                  {tool.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <label className="block text-xs text-sand-500 mb-1.5 uppercase tracking-wide">context</label>
        <textarea
          value={context}
          onChange={e => setContext(e.target.value)}
          rows={2}
          placeholder="any background information..."
          className="w-full bg-sand-900 border border-sand-700 px-4 py-3 text-sm text-sand-100 placeholder-sand-600 focus:outline-none focus:border-accent resize-y"
        />
      </div>

      <button
        type="submit"
        disabled={submitting || !query.trim() || !!selectedNotReady}
        className="px-6 py-2.5 bg-accent text-sand-100 text-sm font-bold uppercase tracking-wide hover:bg-accent-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors border border-sand-600"
      >
        {submitting ? 'submitting...' : selectedNotReady ? 'model not ready' : 'submit'}
      </button>

      {result && (
        <p className={`text-xs ${result.ok ? 'text-sand-400' : 'text-red-400'}`}>
          {result.message}
          {result.ok && (
            <>
              {' // '}
              <button
                type="button"
                onClick={() => onNavigate('queue')}
                className="underline hover:text-sand-200"
              >
                view in queue
              </button>
            </>
          )}
        </p>
      )}
    </form>
  );
}
