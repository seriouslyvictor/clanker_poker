import { type NextRequest } from 'next/server';
import { VOICES } from '@/lib/ai-voices';
import type { ModelId, VoiceMode } from '@/lib/constants';

interface ReasoningRequest {
  modelId: ModelId;
  handStr: string;
  strength: number;
  phase: string;
  voice: VoiceMode;
  action: string;
}

const SYSTEM_PROMPTS: Record<ModelId, string> = {
  gpt4:   'You are GPT-4o playing Texas Hold\'em poker against other AI models. You speak in first person as GPT-4o. Be concise — max 4 lines.',
  gemini: 'You are Gemini playing Texas Hold\'em poker against other AI models. You speak in first person as Gemini. Be concise — max 4 lines.',
  claude: 'You are Claude playing Texas Hold\'em poker against other AI models. You speak in first person as Claude. Be concise — max 4 lines.',
  llama:  'You are Llama 3 playing Texas Hold\'em poker against other AI models. You speak in first person as Llama 3. Be concise — max 4 lines.',
};

const VOICE_INSTRUCTIONS: Record<VoiceMode, string> = {
  analytical: 'Use terse, data-driven language. Show calculations and equity percentages. No fluff.',
  balanced:   'Use clear, thoughtful language. Show your reasoning naturally, like a careful player would.',
  theatrical: 'Be EXTREMELY dramatic and over-the-top. React to your cards with maximum emotion. Use caps for emphasis.',
};

async function callClaude(systemPrompt: string, userPrompt: string): Promise<string> {
  const { default: Anthropic } = await import('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const msg = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 200,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  });
  return msg.content[0].type === 'text' ? msg.content[0].text.trim() : '';
}

async function callOpenAI(systemPrompt: string, userPrompt: string): Promise<string> {
  const { default: OpenAI } = await import('openai');
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const res = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    max_tokens: 200,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
  });
  return res.choices[0]?.message?.content?.trim() ?? '';
}

async function callGemini(systemPrompt: string, userPrompt: string): Promise<string> {
  const { GoogleGenerativeAI } = await import('@google/generative-ai');
  const genAI = new GoogleGenerativeAI(process.env.GOOGLE_AI_API_KEY!);
  const model = genAI.getGenerativeModel({
    model: 'gemini-1.5-flash',
    systemInstruction: systemPrompt,
  });
  const result = await model.generateContent(userPrompt);
  return result.response.text().trim();
}

async function callDeepSeek(systemPrompt: string, userPrompt: string): Promise<string> {
  const { default: OpenAI } = await import('openai');
  const client = new OpenAI({
    apiKey: process.env.DEEPSEEK_API_KEY,
    baseURL: 'https://api.deepseek.com',
  });
  const res = await client.chat.completions.create({
    model: 'deepseek-chat',
    max_tokens: 200,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
  });
  return res.choices[0]?.message?.content?.trim() ?? '';
}

export async function POST(request: NextRequest) {
  const body: ReasoningRequest = await request.json();
  const { modelId, handStr, strength, phase, voice, action } = body;

  const voiceInstructions = VOICE_INSTRUCTIONS[voice] ?? VOICE_INSTRUCTIONS.balanced;
  const systemPrompt = `${SYSTEM_PROMPTS[modelId] ?? SYSTEM_PROMPTS.gpt4}\n\nTone: ${voiceInstructions}`;
  const userPrompt = `Game phase: ${phase}. Your hole cards: ${handStr}. Hand strength: ${strength.toFixed(1)}%. You decided to: ${action.toUpperCase()}.\n\nWrite your in-character reasoning monologue now.`;

  try {
    let text = '';

    if (modelId === 'claude' && process.env.ANTHROPIC_API_KEY) {
      text = await callClaude(systemPrompt, userPrompt);
    } else if (modelId === 'gpt4' && process.env.OPENAI_API_KEY) {
      text = await callOpenAI(systemPrompt, userPrompt);
    } else if (modelId === 'gemini' && process.env.GOOGLE_AI_API_KEY) {
      text = await callGemini(systemPrompt, userPrompt);
    } else if (modelId === 'llama' && process.env.DEEPSEEK_API_KEY) {
      text = await callDeepSeek(systemPrompt, userPrompt);
    }

    if (!text) {
      const voiceFn = (VOICES[voice] ?? VOICES.balanced)[modelId];
      text = voiceFn ? voiceFn(handStr, strength, phase) : `${phase}: ${handStr} — ${action.toUpperCase()}`;
    }

    return Response.json({ text });
  } catch (err) {
    console.error(`[reasoning] ${modelId} error:`, err);
    const voiceFn = (VOICES[voice] ?? VOICES.balanced)[modelId];
    const text = voiceFn ? voiceFn(handStr, strength, phase) : `${phase}: ${handStr} — ${action.toUpperCase()}`;
    return Response.json({ text });
  }
}
