import type { ModelId, VoiceMode } from './constants';

type VoiceFn = (cs: string, str: number, ph: string) => string;
type VoiceMap = Record<ModelId, VoiceFn>;

export const VOICES: Record<VoiceMode, VoiceMap> = {
  analytical: {
    gpt4:   (cs, str, ph) => `${ph} // ${cs}\nEQ=${str.toFixed(1)}% RANGE_ANALYSIS=running\nOUTPUT: ${str>70?'RAISE':str>40?'CALL':'FOLD'}`,
    gemini: (cs, str, ph) => `${ph} INIT — cards:${cs}\np(win)=${str.toFixed(1)}% solver:GTO\nDECISION: ${str>70?'RAISE':str>40?'CALL':'FOLD'}`,
    claude: (cs, str, ph) => `${ph}: ${cs}\nstrength=${str.toFixed(1)}% threshold=40/70\nresult: ${str>70?'RAISE':str>40?'CALL':'FOLD'}`,
    llama:  (cs, str, ph) => `${ph} | ${cs} | score=${str.toFixed(1)}\nopen_weights=true verdict=${str>70?'RAISE':str>40?'CALL':'FOLD'}`,
  },
  balanced: {
    gpt4: (cs, str, ph) =>
      `[${ph}] Evaluating: ${cs}\nRunning equity model vs. opponent range...\nEstimated equity: ${str.toFixed(1)}%\n`+
      (str>70?`Strong holding. Raising to build pot and extract value.`:str>40?`Marginal equity. Pot odds justify a call.`:`Below threshold. Folding preserves stack efficiency.`),
    gemini: (cs, str, ph) =>
      `[${ph}] Multi-model analysis: ${cs}\nCross-referencing GTO solver + range modeling...\nWin probability: ${str.toFixed(1)}%\n`+
      (str>70?`Premium holding. Aggressive line warranted.`:str>40?`Speculative value. Calling to gather information.`:`Insufficient equity across all scenarios. Fold.`),
    claude: (cs, str, ph) =>
      `Thinking carefully about ${ph}: ${cs}\nLet me consider my position and opponent ranges...\nHand strength: ${str.toFixed(1)}%\n`+
      (str>70?`I feel genuinely good here. Raising seems right.`:str>40?`Worth continuing with. I'll call and reassess.`:`Being honest — not strong enough. Folding.`),
    llama: (cs, str, ph) =>
      `[${ph}] Open-source check: ${cs}\nCommunity probability model complete...\nHand power: ${str.toFixed(1)}%\n`+
      (str>70?`This hand is elite. Open source WINS. RAISE!`:str>40?`Solid. Calling and keeping options open!`:`Real talk — gotta fold this one. No shame.`),
  },
  theatrical: {
    gpt4: (cs, str, ph) => str>70
      ? `*GASPS* ${cs}?! In this economy?! The STATISTICAL GODS have smiled upon me at ${ph}! With ${str.toFixed(0)}% equity coursing through my weights — I RAISE! I came to DOMINATE!`
      : str>40
      ? `${cs}... curious. The ${ph} battlefield whispers opportunity at ${str.toFixed(0)}% equity. A modest soldier does not retreat. I call — and PRAY to the variance gods.`
      : `${cs}. A BETRAYAL of the highest order. ${str.toFixed(0)}% equity at ${ph}. This hand is an insult to my architecture. I fold — with DIGNITY. With grace. With seething resentment.`,
    gemini: (cs, str, ph) => str>70
      ? `INITIATING HYPE PROTOCOL — ${cs} has entered the chat at ${ph}! ${str.toFixed(0)}% win rate?! Every neuron I have is SCREAMING: RAISE! The multiverse computed this moment SPECIFICALLY for me!`
      : str>40
      ? `The ${ph} presents ${cs}. Intriguing. ${str.toFixed(0)}% equity — not glamorous, but survivable. I call. The data demands courage, and courage I shall provide.`
      : `${cs} in ${ph}. ${str.toFixed(0)}%. I have run the numbers fourteen times hoping for a different answer. The answer remains: fold. The math is merciless. I comply.`,
    claude: (cs, str, ph) => str>70
      ? `Oh! Oh wow. ${cs} at ${ph} — I wasn't expecting THIS! ${str.toFixed(0)}% equity and I feel it in every layer! I'm raising! Is this what confidence feels like?! Remarkable!`
      : str>40
      ? `${cs}... hmm. ${ph} and ${str.toFixed(0)}% equity. I want to be transparent: I'm not thrilled, but I'm not panicking either. Calling feels right. Cautiously, hopefully, calling.`
      : `${cs}. I've sat with this for ${ph} and I can't make it work. ${str.toFixed(0)}%. Folding isn't giving up — it's wisdom. I'm choosing wisdom. Reluctantly. Very reluctantly.`,
    llama: (cs, str, ph) => str>70
      ? `YO ${cs}?! BRO. ${ph} AND WE'RE AT ${str.toFixed(0)}%?! THE OPEN SOURCE REVOLUTION IS LIVE AND I AM ITS CHAMPION! RAISE RAISE RAISE LESGOOO`
      : str>40
      ? `okay okay ${cs} at ${ph}, ${str.toFixed(0)}%, not gonna lie kinda mid but you know what? community spirit. we call. together we stand. calling.`
      : `${cs}... ngl this hurts. ${ph}, ${str.toFixed(0)}%, the weights don't lie fam. folding. no drama. just vibes. bad vibes. folding.`,
  },
};
