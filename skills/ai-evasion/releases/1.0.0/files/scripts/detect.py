#!/usr/bin/env python3
"""
AI Text Detection Analyzer
===========================
Analyzes text for the 8 statistical signals that RoBERTa-based AI detectors look for.
Based on reverse-engineering of:
- openai-community/roberta-base-openai-detector
- Hello-SimpleAI/chatgpt-detector-roberta
- PirateXX/AI-Content-Detector

References: GLTR (Gehrmann 2019), HC3 Paper (Guo 2023), OpenAI GPT-2 Report (2019)
"""

import sys
import re
import math
import statistics
from collections import Counter
from pathlib import Path

# ─── Constants ───────────────────────────────────────────────────────────────

# High-probability transition words that AI overuses (8x human rate per HC3 paper)
AI_TRANSITIONS = {
    'furthermore', 'moreover', 'additionally', 'consequently', 'therefore',
    'thus', 'hence', 'accordingly', 'subsequently', 'notably', 'indeed',
    'undoubtedly', 'meanwhile', 'nonetheless', 'nevertheless', 'besides',
    'بالإضافة', 'علاوة', 'لذلك', 'وبالتالي', 'مما لا شك', 'من ناحية أخرى',
    'ومن جهة أخرى', 'في الختام', 'ختاماً', 'مما سبق', 'في المقابل',
}

# Contractions and informal markers (rare in AI text)
CONTRACTIONS = {"it's", "don't", "can't", "won't", "isn't", "aren't", "wasn't",
                "weren't", "wouldn't", "shouldn't", "couldn't", "doesn't", "didn't",
                "hasn't", "haven't", "hadn't", "mightn't", "mustn't", "i'm", "you're",
                "we're", "they're", "he's", "she's", "that's", "what's", "let's"}

# Rare punctuation (used by humans, avoided by AI)
RARE_PUNCTUATION = ['—', '…', ';']

# ─── Helper Functions ────────────────────────────────────────────────────────

def get_sentences(text: str) -> list:
    """Split text into sentences."""
    return [s.strip() for s in re.split(r'(?<=[.!?…])\s+', text) if s.strip()]

def get_words(text: str) -> list:
    """Get lowercase words from text."""
    return re.findall(r'\b\w+\b', text.lower())

def sentence_lengths(sentences: list) -> dict:
    """Analyze sentence length distribution."""
    lengths = [len(get_words(s)) for s in sentences]
    if not lengths:
        return {}
    return {
        'count': len(lengths),
        'mean': statistics.mean(lengths),
        'median': statistics.median(lengths),
        'stdev': statistics.stdev(lengths) if len(lengths) > 1 else 0,
        'min': min(lengths),
        'max': max(lengths),
        'values': lengths
    }

def type_token_ratio(text: str) -> float:
    """Calculate Type-Token Ratio (lexical diversity)."""
    words = get_words(text)
    unique = len(set(words))
    total = len(words)
    return unique / total if total > 0 else 0

def count_transitions(text: str) -> dict:
    """Count AI-typical transition words."""
    words = get_words(text)
    bigrams = [' '.join(words[i:i+2]) for i in range(len(words)-1)]
    trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
    
    found = {}
    text_lower = text.lower()
    for t in AI_TRANSITIONS:
        count = text_lower.count(t)
        if count > 0:
            found[t] = count
    return found

def count_rare_punctuation(text: str) -> dict:
    """Count rare punctuation marks."""
    return {p: text.count(p) for p in RARE_PUNCTUATION}

def count_contractions(text: str) -> dict:
    """Count informal contractions."""
    words_lower = text.lower().split()
    found = {}
    for c in CONTRACTIONS:
        count = sum(1 for w in words_lower if w.strip(".,;:!?\"'") == c)
        if count > 0:
            found[c] = count
    return found

def analyze_sentence_openers(sentences: list) -> dict:
    """Analyze how sentences begin (syntactic pattern diversity)."""
    openers = []
    for s in sentences[:50]:  # sample first 50
        words = s.split()
        if words:
            openers.append(words[0].lower().strip(".,;:!?\"'"))
    
    opener_counts = Counter(openers)
    unique_openers = len(opener_counts)
    total = len(openers)
    
    # Common AI opener patterns (Subject-Verb-Object start)
    ai_pattern_count = sum(1 for o in openers if o in {'the', 'a', 'an', 'this', 'it', 'these', 'those'})
    
    return {
        'unique_openers': unique_openers,
        'total_sentences': total,
        'diversity_ratio': unique_openers / total if total > 0 else 0,
        'ai_typical_openers_pct': (ai_pattern_count / total * 100) if total > 0 else 0,
        'top_openers': opener_counts.most_common(5)
    }

def estimate_perplexity_profile(text: str) -> dict:
    """
    Estimate the token probability profile without running the full model.
    Uses heuristics based on word frequency ranks.
    """
    words = get_words(text)
    if not words:
        return {}
    
    # Common English words (high-probability tokens in most LLMs)
    high_prob_words = set("""
        the a an is are was were be been being have has had do does did
        will would shall should can could may might must i you he she it
        we they me him her us them my your his its our their this that
        these those what which who whom where when why how all each every
        both few many most some any no not and but or nor for so yet
        to in on at by with from about into through during before after
        above below between under over up down out off of
    """.split())
    
    high_prob_count = sum(1 for w in words if w in high_prob_words)
    ratio = high_prob_count / len(words) if words else 0
    
    return {
        'high_prob_token_ratio': ratio,
        'estimated_profile': 'AI-typical' if ratio > 0.58 else 'Human-typical',
        'note': 'AI text typically has >58% high-probability tokens; humans <52%'
    }

# ─── Main Analyzer ───────────────────────────────────────────────────────────

def analyze_text(text: str) -> dict:
    """Full analysis of text against 8 detection signals."""
    
    sentences = get_sentences(text)
    words = get_words(text)
    word_count = len(words)
    
    results = {
        'word_count': word_count,
        'sentence_count': len(sentences),
        'signals': {},
        'overall_risk': 0,
        'recommendations': []
    }
    
    # Signal 1: Token probability profile
    perplexity = estimate_perplexity_profile(text)
    signal1_risk = 70 if perplexity.get('high_prob_token_ratio', 0) > 0.58 else 30
    results['signals']['1_token_probability'] = {
        'risk': signal1_risk,
        'detail': perplexity,
        'label': 'توزيع احتمالية الرموز'
    }
    
    # Signal 2: Sentence length variance
    sl = sentence_lengths(sentences)
    if sl:
        signal2_risk = 80 if sl['stdev'] < 6 else (40 if sl['stdev'] < 12 else 15)
        results['signals']['2_sentence_length'] = {
            'risk': signal2_risk,
            'detail': {
                'mean': round(sl['mean'], 1),
                'stdev': round(sl['stdev'], 1),
                'min': sl['min'],
                'max': sl['max'],
                'target_stdev': 12,
                'current_status': 'AI-typical' if sl['stdev'] < 6 else ('borderline' if sl['stdev'] < 12 else 'Human-typical')
            },
            'label': 'انتظام طول الجمل'
        }
    
    # Signal 3: Syntactic opener diversity
    openers = analyze_sentence_openers(sentences)
    signal3_risk = 70 if openers.get('ai_typical_openers_pct', 0) > 60 else 30
    results['signals']['3_syntactic_openers'] = {
        'risk': signal3_risk,
        'detail': openers,
        'label': 'انتظام بدايات الجمل'
    }
    
    # Signal 4: Punctuation diversity
    rare_punct = count_rare_punctuation(text)
    rare_punct_total = sum(rare_punct.values())
    punct_per_1k = (rare_punct_total / word_count * 1000) if word_count > 0 else 0
    signal4_risk = 80 if punct_per_1k < 1 else (50 if punct_per_1k < 3 else 20)
    results['signals']['4_punctuation'] = {
        'risk': signal4_risk,
        'detail': {
            'counts': rare_punct,
            'per_1000_words': round(punct_per_1k, 2),
            'target': 3,
            'status': 'AI-typical' if punct_per_1k < 1 else 'borderline'
        },
        'label': 'تنوع علامات الترقيم'
    }
    
    # Signal 5: Transition word patterns
    transitions = count_transitions(text)
    trans_per_1k = (sum(transitions.values()) / word_count * 1000) if word_count > 0 else 0
    signal5_risk = 70 if trans_per_1k > 3 else (40 if trans_per_1k > 1.5 else 15)
    results['signals']['5_transitions'] = {
        'risk': signal5_risk,
        'detail': {
            'found': transitions,
            'per_1000_words': round(trans_per_1k, 2),
            'ai_transitions_count': sum(transitions.values()),
            'target': '< 1.5 per 1000 words'
        },
        'label': 'كلمات الربط النمطية'
    }
    
    # Signal 6: Lexical diversity
    ttr = type_token_ratio(text)
    signal6_risk = 75 if ttr < 0.45 else (45 if ttr < 0.60 else 20)
    results['signals']['6_lexical_diversity'] = {
        'risk': signal6_risk,
        'detail': {
            'ttr': round(ttr, 3),
            'unique_words': len(set(words)),
            'total_words': word_count,
            'target_ttr': 0.65,
            'status': 'Low (AI-typical)' if ttr < 0.45 else ('Medium' if ttr < 0.60 else 'Good')
        },
        'label': 'التنوع المعجمي'
    }
    
    # Signal 7: Coherence (estimated by paragraph structure)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    avg_para_len = word_count / len(paragraphs) if paragraphs else word_count
    signal7_risk = 60 if len(paragraphs) < 3 else (40 if avg_para_len > 300 else 25)
    results['signals']['7_coherence'] = {
        'risk': signal7_risk,
        'detail': {
            'paragraph_count': len(paragraphs),
            'avg_words_per_paragraph': round(avg_para_len, 1),
            'note': 'AI text has uniform, long paragraphs with no digressions'
        },
        'label': 'التماسك المفرط'
    }
    
    # Signal 8: Tone variation (estimated by formality)
    contractions = count_contractions(text)
    contractions_total = sum(contractions.values())
    signal8_risk = 65 if contractions_total == 0 else (35 if contractions_total < 3 else 15)
    results['signals']['8_tone_variation'] = {
        'risk': signal8_risk,
        'detail': {
            'contractions_found': contractions,
            'total_informal_markers': contractions_total,
            'note': 'Zero contractions = strong AI signal'
        },
        'label': 'تنوع النبرة'
    }
    
    # Calculate overall risk
    risks = [s['risk'] for s in results['signals'].values()]
    results['overall_risk'] = round(statistics.mean(risks), 1)
    
    # Generate recommendations
    recs = []
    if signal1_risk >= 60:
        recs.append("🔄 استبدل 8-12% من الكلمات بمرادفات أقل شيوعاً (كلمات نادرة)")
    if signal2_risk >= 60:
        recs.append("📏 نوّع أطوال الجمل — أضف جملاً قصيرة جداً (3-5 كلمات) وطويلة جداً (40+)")
    if signal3_risk >= 60:
        recs.append("🔀 ابدأ جملك بطرق مختلفة — ظروف، عبارات جر، استفهام، تعجب")
    if signal4_risk >= 60:
        recs.append("✒️ أضف شرطات طويلة (—) وفواصل منقوطة (;) وعلامات حذف (...) — 3 لكل 1000 كلمة")
    if signal5_risk >= 60:
        recs.append("🔗 استبدل 'Furthermore/Moreover' بعبارات بشرية: 'But here's the thing—'، 'That said,'")
    if signal6_risk >= 60:
        recs.append("📚 تجنب تكرار نفس الكلمات — استخدم مرادفات مختلفة في كل مرة")
    if signal7_risk >= 50:
        recs.append("💬 أضف 2-3 استطرادات قصيرة (سطرين) — خروج عن الموضوع والعودة")
    if signal8_risk >= 50:
        recs.append("🎭 غيّر النبرة — أضف عبارات غير رسمية، contractions، تساؤلات")
    
    results['recommendations'] = recs
    results['risk_level'] = (
        'منخفض ✅' if results['overall_risk'] < 35 else
        'متوسط ⚠️' if results['overall_risk'] < 55 else
        'مرتفع 🔴'
    )
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 detect.py <text> OR python3 detect.py <file.txt>")
        print("\n  يحلل النص ويعطي تقريراً باحتمالية اكتشافه كنص مُولّد بالذكاء الاصطناعي")
        sys.exit(1)
    
    input_arg = sys.argv[1]
    
    # Check if it's a file path (only if reasonably short and has no newlines)
    text = None
    if len(input_arg) < 500 and '\n' not in input_arg:
        try:
            if Path(input_arg).exists():
                text = Path(input_arg).read_text(encoding='utf-8')
        except OSError:
            pass
    if text is None:
        text = ' '.join(sys.argv[1:])
    
    if len(text) < 50:
        print("⚠️ النص قصير جداً — التحليل قد لا يكون دقيقاً (أقل من 50 حرفاً)")
    
    results = analyze_text(text)
    
    # Pretty output
    print("\n" + "="*60)
    print("  🔍 تقرير تحليل النص — احتمالية الكشف بالذكاء الاصطناعي")
    print("="*60)
    print(f"\n  📊 الكلمات: {results['word_count']} | الجمل: {results['sentence_count']}")
    print(f"  🎯 نسبة الخطورة الإجمالية: {results['overall_risk']}% — {results['risk_level']}")
    print(f"\n  ── الإشارات الثمانية ──")
    print(f"  {'الإشارة':<28} {'الخطورة':<10}")
    print(f"  {'─'*28} {'─'*10}")
    
    for key, signal in results['signals'].items():
        bar = '█' * int(signal['risk'] / 10) + '░' * (10 - int(signal['risk'] / 10))
        print(f"  {signal['label']:<25} {bar} {signal['risk']}%")
    
    if results['recommendations']:
        print(f"\n  ── توصيات ({len(results['recommendations'])}) ──")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "="*60)
    print("  📚 المصادر: GLTR (2019) | HC3 Paper (2023) | OpenAI GPT-2 Report")
    print("="*60 + "\n")
    
    return results['overall_risk']


if __name__ == '__main__':
    risk = main()
    sys.exit(0 if risk < 55 else 1)
