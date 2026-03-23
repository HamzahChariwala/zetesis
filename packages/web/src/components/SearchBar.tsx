import { useState } from 'react';
import { api } from '../api';
import type { SimilarOutput } from '../api';

interface SearchBarProps {
  onResults: (results: SimilarOutput[]) => void;
  onClear: () => void;
  placeholder?: string;
}

export default function SearchBar({ onResults, onClear, placeholder }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const results = await api.knowledge.search(query.trim(), 20);
      onResults(results);
    } catch (err) {
      console.error('search failed:', err);
    } finally {
      setSearching(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    onClear();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="flex gap-2">
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder ?? 'semantic search...'}
        className="flex-1 bg-sand-900 border border-sand-700 px-4 py-2.5 text-xs text-sand-200 placeholder-sand-600 focus:outline-none focus:border-accent"
      />
      <button
        onClick={handleSearch}
        disabled={searching || !query.trim()}
        className="px-4 py-2.5 bg-accent text-sand-100 text-xs font-bold uppercase tracking-wide hover:bg-accent-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors border border-sand-600"
      >
        {searching ? '...' : 'search'}
      </button>
      {query && (
        <button
          onClick={handleClear}
          className="px-3 py-2.5 bg-sand-800 text-sand-500 text-xs border border-sand-700 hover:text-sand-300 transition-colors"
        >
          clear
        </button>
      )}
    </div>
  );
}
