import type { MigratedSlot } from '../types';

// Extract complete migrated_slot objects from partial/streaming JSON text.
// Returns whatever slots have fully streamed in so far.
export function extractPartialSlots(text: string): MigratedSlot[] {
  const arrStart = text.indexOf('"migrated_slots"');
  if (arrStart < 0) return [];
  const bracket = text.indexOf('[', arrStart);
  if (bracket < 0) return [];

  const slots: MigratedSlot[] = [];
  let i = bracket + 1;
  const n = text.length;

  while (i < n) {
    // skip whitespace/commas
    while (i < n && (text[i] === ' ' || text[i] === '\n' || text[i] === ',' || text[i] === '\r' || text[i] === '\t')) i++;
    if (i >= n || text[i] === ']') break;
    if (text[i] !== '{') { i++; continue; }

    // scan balanced object
    let depth = 0;
    let inStr = false;
    let esc = false;
    const objStart = i;
    let objEnd = -1;
    for (let j = i; j < n; j++) {
      const c = text[j];
      if (inStr) {
        if (esc) esc = false;
        else if (c === '\\') esc = true;
        else if (c === '"') inStr = false;
      } else {
        if (c === '"') inStr = true;
        else if (c === '{') depth++;
        else if (c === '}') {
          depth--;
          if (depth === 0) { objEnd = j; break; }
        }
      }
    }
    if (objEnd < 0) break; // object not complete yet

    const objText = text.slice(objStart, objEnd + 1);
    try {
      slots.push(JSON.parse(objText) as MigratedSlot);
    } catch {
      break;
    }
    i = objEnd + 1;
  }

  return slots;
}
