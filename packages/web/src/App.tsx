import { useEffect, useState } from 'react';
import { api } from './api';
import SubmitPage from './pages/SubmitPage';
import QueuePage from './pages/QueuePage';
import ReviewPage from './pages/ReviewPage';
import KnowledgePage from './pages/KnowledgePage';

type Tab = 'submit' | 'queue' | 'review' | 'knowledge';

export default function App() {
  const [tab, setTab] = useState<Tab>('submit');
  const [reviewCount, setReviewCount] = useState(0);
  const [processingCount, setProcessingCount] = useState(0);

  useEffect(() => {
    const poll = async () => {
      try {
        const qs = await api.system.queueStatus();
        setProcessingCount(qs.queued + qs.processing);
        const unchecked = await api.outputs.list({ status: 'unchecked' });
        setReviewCount(unchecked.length);
      } catch { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  const tabs: { key: Tab; label: string; badge?: number }[] = [
    { key: 'submit', label: 'submit' },
    { key: 'queue', label: 'queue', badge: processingCount || undefined },
    { key: 'review', label: 'review', badge: reviewCount || undefined },
    { key: 'knowledge', label: 'knowledge' },
  ];

  return (
    <div className="min-h-screen bg-sand-950 text-sand-200 font-mono">
      <header className="border-b border-sand-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <h1 className="text-lg font-bold tracking-wide text-sand-100 uppercase">zetesis</h1>
          <nav className="flex gap-0.5">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 py-1.5 text-xs tracking-wide transition-colors border ${
                  tab === t.key
                    ? 'bg-sand-800 text-sand-100 border-sand-600'
                    : 'text-sand-500 border-transparent hover:text-sand-300 hover:border-sand-700'
                }`}
              >
                {t.label}
                {t.badge !== undefined && t.badge > 0 && (
                  <span className={`ml-1.5 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold ${
                    t.key === 'review' ? 'bg-accent text-sand-100' : 'bg-sand-700 text-sand-300'
                  }`}>
                    {t.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-6">
        {tab === 'submit' && <SubmitPage onNavigate={setTab} />}
        {tab === 'queue' && <QueuePage />}
        {tab === 'review' && <ReviewPage />}
        {tab === 'knowledge' && <KnowledgePage />}
      </main>
    </div>
  );
}
