import { registerRoot, Composition } from 'remotion';
import { PromoVideo } from './PromoVideo';
import React from 'react';

registerRoot(() => {
  return (
    <Composition
      id="PromoVideo"
      component={PromoVideo}
      durationInFrames={1140}
      fps={30}
      width={1920}
      height={1080}
    />
  );
});
