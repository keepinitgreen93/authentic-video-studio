import React from 'react';

/** Everything visual comes from this object. vs.py builds it from brand.yaml. */
export type FontSpec = {family: string; file: string | null};
export type Brand = {
  name: string;
  colors: {primary: string; accent: string; background: string; text: string};
  fonts: {heading: FontSpec; body: FontSpec};
  logo: {file: string | null; position: string; scale: number};
  theme: {
    ink: string;            // dark surface for graphics
    label: string;          // text on ink
    accentOnDark: string;   // accent adjusted to read on dark surfaces
    accentRgb: string;      // "r,g,b" for glows
    gridLight: boolean;
    bg: [string, string, string];
    tileRgb: string;
    vignetteRgb: string;
    mini: {inner: string; middle: string; outer: string; text: string; highlight: string};
    hookBox: string;
    hookText: string;
    endBox: string;
    endText: string;
    widthFactor: number;    // brand font width relative to Arial Bold
  };
  hook?: {lines: string[]; seconds: number};
  endCard?: {text: string; seconds: number};
};

export const DEFAULT_BRAND: Brand = {
  name: 'Your Brand',
  colors: {primary: '#2563EB', accent: '#F59E0B', background: '#FFFFFF', text: '#111827'},
  fonts: {heading: {family: 'Arial', file: null}, body: {family: 'Arial', file: null}},
  logo: {file: null, position: 'top-right', scale: 0.16},
  theme: {
    ink: '#0B1220', label: '#F8FAFC', accentOnDark: '#F59E0B', accentRgb: '245,158,11', gridLight: true,
    bg: ['#FFFFFF', '#F3F6FC', '#E5EBF8'], tileRgb: '17,24,39', vignetteRgb: '37,99,235',
    mini: {inner: '#14306B', middle: '#0C1D43', outer: '#060F24', text: '#F8FAFC', highlight: '#F59E0B'},
    hookBox: 'rgba(37,99,235,0.92)', hookText: '#FFFFFF', endBox: 'rgba(245,158,11,0.95)', endText: '#111827',
    widthFactor: 1,
  },
};

export const HEADING = '"VSHeading", Arial, Helvetica, sans-serif';
export const BODY = '"VSBody", Arial, Helvetica, sans-serif';

export const BrandCtx = React.createContext<Brand>(DEFAULT_BRAND);
export const useBrand = () => React.useContext(BrandCtx);
