/** Captured from the approved "Remove dead air" overlay at 30 fps.
 * Preserve its six word entrances and four sound accents as one reusable unit.
 */
export type CaptionCadence = 'scissors';
export const SCISSORS_WORD_OFFSETS = [0,4,8.25,15.45,19.65,23.65] as const;
export const SCISSORS_CLICK_WORDS = [0,2,4,5] as const;

export function scissorsWordOffset(index:number):number {
  return index<SCISSORS_WORD_OFFSETS.length
    ?SCISSORS_WORD_OFFSETS[index]
    :SCISSORS_WORD_OFFSETS[5]+4*(index-5);
}
