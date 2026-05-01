export const SUITS = ['♠', '♥', '♦', '♣'] as const;
export const RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'] as const;
export const RANK_V: Record<string, number> = {
  2:2, 3:3, 4:4, 5:5, 6:6, 7:7, 8:8, 9:9, 10:10, J:11, Q:12, K:13, A:14,
};

export const MODELS = [
  { id:'gpt4',   name:'GPT-4o',  org:'OpenAI',    color:'#10a37f', deck:'url(/assets/deck-blue.png)'   },
  { id:'gemini', name:'Gemini',  org:'Google',    color:'#4285f4', deck:'url(/assets/deck-yellow.png)' },
  { id:'claude', name:'Claude',  org:'Anthropic', color:'#d97757', deck:'url(/assets/deck-red.png)'    },
  { id:'llama',  name:'Llama 3', org:'Meta',      color:'#a855f7', deck:'url(/assets/deck-ghost.png)'  },
] as const;

export type ModelId = 'gpt4' | 'gemini' | 'claude' | 'llama';
export type VoiceMode = 'analytical' | 'balanced' | 'theatrical';
export type AtmosphereMode = 'felt' | 'neon' | 'noir';
export type TempoMode = 'cinematic' | 'normal' | 'turbo';

export const THEMES: Record<AtmosphereMode, {
  tableBg: string; panelBg: string; panelBorder: string;
  topBar: string; accent: string; cardBack: string; tex: string; name: string;
}> = {
  felt: {
    tableBg: 'radial-gradient(ellipse at 50% 45%, #1a5c3b 0%, #0d3321 55%, #061910 100%)',
    panelBg: '#080c12', panelBorder: 'rgba(255,255,255,0.07)',
    topBar: 'rgba(0,0,0,0.55)', accent: '#52b788',
    cardBack: 'url(/assets/deck-red.png)',
    tex: 'rgba(0,0,0,0.04)', name: 'Green Felt',
  },
  neon: {
    tableBg: 'radial-gradient(ellipse at 50% 45%, #1a0d3a 0%, #0a0519 55%, #030110 100%)',
    panelBg: '#07050f', panelBorder: 'rgba(192,132,252,0.12)',
    topBar: 'rgba(0,0,0,0.7)', accent: '#c084fc',
    cardBack: 'url(/assets/deck-plasma.png)',
    tex: 'rgba(139,92,246,0.04)', name: 'Neon Underground',
  },
  noir: {
    tableBg: 'radial-gradient(ellipse at 50% 45%, #3a0a0a 0%, #1a0404 55%, #0a0202 100%)',
    panelBg: '#0b0404', panelBorder: 'rgba(248,113,113,0.1)',
    topBar: 'rgba(0,0,0,0.75)', accent: '#f87171',
    cardBack: 'url(/assets/deck-ghost.png)',
    tex: 'rgba(239,68,68,0.03)', name: 'Noir',
  },
};

export const TEMPO_MULT: Record<TempoMode, number> = {
  cinematic: 2.6, normal: 1.0, turbo: 0.2,
};

export const STAKE_COLORS: Record<string, { bg: string; shadow: string; text: string; border?: string }> = {
  white:  { bg:'rgb(220,220,220)', shadow:'rgb(140,140,140)',  text:'rgb(50,50,50)'    },
  blue:   { bg:'rgb(1,139,246)',   shadow:'rgb(0,80,160)',     text:'#fff'             },
  red:    { bg:'rgb(239,70,55)',   shadow:'rgb(140,30,15)',    text:'#fff'             },
  green:  { bg:'rgb(37,120,95)',   shadow:'rgb(18,70,55)',     text:'#fff'             },
  purple: { bg:'rgb(151,71,255)',  shadow:'rgb(90,30,160)',    text:'#fff'             },
  orange: { bg:'rgb(250,140,1)',   shadow:'rgb(160,85,0)',     text:'#fff'             },
  gold:   { bg:'rgb(255,215,102)', shadow:'rgb(180,140,20)',   text:'rgb(80,50,0)'     },
  black:  { bg:'rgb(31,42,44)',    shadow:'rgb(10,15,16)',     text:'#fff', border:'rgb(80,100,102)' },
};

export const STAKE_MAP: Record<string, string> = {
  gpt4:'blue', gemini:'green', claude:'orange', llama:'purple',
};
