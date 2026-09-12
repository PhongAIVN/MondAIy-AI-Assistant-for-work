export interface FaqEntry {
  id: string;
  question: string;
  answer: string;
}

const STOPWORDS = new Set([
  'mondaiy', 'la', 'gi', 'khong', 'co', 'the', 'cua', 'va', 'nao', 'nhu', 'nao',
  'sao', 'khi', 'duoc', 'cho', 'voi', 'hay', 'lam', 'nay', 'mot', 'ban', 'toi',
  'is', 'the', 'a', 'an', 'do', 'does', 'how', 'what', 'why', 'to', 'of', 'in',
  'on', 'for', 'and', 'or', 'work', 'works',
]);

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/gi, 'd')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ');
}

function tokenize(text: string): string[] {
  return normalize(text)
    .split(/\s+/)
    .filter((word) => word.length >= 3 && !STOPWORDS.has(word));
}

/**
 * So khớp câu hỏi khách gõ với bộ FAQ cục bộ (không gọi API/LLM).
 * Từ trong câu hỏi gốc của FAQ tính điểm cao hơn từ trong phần trả lời,
 * vì câu hỏi mới thường gần cách diễn đạt của câu hỏi FAQ hơn là câu trả lời dài.
 */
export function matchFaqEntry(question: string, entries: FaqEntry[]): FaqEntry | null {
  const askedTokens = new Set(tokenize(question));
  if (askedTokens.size === 0) return null;

  let best: { entry: FaqEntry; score: number } | null = null;
  for (const entry of entries) {
    const questionTokens = tokenize(entry.question);
    const answerTokens = tokenize(entry.answer);
    let score = 0;
    for (const token of questionTokens) if (askedTokens.has(token)) score += 3;
    for (const token of answerTokens) if (askedTokens.has(token)) score += 1;
    if (score > 0 && (!best || score > best.score)) {
      best = { entry, score };
    }
  }
  return best ? best.entry : null;
}
