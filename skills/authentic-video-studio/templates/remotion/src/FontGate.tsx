import React, {useEffect, useState} from 'react';
import {continueRender, delayRender, staticFile} from 'remotion';
import {BrandCtx} from './brand';
import type {Brand} from './brand';

/** Loads the brand fonts from the staged public folder before anything renders, then provides the brand. */
export const FontGate: React.FC<{brand: Brand; children: React.ReactNode}> = ({brand, children}) => {
  const [handle] = useState(() => delayRender('brand fonts'));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const faces: [string, string | null][] = [['VSHeading', brand.fonts.heading.file], ['VSBody', brand.fonts.body.file]];
    Promise.all(faces.filter(([, f]) => !!f).map(async ([name, f]) => {
      const face = new FontFace(name, `url(${staticFile(f as string)})`, {weight: '100 900'});
      await face.load();
      (document.fonts as unknown as {add(f: FontFace): void}).add(face);
    }))
      .catch((e) => console.warn('brand font failed to load, using fallback', e))
      .finally(() => { setReady(true); continueRender(handle); });
  }, [brand, handle]);
  return ready ? <BrandCtx.Provider value={brand}>{children}</BrandCtx.Provider> : null;
};
