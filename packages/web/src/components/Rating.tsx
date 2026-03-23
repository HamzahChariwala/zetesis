import { useState } from 'react';
import { api } from '../api';

interface RatingProps {
  outputId: string;
  currentRating: number | null;
  onRated?: (rating: number) => void;
}

export default function Rating({ outputId, currentRating, onRated }: RatingProps) {
  const [rating, setRating] = useState<number | null>(currentRating);
  const [hovered, setHovered] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const handleRate = async (value: number) => {
    setSaving(true);
    try {
      await api.outputs.rate(outputId, value);
      setRating(value);
      onRated?.(value);
    } catch (err) {
      console.error('rating failed:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-sand-600 uppercase tracking-wide mr-1">rating</span>
      {[1, 2, 3, 4, 5].map(v => {
        const active = (hovered ?? rating ?? 0) >= v;
        return (
          <button
            key={v}
            disabled={saving}
            onClick={() => handleRate(v)}
            onMouseEnter={() => setHovered(v)}
            onMouseLeave={() => setHovered(null)}
            className={`w-6 h-6 text-xs border transition-colors disabled:opacity-40 ${
              active
                ? 'bg-accent text-sand-100 border-accent-light'
                : 'bg-sand-900 text-sand-600 border-sand-700 hover:border-sand-500'
            }`}
          >
            {v}
          </button>
        );
      })}
    </div>
  );
}
