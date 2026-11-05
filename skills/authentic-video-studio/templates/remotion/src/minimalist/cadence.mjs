export const SCISSORS_WORD_OFFSETS = [0, 4, 8.25, 15.45, 19.65, 23.65];
export const SCISSORS_CLICK_WORDS = [0, 2, 4, 5];
export function scissorsWordOffset(index) {
    return index < SCISSORS_WORD_OFFSETS.length
        ? SCISSORS_WORD_OFFSETS[index]
        : SCISSORS_WORD_OFFSETS[5] + 4 * (index - 5);
}
