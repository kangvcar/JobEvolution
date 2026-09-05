import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import { SceneOpen } from './live/SceneOpen';
import { SceneFlyIn } from './live/SceneFlyIn';
import { SceneDetail } from './live/SceneDetail';
import { SceneClip } from './live/SceneClip';
import { SceneReport } from './live/SceneReport';
import { PaperTitleCard } from './PaperTitleCard';
import { SceneOutroLive } from './live/SceneOutroLive';
import { FlashCut } from './FlashCut';
import { Caption } from './Caption';
import { PAPER } from './theme';

// ~43.2s @ 30fps — Ink Press structure, JobEvolution skin (11 shots). Both
// wordmark moments (brand open, outro sign-off) hold a full second once on.
export const AIFL_SHOTS = {
  morning: { from: 0, duration: 220 },    // 0–7.3s   brand ~46f + 30f hold + home macro (release readout hero)
  card1: { from: 220, duration: 55 },     // 7.3–9.2s "3,586 份 JD，长成一张岗位能力图谱。"
  table: { from: 275, duration: 190 },    // 9.2–15.5s pile close-up → deal 12 job rows → rest → search → filter → click
  macro: { from: 465, duration: 100 },    // 15.5–18.8s Agent dossier: requirement rows embed
  card2: { from: 565, duration: 55 },     // 18.8–20.7s "图谱工作台，看清要求边怎么来。"
  graph: { from: 620, duration: 135 },    // 20.7–25.2s graph workbench — real operation footage
  cardDx: { from: 755, duration: 50 },    // 25.2–26.8s "上传一份简历，换档条件算给你看。"
  dx: { from: 805, duration: 180 },       // 26.8–32.8s diagnose flow — real operation footage
  report: { from: 985, duration: 110 },   // 32.8–36.5s diagnosis report writes itself
  card3: { from: 1095, duration: 55 },    // 36.5–38.3s "每一条结论，都回溯到简历与 JD 原文。"
  outro: { from: 1150, duration: 145 },   // 38.3–43.2s defocus + group photo + wordmark (+1s hold)
} as const; // sum = 1295

export const AIFL_TOTAL = 1295;

const S = AIFL_SHOTS;

// bottom-strip narration over the live shots (absolute frames; outro stays clean)
const CAPTIONS = [
  { from: S.morning.from + 90, duration: 40, text: '四个领域 · 9 个入谱岗位 · 3,586 份去重 JD' },
  { from: S.table.from + 43, duration: 44, text: '每日采集 · 候选 → 萌芽 → 成型' },
  { from: S.table.from + 120, duration: 52, text: '搜索 · 筛选 · 打开卷宗' },
  { from: S.macro.from + 12, duration: 68, text: '每条要求边 · 至少两个独立源印证' },
  { from: S.graph.from + 14, duration: 106, text: '图谱工作台 · 点开要求看原文证据' },
  { from: S.dx.from + 12, duration: 156, text: '上传简历 → 校对 → 选岗 → 生成对照' },
  { from: S.report.from + 14, duration: 84, text: '诊断报告 · 档位 · 换档条件 · 证据' },
] as const;

// sound design pinned to animation beats, expressed relative to each shot's
// start (sound-design §4.5) so a timeline shift never desyncs a whole table.
const at = (shot: keyof typeof AIFL_SHOTS, rel: number) => AIFL_SHOTS[shot].from + rel;
const SFX: { from: number; src: string; volume: number; dur?: number }[] = [
  // brand open: soft transition as the lockup lands, whoosh into the home page
  { from: at('morning', 12), src: 'transition-soft.mp3', volume: 0.4 },
  { from: at('morning', 78), src: 'whoosh-fast.mp3', volume: 0.45 },
  // hero readout: whoosh up on the pop, sparkle on the beam scan, snap reseat
  { from: at('morning', 127), src: 'whoosh-big.mp3', volume: 0.5 },
  { from: at('morning', 141), src: 'sparkle.mp3', volume: 0.35 },
  { from: at('morning', 204), src: 'transition-snap.mp3', volume: 0.5 },
  // title cards ride a quick swoosh
  { from: at('card1', 0), src: 'swoosh-quick.mp3', volume: 0.4 },
  // deck shot: soft transition into the pile close-up, whoosh as the orbit
  // pulls back and dealing starts, fast whooshes as the deal accelerates,
  // then the rest → big whoosh up to the search box
  { from: at('table', 2), src: 'transition-soft.mp3', volume: 0.4 },
  { from: at('table', 33), src: 'whoosh-big.mp3', volume: 0.5 },
  { from: at('table', 50), src: 'whoosh-fast.mp3', volume: 0.4 },
  { from: at('table', 62), src: 'whoosh-fast.mp3', volume: 0.32 },
  { from: at('table', 97), src: 'whoosh-big.mp3', volume: 0.5 },
  // typing (3f/char) + a breath + filter + click + push-in
  { from: at('table', 120), src: 'keyboard.mp3', volume: 0.4, dur: 18 },
  { from: at('table', 150), src: 'whoosh-fast.mp3', volume: 0.4 },
  { from: at('table', 176), src: 'click-camera.mp3', volume: 0.6 },
  { from: at('table', 180), src: 'swoosh-quick.mp3', volume: 0.35 },
  // dossier rows embed with one cinematic transition sweep
  { from: at('macro', 10), src: 'transition-soft.mp3', volume: 0.45 },
  { from: at('card2', 0), src: 'swoosh-quick.mp3', volume: 0.4 },
  // graph workbench footage: soft transition in; camera-clicks on the real clicks
  { from: at('graph', 3), src: 'transition-soft.mp3', volume: 0.45 },
  { from: at('cardDx', 0), src: 'swoosh-quick.mp3', volume: 0.4 },
  // diagnose footage: soft transition in; camera-clicks on the real clicks
  { from: at('dx', 3), src: 'transition-soft.mp3', volume: 0.4 },
  // report: the page "writes itself" over live keyboard typing, then the
  // report-view rail items pop in one by one (a pop per landing)
  { from: at('report', 4), src: 'transition-soft.mp3', volume: 0.4 },
  { from: at('report', 6), src: 'keyboard.mp3', volume: 0.34, dur: 44 },
  { from: at('report', 60), src: 'pop.mp3', volume: 0.4 },
  { from: at('report', 65), src: 'pop.mp3', volume: 0.36 },
  { from: at('report', 70), src: 'pop.mp3', volume: 0.32 },
  { from: at('report', 75), src: 'pop.mp3', volume: 0.28 },
  { from: at('card3', 0), src: 'swoosh-quick.mp3', volume: 0.4 },
  // outro: riser under the assembly, big impact when the wordmark stamps
  { from: at('outro', 5), src: 'riser-cine.mp3', volume: 0.5 },
  { from: at('outro', 40), src: 'impact-cine.mp3', volume: 0.55 },
  { from: at('outro', 65), src: 'sparkle.mp3', volume: 0.3 },
];

/** Click beats inside the two footage shots (frames relative to the shot),
 * filled in from the recording logs. */
export const FOOTAGE_CLICKS: { shot: 'graph' | 'dx'; rel: number }[] = [];

export const AiflMain: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: PAPER }}>
      {SFX.map((s, i) => (
        <Sequence key={`sfx-${i}`} from={s.from} durationInFrames={s.dur ?? 90}>
          <Audio src={staticFile(`audio/${s.src}`)} volume={s.volume} />
        </Sequence>
      ))}
      {FOOTAGE_CLICKS.map((c, i) => (
        <Sequence key={`click-${i}`} from={at(c.shot, c.rel)} durationInFrames={40}>
          <Audio src={staticFile('audio/click-camera.mp3')} volume={0.45} />
        </Sequence>
      ))}

      <Sequence from={S.morning.from} durationInFrames={S.morning.duration}><SceneOpen /></Sequence>
      <Sequence from={S.card1.from} durationInFrames={S.card1.duration}>
        <PaperTitleCard duration={S.card1.duration} words={[{ text: '3,586 份 JD，' }, { text: '长成一张' }, { text: '岗位能力图谱', accent: true }, { text: '。' }]} />
      </Sequence>
      <Sequence from={S.table.from} durationInFrames={S.table.duration}><SceneFlyIn /></Sequence>
      <Sequence from={S.macro.from} durationInFrames={S.macro.duration}><SceneDetail /></Sequence>
      <Sequence from={S.card2.from} durationInFrames={S.card2.duration}>
        <PaperTitleCard duration={S.card2.duration} words={[{ text: '图谱工作台，' }, { text: '看清' }, { text: '要求边', accent: true }, { text: '怎么来。' }]} sub="条正式要求 · Agent 工程师 · 6 个独立源" subDigits="22" />
      </Sequence>
      <Sequence from={S.graph.from} durationInFrames={S.graph.duration}>
        <SceneClip src="clips/graph-ops.mp4" duration={S.graph.duration} kicker="图谱工作台 · AGENT 工程师" drift={1} />
      </Sequence>
      <Sequence from={S.cardDx.from} durationInFrames={S.cardDx.duration}>
        <PaperTitleCard duration={S.cardDx.duration} words={[{ text: '上传一份简历，' }, { text: '换档条件', accent: true }, { text: '算给你看。' }]} />
      </Sequence>
      <Sequence from={S.dx.from} durationInFrames={S.dx.duration}>
        <SceneClip src="clips/diagnose-flow.mp4" duration={S.dx.duration} kicker="简历诊断 · 5 步" drift={-1} />
      </Sequence>
      <Sequence from={S.report.from} durationInFrames={S.report.duration}><SceneReport /></Sequence>
      <Sequence from={S.card3.from} durationInFrames={S.card3.duration}>
        <PaperTitleCard duration={S.card3.duration} words={[{ text: '每一条结论，' }, { text: '都' }, { text: '回溯', accent: true }, { text: '到简历与 JD 原文。' }]} />
      </Sequence>
      <Sequence from={S.outro.from} durationInFrames={S.outro.duration}><SceneOutroLive /></Sequence>

      {CAPTIONS.map((c) => (
        <Sequence key={c.from} from={c.from} durationInFrames={c.duration}>
          <Caption text={c.text} duration={c.duration} />
        </Sequence>
      ))}
      {/* paper-white flash cuts straddling the hard scene changes */}
      {[S.table.from, S.macro.from, S.graph.from, S.report.from].map((cut) => (
        <Sequence key={cut} from={cut - 5} durationInFrames={10}>
          <FlashCut duration={10} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
