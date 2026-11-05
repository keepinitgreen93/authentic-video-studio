// Usage: node validate-plan.mjs plan.json
// Prints one JSON line: {valid, errors, warnings}. Uses the same planner the renderer uses.
import fs from 'node:fs';
import {validatePlan} from './src/minimalist/plan.mjs';

const file = process.argv[2];
if (!file) {
  console.log(JSON.stringify({valid: false, errors: ['usage: node validate-plan.mjs plan.json'], warnings: []}));
  process.exit(2);
}
const plan = JSON.parse(fs.readFileSync(file, 'utf8'));
if (!plan.source) plan.source = {src: 'host/cut.mp4', durationInFrames: plan.durationInFrames ?? 100000};
console.log(JSON.stringify(validatePlan(plan)));
