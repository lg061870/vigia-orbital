import React from 'react';
import {registerRoot, Composition, AbsoluteFill, Sequence, Audio, Img, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';

const FPS = 30;
const GAP = 0.45;            // pause between narrations (s)
const XF = 14;               // crossfade frames
const SMS = `FIRE RISK · LIBERIA
Issued Thu 18 Jan 2018
Fri Moderate · Sat Moderate · Sun High · Mon High · Tue High
Highest: Tue HIGH (39 %)
Vigía Orbital`;

// [audio, seconds, visuals: list of {img, at (s), focus [x,y] in 0..1, zoom}]
const SHOTS = [
  {a: 'a1', d: 15.70, v: [{img: 'slides/s1.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a2', d: 19.30, v: [{img: 'slides/s2.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a3', d: 18.75, v: [{img: 'slides/s3.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a4', d: 24.05, v: [
    {img: 'site/a.png', at: 0, focus: [0.5, 0.5], zoom: 1.03, cap: true},
    {img: 'site/b.png', at: 6.0, focus: [0.5, 0.5], zoom: 1.03, cap: true},
    {img: 'site/c.png', at: 10.5, focus: [0.5, 0.5], zoom: 1.03, cap: true},
    {sms: true, at: 16.5}]},
  {a: 'a6', d: 35.50, v: [{img: 'slides/s6.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a7', d: 23.62, v: [{img: 'slides/s7.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}, {img: 'slides/s8.png', at: 17.9, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a9', d: 29.20, v: [{img: 'slides/s9.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a10', d: 17.65, v: [{img: 'slides/s10.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
  {a: 'a12', d: 16.70, v: [{img: 'slides/s12.png', at: 0, focus: [0.5, 0.5], zoom: 1.03}]},
];
const f = s => Math.round(s * FPS);
let t = f(0.6);
const TIMED = SHOTS.map(s => { const start = t; const len = f(s.d + GAP); t += len; return {...s, start, len}; });
const TOTAL = t + f(2.2);

const Still = ({img, focus, zoom, from = 1, len, cap}) => {
  const fr = useCurrentFrame();
  const z = interpolate(fr, [0, len], [from, zoom], {extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad)});
  const op = interpolate(fr, [0, XF], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{opacity: op, backgroundColor: '#0F2236'}}>
      <Img src={staticFile(img)} style={{width: 1920, height: 1080, transform: `scale(${z})`, transformOrigin: `${focus[0] * 100}% ${focus[1] * 100}%`}} />
      {cap ? <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 54, background: 'rgba(15,34,54,0.92)', color: '#FAF8F3', font: '600 30px Arial', display: 'flex', alignItems: 'center', justifyContent: 'center', letterSpacing: 0.5}}>Live at&nbsp;<span style={{color: '#F5B971'}}>lg061870.github.io/vigia-orbital</span></div> : null}
    </AbsoluteFill>
  );
};

const Sms = ({len}) => {
  const fr = useCurrentFrame();
  const op = interpolate(fr, [0, XF], [0, 1], {extrapolateRight: 'clamp'});
  const up = interpolate(fr, [6, 24], [60, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const lines = SMS.split('\n');
  return (
    <AbsoluteFill style={{opacity: op, background: 'linear-gradient(160deg,#0F2236,#1b3550)', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{color: '#F5B971', font: '700 44px Arial', marginBottom: 14}}>The same forecast, as a text message</div>
      <div style={{color: '#C9D6E2', font: '400 30px Arial', marginBottom: 36}}>GET /api/sms?canton=Liberia&eve=2018-01-18 · open API (FastAPI) · under 1 KB</div>
      <div style={{transform: `translateY(${up}px)`, width: 1050, background: '#FAF8F3', borderRadius: 36, padding: '40px 52px', boxShadow: '0 20px 60px rgba(0,0,0,.45)'}}>
        {lines.map((l, i) => {
          const o = interpolate(fr, [18 + i * 14, 30 + i * 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return <div key={i} style={{opacity: o, font: `${i === 0 ? 700 : 400} ${i === 0 ? 46 : 40}px Arial`, color: i === 0 ? '#C4471A' : '#0F2236', lineHeight: 1.5}}>{l}</div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const Video = () => {
  const fr = useCurrentFrame();
  const fade = interpolate(fr, [0, 15, TOTAL - 30, TOTAL - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{backgroundColor: '#0F2236'}}>
      <AbsoluteFill style={{opacity: fade}}>
        {TIMED.map((s, i) => {
          const last = i === TIMED.length - 1;
          return s.v.map((v, j) => {
            const from = s.start + f(v.at) - (i + j === 0 ? f(0.6) : 0);
            const next = s.v[j + 1];
            const end = next ? s.start + f(next.at) + XF : s.start + s.len + (last ? f(2.2) : XF);
            const len = end - from;
            return (
              <Sequence key={`${i}-${j}`} from={from} durationInFrames={len}>
                {v.sms ? <Sms len={len} /> : <Still {...v} len={len} />}
              </Sequence>
            );
          });
        })}
      </AbsoluteFill>
      {TIMED.map((s, i) => (
        <Sequence key={'a' + i} from={s.start} durationInFrames={s.len}>
          <Audio src={staticFile(`audio/${s.a}.wav`)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

registerRoot(() => <Composition id="Vigia" component={Video} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />);
